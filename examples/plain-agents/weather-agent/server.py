#!/usr/bin/env python3
"""
Weather Agent API Server

FastAPI server that exposes the weather agent through REST API endpoints.
Includes OpenTelemetry instrumentation for trace context propagation.
"""

import json
import os
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from opentelemetry import trace as trace_api
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

from main import WeatherAgent, setup_telemetry, FaultConfig, AgentError, SYSTEMS


# Request/Response models
class FaultRequest(BaseModel):
    type: str
    delay_ms: int = 0
    probability: float = 1.0
    tool: Optional[str] = None


class InvokeRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    fault: Optional[FaultRequest] = None


class InvokeResponse(BaseModel):
    response: str
    conversation_id: str


class HealthResponse(BaseModel):
    status: str
    agent_id: str
    agent_name: str


# Setup telemetry BEFORE creating app
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
tracer, meter, logger = setup_telemetry(
    service_name="weather-agent",
    service_version="1.0.0",
    otlp_endpoint=otlp_endpoint,
)

# Create agent
agent = WeatherAgent(tracer, meter, logger)

# Create inner FastAPI app
inner_app = FastAPI(title="Weather Agent API", version="1.0.0")

logger.info("Weather Agent API server started", extra={"otlp_endpoint": otlp_endpoint})


@inner_app.get("/")
async def root():
    return {"name": "Weather Agent API", "version": "1.0.0"}


@inner_app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy", agent_id=agent.agent_id, agent_name=agent.agent_name)


@inner_app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest):
    conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    
    fault_config = None
    if request.fault:
        fault_config = FaultConfig(
            type=request.fault.type,
            delay_ms=request.fault.delay_ms,
            probability=request.fault.probability,
            tool=request.fault.tool
        )
    
    # Promote gen_ai attributes to the root HTTP span so the UI can read them
    root_span = trace_api.get_current_span()
    root_span.set_attribute("gen_ai.system", agent.model and SYSTEMS.get(agent.model, "openai") or "openai")
    root_span.set_attribute("gen_ai.agent.name", agent.agent_name)
    root_span.set_attribute("gen_ai.request.model", agent.model)
    root_span.set_attribute("gen_ai.operation.name", "invoke_agent")
    root_span.set_attribute("gen_ai.input.messages", json.dumps(
        [{"role": "user", "parts": [{"type": "text", "content": request.message}]}]
    ))
    
    try:
        response = agent.invoke(request.message, conversation_id, fault_config)
        root_span.set_attribute("gen_ai.output.messages", json.dumps(
            [{"role": "assistant", "parts": [{"type": "text", "content": response}]}]
        ))
        return InvokeResponse(response=response, conversation_id=conversation_id)
    except AgentError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"response": None, "error": {"type": e.error_type, "message": str(e)}, "conversation_id": conversation_id}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent invocation failed: {str(e)}")


# Wrap with ASGI middleware for trace context propagation
app = OpenTelemetryMiddleware(inner_app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
