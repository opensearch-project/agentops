#!/usr/bin/env python3
"""
MCP Server - Provides low-level tools via MCP protocol.
Sub-agents call this server to execute actual tool logic.
"""

import os
import random
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.propagate import extract
from pydantic import BaseModel
from typing import Optional

MCP_PROTOCOL_VERSION = "2025-06-18"

# Available tools - leaf-level APIs that sub-agents call
TOOLS = {
    "fetch_weather_api": {
        "description": "Fetch weather data from external weather API",
        "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}
    },
    "fetch_events_api": {
        "description": "Fetch events data from external events API",
        "parameters": {"type": "object", "properties": {"destination": {"type": "string"}}, "required": ["destination"]}
    }
}


def setup_telemetry():
    resource = Resource.create({"service.name": "mcp-server", "service.version": "1.0.0"})
    provider = TracerProvider(resource=resource)
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("mcp-server")


tracer = setup_telemetry()
inner_app = FastAPI(title="MCP Server", version="1.0.0")


class ToolCallRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str = "tools/call"
    id: Optional[str] = None
    params: dict


@inner_app.get("/health")
async def health():
    return {"status": "healthy", "protocol_version": MCP_PROTOCOL_VERSION, "tools": list(TOOLS.keys())}


@inner_app.post("/mcp")
async def handle_mcp(request: Request, body: ToolCallRequest):
    """Handle MCP JSON-RPC requests."""
    ctx = extract(request.headers)
    session_id = request.headers.get("mcp-session-id", uuid4().hex)
    request_id = body.id or str(uuid4().hex[:8])
    tool_name = body.params.get("name", "unknown")
    arguments = body.params.get("arguments", {})

    # MCP SERVER span (protocol layer)
    with tracer.start_as_current_span(
        f"tools/call {tool_name}",
        context=ctx,
        kind=SpanKind.SERVER,
        attributes={
            "mcp.method.name": "tools/call",
            "mcp.session.id": session_id,
            "mcp.protocol.version": MCP_PROTOCOL_VERSION,
            "jsonrpc.request.id": request_id,
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "network.transport": "tcp",
            "network.protocol.name": "http",
        },
    ) as mcp_span:
        # Tool execution span (application layer)
        with tracer.start_as_current_span(
            f"tool_call {tool_name}",
            kind=SpanKind.INTERNAL,
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_name,
                "gen_ai.tool.call.id": f"call_{uuid4().hex[:8]}",
            },
        ) as tool_span:
            try:
                result = execute_tool(tool_name, arguments)
                return {"jsonrpc": "2.0", "id": request_id, "result": result}
            except Exception as e:
                tool_span.set_status(Status(StatusCode.ERROR, str(e)))
                mcp_span.set_status(Status(StatusCode.ERROR, str(e)))
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(e)}}


def execute_tool(name: str, args: dict) -> dict:
    """Execute tool and return result."""
    time.sleep(random.uniform(0.05, 0.15))  # Simulate API latency

    if name == "fetch_weather_api":
        location = args.get("location", "Unknown")
        temp = random.randint(50, 90)
        condition = random.choice(["sunny", "cloudy", "rainy", "partly cloudy"])
        return {
            "location": location,
            "temperature": f"{temp}°F",
            "condition": condition,
            "humidity": f"{random.randint(30, 80)}%",
            "wind_speed": f"{random.randint(0, 25)} mph",
        }

    elif name == "fetch_events_api":
        destination = args.get("destination", "Unknown")
        events = [
            {"name": f"{destination} Food Festival", "date": "2025-03-15", "type": "food"},
            {"name": f"{destination} Art Walk", "date": "2025-03-20", "type": "art"},
            {"name": f"Live Music at {destination} Park", "date": "2025-03-22", "type": "music"},
        ]
        return {"destination": destination, "events": random.sample(events, k=random.randint(1, 3))}

    else:
        raise ValueError(f"Unknown tool: {name}")


app = OpenTelemetryMiddleware(inner_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
