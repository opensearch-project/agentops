#!/usr/bin/env python3
"""
Simple Agent Example - Minimal OpenTelemetry Instrumentation

This is a minimal example showing the essential OpenTelemetry instrumentation
for an AI agent. Use this as a starting point for your own agent applications.
"""

import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


# Set up OpenTelemetry (do this once at application startup)
resource = Resource.create({
    "service.name": "simple-agent",
    "service.version": "1.0.0"
})

trace_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(trace_provider)

tracer = trace.get_tracer(__name__)


def invoke_agent(user_message: str) -> str:
    """
    Simple agent invocation with OpenTelemetry tracing.
    """
    # Create a span for the agent invocation
    with tracer.start_as_current_span("invoke_agent SimpleAgent") as span:
        # Add gen-ai semantic convention attributes
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.agent.id", "simple_agent_001")
        span.set_attribute("gen_ai.agent.name", "Simple Agent")
        span.set_attribute("gen_ai.provider.name", "openai")
        span.set_attribute("gen_ai.request.model", "gpt-4")
        
        # Your agent logic here
        time.sleep(0.5)  # Simulate processing
        response = f"Processed: {user_message}"
        
        # Add response attributes
        span.set_attribute("gen_ai.response.model", "gpt-4-0613")
        span.set_attribute("gen_ai.usage.input_tokens", 50)
        span.set_attribute("gen_ai.usage.output_tokens", 20)
        
        return response


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """
    Simple tool execution with OpenTelemetry tracing.
    """
    # Create a span for the tool execution
    with tracer.start_as_current_span(f"execute_tool {tool_name}") as span:
        # Add gen-ai semantic convention attributes
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", tool_name)
        
        # Your tool logic here
        time.sleep(0.2)  # Simulate tool execution
        result = {"status": "success", "data": "tool result"}
        
        return result


if __name__ == "__main__":
    print("Simple Agent Example")
    print("=" * 40)
    
    # Invoke the agent
    response = invoke_agent("Hello, agent!")
    print(f"Response: {response}")
    
    # Execute a tool
    result = execute_tool("example_tool", {"param": "value"})
    print(f"Tool result: {result}")
    
    # Wait for telemetry export
    time.sleep(2)
    print("\n✓ Telemetry sent to ATLAS stack")
    print("View at: http://localhost:5601")
