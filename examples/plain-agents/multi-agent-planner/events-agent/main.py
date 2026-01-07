#!/usr/bin/env python3
"""
Events Agent - Fetches local events for a destination.
Supports fault injection for testing observability.
"""

import os
import random
import time
from datetime import datetime
from typing import Optional

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
from pydantic import BaseModel, Field


AGENT_ID = "events-agent-001"
AGENT_NAME = "Events Agent"

SAMPLE_EVENTS = {
    "paris": [
        {"name": "Louvre Late Night", "type": "museum", "venue": "Louvre Museum"},
        {"name": "Seine River Cruise", "type": "tour", "venue": "Port de la Bourdonnais"},
        {"name": "Jazz at Le Caveau", "type": "music", "venue": "Le Caveau de la Huchette"},
    ],
    "london": [
        {"name": "West End Show", "type": "theater", "venue": "Various"},
        {"name": "Borough Market Food Tour", "type": "food", "venue": "Borough Market"},
        {"name": "British Museum Exhibition", "type": "museum", "venue": "British Museum"},
    ],
    "tokyo": [
        {"name": "Shibuya Night Walk", "type": "tour", "venue": "Shibuya"},
        {"name": "Tsukiji Outer Market", "type": "food", "venue": "Tsukiji"},
        {"name": "Robot Restaurant Show", "type": "entertainment", "venue": "Shinjuku"},
    ],
    "berlin": [
        {"name": "Berlin Wall Tour", "type": "tour", "venue": "East Side Gallery"},
        {"name": "Techno Night", "type": "music", "venue": "Berghain"},
        {"name": "Museum Island Visit", "type": "museum", "venue": "Museum Island"},
    ],
    "new york": [
        {"name": "Broadway Show", "type": "theater", "venue": "Times Square"},
        {"name": "Central Park Walk", "type": "tour", "venue": "Central Park"},
        {"name": "Jazz at Blue Note", "type": "music", "venue": "Blue Note"},
    ],
    "sydney": [
        {"name": "Opera House Tour", "type": "tour", "venue": "Sydney Opera House"},
        {"name": "Bondi Beach Day", "type": "outdoor", "venue": "Bondi Beach"},
        {"name": "Harbour Bridge Climb", "type": "adventure", "venue": "Sydney Harbour"},
    ],
    "mumbai": [
        {"name": "Bollywood Studio Tour", "type": "tour", "venue": "Film City"},
        {"name": "Street Food Walk", "type": "food", "venue": "Chowpatty Beach"},
        {"name": "Gateway of India Visit", "type": "landmark", "venue": "Gateway of India"},
    ],
    "seattle": [
        {"name": "Pike Place Market Tour", "type": "food", "venue": "Pike Place"},
        {"name": "Space Needle Visit", "type": "landmark", "venue": "Space Needle"},
        {"name": "Coffee Crawl", "type": "food", "venue": "Capitol Hill"},
    ],
}


class FaultConfig(BaseModel):
    type: str = Field(..., description="Fault type: timeout, error, rate_limited, high_latency, wrong_city, empty")
    delay_ms: int = Field(0, description="Delay in milliseconds")
    probability: float = Field(1.0, description="Probability of fault (0.0-1.0)")
    wrong_city: Optional[str] = Field(None, description="Return events from this city instead")


class EventsRequest(BaseModel):
    destination: str
    date: Optional[str] = None
    fault: Optional[FaultConfig] = None


class Event(BaseModel):
    name: str
    type: str
    venue: str
    date: str


class EventsResponse(BaseModel):
    destination: str
    events: list[Event]
    agent_id: str


class ErrorResponse(BaseModel):
    error: dict
    destination: str
    agent_id: str


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
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
        export_interval_millis=10000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    return trace.get_tracer(service_name), metrics.get_meter(service_name)


otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
tracer, meter = setup_telemetry("events-agent", otlp_endpoint)

inner_app = FastAPI(title="Events Agent", version="1.0.0")


def should_inject_fault(fault: Optional[FaultConfig]) -> bool:
    if not fault:
        return False
    return random.random() < fault.probability


@inner_app.get("/health")
async def health():
    return {"status": "healthy", "agent_id": AGENT_ID, "agent_name": AGENT_NAME}


@inner_app.post("/events")
async def get_events(request: EventsRequest):
    with tracer.start_as_current_span(
        "invoke_agent",
        kind=SpanKind.INTERNAL,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.id": AGENT_ID,
            "gen_ai.agent.name": AGENT_NAME,
        },
    ) as span:
        destination = request.destination.lower()
        date = request.date or datetime.now().strftime("%Y-%m-%d")
        fault = request.fault

        # Check for fault injection
        if should_inject_fault(fault):
            span.set_attribute("fault.injected", fault.type)

            if fault.type == "high_latency":
                delay = fault.delay_ms / 1000.0
                span.set_attribute("fault.delay_ms", fault.delay_ms)
                time.sleep(delay)

            elif fault.type == "timeout":
                span.set_status(Status(StatusCode.ERROR, "Tool execution timed out"))
                time.sleep(30)  # Simulate timeout
                return ErrorResponse(
                    error={"type": "timeout", "message": "Events lookup timed out"},
                    destination=request.destination,
                    agent_id=AGENT_ID,
                )

            elif fault.type == "error":
                span.set_status(Status(StatusCode.ERROR, "Events API error"))
                return ErrorResponse(
                    error={"type": "tool_error", "message": "Events API returned an error"},
                    destination=request.destination,
                    agent_id=AGENT_ID,
                )

            elif fault.type == "rate_limited":
                span.set_status(Status(StatusCode.ERROR, "Rate limited"))
                return ErrorResponse(
                    error={"type": "rate_limited", "message": "Events API rate limit exceeded"},
                    destination=request.destination,
                    agent_id=AGENT_ID,
                )

            elif fault.type == "wrong_city":
                # Return events from a different city
                wrong = fault.wrong_city or random.choice([c for c in SAMPLE_EVENTS.keys() if c != destination])
                span.set_attribute("fault.wrong_city", wrong)
                events_data = SAMPLE_EVENTS.get(wrong, SAMPLE_EVENTS["paris"])
                selected = random.sample(events_data, min(len(events_data), 2))
                events = [Event(name=e["name"], type=e["type"], venue=e["venue"], date=date) for e in selected]
                return EventsResponse(destination=request.destination, events=events, agent_id=AGENT_ID)

            elif fault.type == "empty":
                # Return no events
                return EventsResponse(destination=request.destination, events=[], agent_id=AGENT_ID)

        # Normal execution
        with tracer.start_as_current_span(
            "execute_tool",
            kind=SpanKind.INTERNAL,
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "lookup_events",
                "gen_ai.request.model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "gen_ai.system": "aws.bedrock",
                "destination": destination,
            },
        ):
            events_data = SAMPLE_EVENTS.get(destination, SAMPLE_EVENTS["paris"])
            selected = random.sample(events_data, min(len(events_data), random.randint(1, 3)))
            events = [Event(name=e["name"], type=e["type"], venue=e["venue"], date=date) for e in selected]

        span.set_attribute("events.count", len(events))
        return EventsResponse(destination=request.destination, events=events, agent_id=AGENT_ID)


app = OpenTelemetryMiddleware(inner_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
