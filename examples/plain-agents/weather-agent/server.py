#!/usr/bin/env python3
"""
Weather Agent API Server

FastAPI server that exposes the weather agent through REST API endpoints.
Includes OpenTelemetry instrumentation for the API layer.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from main import WeatherAgent, setup_telemetry


# Request/Response models
class InvokeRequest(BaseModel):
    """Request model for agent invocation"""
    message: str = Field(..., description="User message to send to the agent")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for tracking")


class InvokeResponse(BaseModel):
    """Response model for agent invocation"""
    response: str = Field(..., description="Agent's response")
    conversation_id: str = Field(..., description="Conversation ID used for this invocation")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service health status")
    agent_id: str = Field(..., description="Agent identifier")
    agent_name: str = Field(..., description="Agent name")


# Global agent instance
agent: Optional[WeatherAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Sets up OpenTelemetry and creates the agent on startup.
    """
    import os

    global agent

    # Get OTLP endpoint from environment or use default
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    # Setup OpenTelemetry
    tracer, meter, logger = setup_telemetry(
        service_name="weather-agent-api",
        service_version="1.0.0",
        otlp_endpoint=otlp_endpoint,
    )

    # Create agent
    agent = WeatherAgent(tracer, meter, logger)

    logger.info(
        "Weather Agent API server started", extra={"otlp_endpoint": otlp_endpoint}
    )

    yield

    # Cleanup (if needed)
    logger.info("Weather Agent API server shutting down")


# Create FastAPI app
app = FastAPI(
    title="Weather Agent API",
    description="REST API for the Weather Agent with OpenTelemetry instrumentation",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Weather Agent API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "invoke": "/invoke (POST)"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    return HealthResponse(
        status="healthy",
        agent_id=agent.agent_id,
        agent_name=agent.agent_name
    )


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest):
    """
    Invoke the weather agent with a user message.
    
    Args:
        request: InvokeRequest with message and optional conversation_id
    
    Returns:
        InvokeResponse with agent's response and conversation_id
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    
    try:
        # Invoke the agent
        response = agent.invoke(request.message, conversation_id)
        
        return InvokeResponse(
            response=response,
            conversation_id=conversation_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent invocation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
