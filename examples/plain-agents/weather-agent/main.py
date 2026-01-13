#!/usr/bin/env python3
"""
Weather Agent Example - OpenTelemetry Instrumentation

This example demonstrates how to instrument an AI agent application with OpenTelemetry
to send telemetry data to the ATLAS observability stack using OTLP protocol.

Key features demonstrated:
- OTLP exporter configuration for traces, metrics, and logs
- OTel Gen-AI semantic convention attributes (invoke_agent, execute_tool)
- Custom attributes for agent context
- Structured logging with trace correlation
- Tool execution tracing
- Token usage metrics
"""

import json
import logging
import time
from typing import Dict, Any, List
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.trace import Status, StatusCode


# Configure OpenTelemetry with OTLP exporters
def setup_telemetry(
    service_name: str = "weather-agent",
    service_version: str = "1.0.0",
    otlp_endpoint: str = "http://localhost:4317"
) -> tuple:
    """
    Set up OpenTelemetry with OTLP exporters for traces, metrics, and logs.
    
    Args:
        service_name: Name of the service/agent
        service_version: Version of the service
        otlp_endpoint: OTLP collector endpoint (gRPC)
    
    Returns:
        Tuple of (tracer, meter, logger)
    """
    # Create resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": "development"
    })
    
    # Set up tracing
    trace_provider = TracerProvider(resource=resource)
    otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(__name__)
    
    # Set up metrics
    otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    # Export metrics every 2 seconds for faster demo feedback
    metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter, export_interval_millis=2000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(__name__)
    
    # Set up logging
    logger_provider = LoggerProvider(resource=resource)
    otlp_log_exporter = OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
    set_logger_provider(logger_provider)
    
    # Configure Python logging to use OpenTelemetry
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    
    return tracer, meter, logger


# Simulated weather tool
def get_weather(location: str) -> Dict[str, Any]:
    """
    Simulated weather API call.
    
    Args:
        location: Location to get weather for
    
    Returns:
        Weather data dictionary
    """
    # Simulate API latency
    time.sleep(0.5)
    
    # Return mock weather data
    return {
        "location": location,
        "temperature": "57°F",
        "condition": "rainy",
        "humidity": "85%",
        "wind_speed": "12 mph"
    }


# Simulated LLM call
def call_llm(
    model: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Simulated LLM API call.
    
    Args:
        model: Model name to use
        messages: Chat messages
        tools: Available tools
    
    Returns:
        LLM response with tool call
    """
    # Simulate LLM latency
    time.sleep(1.0)
    
    # Return mock response with tool call
    return {
        "id": "chatcmpl-123456",
        "model": "gpt-4-0613",
        "choices": [{
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": json.dumps({"location": messages[-1]["content"].split()[-1].rstrip("?")})
                    }
                }]
            },
            "finish_reason": "tool_calls"
        }],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 25,
            "total_tokens": 175
        }
    }


class WeatherAgent:
    """
    Example AI agent that answers weather questions using OpenTelemetry instrumentation.
    
    This agent demonstrates:
    - invoke_agent spans for agent invocations
    - execute_tool spans for tool executions
    - Gen-AI semantic convention attributes
    - Custom agent context attributes
    - Structured logging with trace correlation
    """
    
    def __init__(self, tracer, meter, logger):
        self.tracer = tracer
        self.meter = meter
        self.logger = logger
        
        # Agent metadata
        self.agent_id = "asst_weather_001"
        self.agent_name = "Weather Assistant"
        self.agent_description = "Helps users get weather information for any location"
        self.model = "gpt-4"
        
        # Create metrics
        self.token_counter = meter.create_counter(
            name="gen_ai.client.token.usage",
            description="Number of tokens used in LLM operations",
            unit="token"
        )
        
        self.operation_duration = meter.create_histogram(
            name="gen_ai.client.operation.duration",
            description="Duration of agent operations",
            unit="s"
        )
        
        # Available tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name or location"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
    
    def invoke(self, user_message: str, conversation_id: str) -> str:
        """
        Invoke the agent with a user message.
        
        This method creates an invoke_agent span following gen-ai semantic conventions.
        
        Args:
            user_message: User's question
            conversation_id: Conversation/session identifier
        
        Returns:
            Agent's response
        """
        start_time = time.time()
        
        # Create invoke_agent span with gen-ai semantic conventions
        with self.tracer.start_as_current_span(
            f"invoke_agent {self.agent_name}",
            kind=trace.SpanKind.CLIENT
        ) as span:
            try:
                # Set gen-ai semantic convention attributes
                span.set_attribute("gen_ai.operation.name", "invoke_agent")
                span.set_attribute("gen_ai.provider.name", "openai")
                span.set_attribute("gen_ai.agent.id", self.agent_id)
                span.set_attribute("gen_ai.agent.name", self.agent_name)
                span.set_attribute("gen_ai.agent.description", self.agent_description)
                span.set_attribute("gen_ai.conversation.id", conversation_id)
                span.set_attribute("gen_ai.request.model", self.model)
                span.set_attribute("server.address", "api.openai.com")
                span.set_attribute("server.port", 443)
                
                # Custom agent context attributes
                span.set_attribute("agent.tools.count", len(self.tools))
                span.set_attribute("agent.tools.available", json.dumps([t["function"]["name"] for t in self.tools]))
                
                # Structured logging with trace correlation
                self.logger.info(
                    "Agent invoked",
                    extra={
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.agent.id": self.agent_id,
                        "gen_ai.agent.name": self.agent_name,
                        "gen_ai.conversation.id": conversation_id,
                        "user_message": user_message
                    }
                )
                
                # Prepare messages
                messages = [
                    {"role": "system", "content": "You are a helpful weather assistant."},
                    {"role": "user", "content": user_message}
                ]
                
                # Add span event for input
                span.add_event(
                    "gen_ai.client.inference.operation.details",
                    attributes={
                        "gen_ai.operation.name": "chat",
                        "gen_ai.input.messages": json.dumps(messages)
                    }
                )
                
                # Call LLM
                llm_response = call_llm(self.model, messages, self.tools)
                
                # Set response attributes
                span.set_attribute("gen_ai.response.model", llm_response["model"])
                span.set_attribute("gen_ai.response.id", llm_response["id"])
                span.set_attribute("gen_ai.response.finish_reasons", [llm_response["choices"][0]["finish_reason"]])
                span.set_attribute("gen_ai.usage.input_tokens", llm_response["usage"]["prompt_tokens"])
                span.set_attribute("gen_ai.usage.output_tokens", llm_response["usage"]["completion_tokens"])
                
                # Record token usage metrics
                self.token_counter.add(
                    llm_response["usage"]["prompt_tokens"],
                    attributes={
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.provider.name": "openai",
                        "gen_ai.request.model": self.model,
                        "gen_ai.response.model": llm_response["model"],
                        "gen_ai.token.type": "input",
                        "server.address": "api.openai.com"
                    }
                )
                
                self.token_counter.add(
                    llm_response["usage"]["completion_tokens"],
                    attributes={
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.provider.name": "openai",
                        "gen_ai.request.model": self.model,
                        "gen_ai.response.model": llm_response["model"],
                        "gen_ai.token.type": "output",
                        "server.address": "api.openai.com"
                    }
                )
                
                # Add span event for output
                span.add_event(
                    "gen_ai.client.inference.operation.details",
                    attributes={
                        "gen_ai.operation.name": "chat",
                        "gen_ai.output.messages": json.dumps([llm_response["choices"][0]["message"]])
                    }
                )
                
                # Execute tool if requested
                tool_call = llm_response["choices"][0]["message"].get("tool_calls", [None])[0]
                if tool_call:
                    tool_result = self.execute_tool(
                        tool_call["function"]["name"],
                        json.loads(tool_call["function"]["arguments"])
                    )
                    
                    # Generate final response
                    final_response = f"The weather in {tool_result['location']} is {tool_result['condition']} with a temperature of {tool_result['temperature']}."
                else:
                    final_response = "I couldn't determine what you're asking about."
                
                # Log successful completion
                self.logger.info(
                    "Agent invocation completed",
                    extra={
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.agent.id": self.agent_id,
                        "gen_ai.response.id": llm_response["id"],
                        "gen_ai.conversation.id": conversation_id,
                        "response": final_response
                    }
                )
                
                # Record operation duration
                duration = time.time() - start_time
                self.operation_duration.record(
                    duration,
                    attributes={
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.provider.name": "openai",
                        "gen_ai.request.model": self.model,
                        "gen_ai.response.model": llm_response["model"],
                        "server.address": "api.openai.com"
                    }
                )
                
                span.set_status(Status(StatusCode.OK))
                return final_response
                
            except Exception as e:
                # Log error
                self.logger.error(
                    f"Agent invocation failed: {str(e)}",
                    extra={
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.agent.id": self.agent_id,
                        "gen_ai.conversation.id": conversation_id,
                        "error": str(e)
                    }
                )
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with proper instrumentation.
        
        This method creates an execute_tool span following gen-ai semantic conventions.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
        
        Returns:
            Tool execution result
        """
        # Create execute_tool span with gen-ai semantic conventions
        with self.tracer.start_as_current_span(
            f"execute_tool {tool_name}",
            kind=trace.SpanKind.INTERNAL
        ) as span:
            try:
                # Set gen-ai semantic convention attributes
                span.set_attribute("gen_ai.operation.name", "execute_tool")
                span.set_attribute("gen_ai.tool.name", tool_name)
                
                # Find tool description
                tool_def = next((t for t in self.tools if t["function"]["name"] == tool_name), None)
                if tool_def:
                    span.set_attribute("gen_ai.tool.description", tool_def["function"]["description"])
                
                # Custom tool context attributes
                span.set_attribute("tool.arguments", json.dumps(arguments))
                
                # Log tool execution start
                self.logger.info(
                    f"Executing tool: {tool_name}",
                    extra={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": tool_name,
                        "tool.arguments": json.dumps(arguments)
                    }
                )
                
                # Add span event for tool execution start
                span.add_event(
                    "tool_execution_start",
                    attributes={
                        "tool.input": json.dumps(arguments)
                    }
                )
                
                # Execute the actual tool
                if tool_name == "get_weather":
                    result = get_weather(arguments["location"])
                else:
                    raise ValueError(f"Unknown tool: {tool_name}")
                
                # Add span event for tool execution complete
                span.add_event(
                    "tool_execution_complete",
                    attributes={
                        "tool.output": json.dumps(result)
                    }
                )
                
                # Log tool execution completion
                self.logger.info(
                    f"Tool execution completed: {tool_name}",
                    extra={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": tool_name,
                        "tool.result": json.dumps(result)
                    }
                )
                
                span.set_status(Status(StatusCode.OK))
                return result
                
            except Exception as e:
                # Log error
                self.logger.error(
                    f"Tool execution failed: {tool_name} - {str(e)}",
                    extra={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": tool_name,
                        "error": str(e)
                    }
                )
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


def main():
    """
    Main function demonstrating agent usage with OpenTelemetry instrumentation.
    """
    print("Weather Agent Example - OpenTelemetry Instrumentation")
    print("=" * 60)
    print()
    
    # Set up OpenTelemetry
    print("Setting up OpenTelemetry with OTLP exporters...")
    tracer, meter, logger = setup_telemetry(
        service_name="weather-agent",
        service_version="1.0.0",
        otlp_endpoint="http://localhost:4317"
    )
    print("✓ OpenTelemetry configured")
    print()
    
    # Create agent
    print("Creating Weather Agent...")
    agent = WeatherAgent(tracer, meter, logger)
    print(f"✓ Agent created: {agent.agent_name} (ID: {agent.agent_id})")
    print()
    
    # Example conversation
    conversation_id = "conv_example_001"
    user_message = "What's the weather in Paris?"
    
    print(f"User: {user_message}")
    print()
    
    # Invoke agent
    print("Invoking agent...")
    response = agent.invoke(user_message, conversation_id)
    print(f"Agent: {response}")
    print()
    
    # Give time for telemetry to be exported
    # Metrics export every 2 seconds, so wait at least 3 seconds
    print("Waiting for telemetry export...")
    time.sleep(3)
    print("✓ Telemetry exported to ATLAS stack")
    print()
    
    print("=" * 60)
    print("Example complete!")
    print()
    print("View telemetry data:")
    print("  - OpenSearch Dashboards: http://localhost:5601")
    print("  - Prometheus: http://localhost:9090")
    print()


if __name__ == "__main__":
    main()
