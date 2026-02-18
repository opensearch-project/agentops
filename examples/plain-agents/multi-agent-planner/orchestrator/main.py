#!/usr/bin/env python3
"""
Travel Planner - Orchestrates weather and events agents.
Supports fault injection at orchestrator level and pass-through to sub-agents.
"""

import asyncio
import os
import random
import time
import json
from typing import Optional
from uuid import uuid4

import httpx
from fastapi import FastAPI
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from pydantic import BaseModel, Field


AGENT_ID = "travel-planner-001"
AGENT_NAME = "Travel Planner"

WEATHER_AGENT_URL = os.getenv("WEATHER_AGENT_URL", "http://weather-agent:8000")
EVENTS_AGENT_URL = os.getenv("EVENTS_AGENT_URL", "http://events-agent:8002")

# Tool definitions for this agent
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather information for a destination by calling the weather agent",
            "parameters": {"type": "object", "properties": {"destination": {"type": "string"}}, "required": ["destination"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "Get local events for a destination by calling the events agent",
            "parameters": {"type": "object", "properties": {"destination": {"type": "string"}}, "required": ["destination"]}
        }
    }
]

# Model rotation for realistic traces
MODELS = [
    "claude-opus-4.5", "claude-sonnet-4.5", "claude-haiku-4.5", "claude-sonnet-4", "claude-haiku",
    "gpt-5", "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o4-mini",
    "gemini-3-flash", "gemini-2.5-pro", "gemini-2.5-flash",
    "nova-2-pro", "nova-2-lite", "nova-premier", "nova-pro", "nova-lite",
]
SYSTEMS = {
    "claude-opus-4.5": "anthropic", "claude-sonnet-4.5": "anthropic", "claude-haiku-4.5": "anthropic",
    "claude-sonnet-4": "anthropic", "claude-haiku": "anthropic",
    "gpt-5": "openai", "gpt-4.1": "openai", "gpt-4.1-mini": "openai",
    "gpt-4o": "openai", "gpt-4o-mini": "openai", "o4-mini": "openai",
    "gemini-3-flash": "google", "gemini-2.5-pro": "google", "gemini-2.5-flash": "google",
    "nova-2-pro": "amazon", "nova-2-lite": "amazon", "nova-premier": "amazon",
    "nova-pro": "amazon", "nova-lite": "amazon",
}


class SubAgentFault(BaseModel):
    type: str = Field(..., description="Fault type: timeout, error, rate_limited, high_latency, wrong_city, empty")
    delay_ms: int = Field(0, description="Delay in ms for high_latency")
    probability: float = Field(1.0, description="Probability of fault (0.0-1.0)")
    wrong_city: Optional[str] = Field(None, description="For wrong_city fault: return events from this city")


class FaultConfig(BaseModel):
    orchestrator: Optional[str] = Field(None, description="Orchestrator fault: partial_failure, fan_out_timeout")
    weather: Optional[SubAgentFault] = Field(None, description="Fault to inject in weather-agent")
    events: Optional[SubAgentFault] = Field(None, description="Fault to inject in events-agent")


class PlanRequest(BaseModel):
    destination: str
    fault: Optional[FaultConfig] = None


class PlanResponse(BaseModel):
    destination: str
    weather: Optional[dict] = None
    events: list = []
    recommendation: str
    partial: bool = False
    errors: list = []


def setup_telemetry(service_name: str, otlp_endpoint: str):
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "gen_ai.agent.id": AGENT_ID,
        "gen_ai.agent.name": AGENT_NAME,
    })
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)
    HTTPXClientInstrumentor().instrument()
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
        export_interval_millis=10000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    return trace.get_tracer(service_name), metrics.get_meter(service_name)


otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
tracer, meter = setup_telemetry("travel-planner", otlp_endpoint)


inner_app = FastAPI(title="Travel Planner", version="1.0.0")


@inner_app.get("/health")
async def health():
    return {"status": "healthy", "agent_id": AGENT_ID, "agent_name": AGENT_NAME}


@inner_app.post("/plan")
async def plan_trip(request: PlanRequest):
    model = random.choice(MODELS)
    
    # Promote gen_ai attributes to the root HTTP span so the UI can read them
    root_span = trace.get_current_span()
    root_span.set_attribute("gen_ai.system", SYSTEMS[model])
    root_span.set_attribute("gen_ai.agent.name", AGENT_NAME)
    root_span.set_attribute("gen_ai.request.model", model)
    root_span.set_attribute("gen_ai.operation.name", "invoke_agent")
    root_span.set_attribute("gen_ai.input.messages", json.dumps(
        [{"role": "user", "parts": [{"type": "text", "content": f"Plan a trip to {request.destination}"}]}]
    ))
    
    with tracer.start_as_current_span(
        "invoke_agent",
        kind=SpanKind.INTERNAL,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.id": AGENT_ID,
            "gen_ai.agent.name": AGENT_NAME,
            "gen_ai.system": SYSTEMS[model],
            "gen_ai.request.model": model,
            "gen_ai.tool.definitions": json.dumps(TOOL_DEFINITIONS),
            "destination": request.destination,
        },
    ) as span:
        fault = request.fault
        errors = []
        weather_data = None
        events_data = []

        # Synthetic "thinking" LLM call
        with tracer.start_as_current_span("chat", kind=SpanKind.INTERNAL) as chat_span:
            chat_span.set_attribute("gen_ai.operation.name", "chat")
            chat_span.set_attribute("gen_ai.system", SYSTEMS[model])
            chat_span.set_attribute("gen_ai.request.model", model)
            input_tokens = random.randint(500, 2000)
            output_tokens = random.randint(100, 500)
            chat_span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            chat_span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
            chat_span.set_attribute("gen_ai.response.finish_reasons", ["tool_calls"])
            time.sleep(random.uniform(0.1, 0.3))

        # Build sub-agent payloads with fault pass-through
        weather_payload = {"message": f"What's the weather in {request.destination}?"}
        events_payload = {"destination": request.destination}

        if fault:
            if fault.weather:
                weather_payload["fault"] = fault.weather.model_dump()
            if fault.events:
                events_payload["fault"] = fault.events.model_dump()

        # Orchestrator-level fault injection
        if fault and fault.orchestrator:
            span.set_attribute("fault.orchestrator", fault.orchestrator)

            if fault.orchestrator == "fan_out_timeout":
                timeout = 0.001
            else:
                timeout = 30.0
        else:
            timeout = 30.0

        # Fan out to sub-agents
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Invoke weather agent
            with tracer.start_as_current_span("invoke_agent weather-agent", kind=SpanKind.CLIENT) as agent_span:
                agent_span.set_attribute("gen_ai.operation.name", "invoke_agent")
                agent_span.set_attribute("gen_ai.agent.name", "weather-agent")
                try:
                    if fault and fault.orchestrator == "partial_failure" and random.random() < 0.5:
                        raise Exception("Simulated partial failure - skipping weather")
                    resp = await client.post(f"{WEATHER_AGENT_URL}/invoke", json=weather_payload)
                    if resp.status_code == 200:
                        weather_data = resp.json()
                    else:
                        errors.append({"agent": "weather", "error": resp.text})
                        agent_span.set_status(Status(StatusCode.ERROR, resp.text))
                except Exception as e:
                    errors.append({"agent": "weather", "error": str(e)})
                    agent_span.set_status(Status(StatusCode.ERROR, str(e)))

            # Invoke events agent
            with tracer.start_as_current_span("invoke_agent events-agent", kind=SpanKind.CLIENT) as agent_span:
                agent_span.set_attribute("gen_ai.operation.name", "invoke_agent")
                agent_span.set_attribute("gen_ai.agent.name", "events-agent")
                try:
                    if fault and fault.orchestrator == "partial_failure" and random.random() < 0.5:
                        raise Exception("Simulated partial failure - skipping events")
                    resp = await client.post(f"{EVENTS_AGENT_URL}/events", json=events_payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        if "error" not in data:
                            events_data = data.get("events", [])
                        else:
                            errors.append({"agent": "events", "error": data["error"]})
                            agent_span.set_status(Status(StatusCode.ERROR, str(data["error"])))
                    else:
                        errors.append({"agent": "events", "error": resp.text})
                        agent_span.set_status(Status(StatusCode.ERROR, resp.text))
                except Exception as e:
                    errors.append({"agent": "events", "error": str(e)})
                    tool_span.set_status(Status(StatusCode.ERROR, str(e)))

        # Final response "chat" span
        with tracer.start_as_current_span("chat", kind=SpanKind.INTERNAL) as chat_span:
            chat_span.set_attribute("gen_ai.operation.name", "chat")
            chat_span.set_attribute("gen_ai.system", SYSTEMS[model])
            chat_span.set_attribute("gen_ai.request.model", model)
            chat_span.set_attribute("gen_ai.usage.input_tokens", random.randint(200, 800))
            chat_span.set_attribute("gen_ai.usage.output_tokens", random.randint(50, 200))
            chat_span.set_attribute("gen_ai.response.finish_reasons", ["stop"])
            time.sleep(random.uniform(0.05, 0.15))

        # Build recommendation with graceful degradation
        partial = len(errors) > 0
        if partial:
            span.set_attribute("response.partial", True)
            span.set_attribute("response.errors_count", len(errors))
            for i, err in enumerate(errors):
                span.set_attribute(f"response.error_{i}_agent", err["agent"])
                span.set_attribute(f"response.error_{i}_message", str(err["error"])[:200])
            span.set_status(Status(StatusCode.ERROR, f"Partial failure: {len(errors)} sub-agent(s) failed"))

        recommendation = build_recommendation(request.destination, weather_data, events_data, partial)

        root_span.set_attribute("gen_ai.output.messages", json.dumps(
            [{"role": "assistant", "parts": [{"type": "text", "content": recommendation}]}]
        ))

        return PlanResponse(
            destination=request.destination,
            weather=weather_data,
            events=events_data,
            recommendation=recommendation,
            partial=partial,
            errors=errors,
        )


def build_recommendation(destination: str, weather: Optional[dict], events: list, partial: bool) -> str:
    parts = [f"Great choice! {destination} looks wonderful."]

    if weather and "response" in weather:
        parts.append(weather["response"])
    elif partial:
        parts.append("Weather info temporarily unavailable.")

    if events:
        event_names = [e["name"] for e in events[:2]]
        parts.append(f"Check out {', '.join(event_names)}.")
    elif partial:
        parts.append("Events info temporarily unavailable.")

    return " ".join(parts)


app = OpenTelemetryMiddleware(inner_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
