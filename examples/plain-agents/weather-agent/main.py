#!/usr/bin/env python3
"""
Weather Agent Example - OpenTelemetry Instrumentation

This example demonstrates how to instrument an AI agent application with OpenTelemetry
to send telemetry data to the AgentOps observability stack using OTLP protocol.

Key features demonstrated:
- OTLP exporter configuration for traces, metrics, and logs
- OTel Gen-AI semantic convention attributes (invoke_agent, execute_tool)
- Structured content capture (system instructions, messages, tool calls)
- Token usage metrics
- Structured logging with trace correlation

References:
- OpenTelemetry GenAI Semantic Conventions:
  https://github.com/open-telemetry/semantic-conventions/tree/e126ea9105b15912ccd80deab98929025189b696/docs/gen-ai
- Agent spans: gen-ai-agent-spans.md
- Tool execution: gen-ai-spans.md#execute-tool-span
- Input/output message schemas: gen-ai-input-messages.json, gen-ai-output-messages.json
- System instructions schema: gen-ai-system-instructions.json
"""

from dataclasses import dataclass
import json
import logging
import random
import time
from typing import Dict, Any, List, Optional
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


# Fault injection exceptions
class AgentError(Exception):
    """Base exception for agent errors."""
    def __init__(self, message: str, error_type: str, status_code: int = 500):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


class ToolTimeoutError(AgentError):
    def __init__(self, message: str):
        super().__init__(message, "timeout", 504)


class ToolExecutionError(AgentError):
    def __init__(self, message: str):
        super().__init__(message, "tool_error", 502)


class RateLimitError(AgentError):
    def __init__(self, message: str):
        super().__init__(message, "rate_limit_exceeded", 429)


@dataclass
class FaultConfig:
    """Configuration for fault injection."""
    type: str
    delay_ms: int = 0
    probability: float = 1.0
    tool: Optional[str] = None


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


def get_forecast(location: str, days: int = 3) -> Dict[str, Any]:
    """Get weather forecast for a location."""
    time.sleep(0.5)
    forecasts = []
    conditions = ["sunny", "cloudy", "rainy", "partly cloudy"]
    for i in range(days):
        forecasts.append({
            "day": i + 1,
            "high": f"{65 + i * 3}°F",
            "low": f"{45 + i * 2}°F",
            "condition": conditions[i % len(conditions)]
        })
    return {"location": location, "forecast": forecasts}


def get_historical_weather(location: str, date: str) -> Dict[str, Any]:
    """Get historical weather for a location and date."""
    time.sleep(0.5)
    return {
        "location": location,
        "date": date,
        "high": "62°F",
        "low": "48°F",
        "condition": "partly cloudy",
        "precipitation": "0.1 in"
    }


# Simulated LLM call
def call_llm(
    model: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Simulated LLM API call that selects appropriate tool based on query.
    """
    time.sleep(1.0)
    
    user_message = messages[-1]["content"].lower()
    location = messages[-1]["content"].split()[-1].rstrip("?")
    
    # Determine which tool to call based on query
    if any(word in user_message for word in ["forecast", "next", "tomorrow", "week", "upcoming"]):
        tool_name = "get_forecast"
        arguments = {"location": location, "days": 3}
    elif any(word in user_message for word in ["yesterday", "last", "historical", "was", "were", "past"]):
        tool_name = "get_historical_weather"
        arguments = {"location": location, "date": "2026-01-25"}
    else:
        tool_name = "get_current_weather"
        arguments = {"location": location}
    
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
                        "name": tool_name,
                        "arguments": json.dumps(arguments)
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
                    "name": "get_current_weather",
                    "description": "Get current weather conditions for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name or location"}
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_forecast",
                    "description": "Get weather forecast for the next several days",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name or location"},
                            "days": {"type": "integer", "description": "Number of days (1-7)", "default": 3}
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_historical_weather",
                    "description": "Get historical weather data for a past date",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name or location"},
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
                        },
                        "required": ["location", "date"]
                    }
                }
            }
        ]
    
    def _should_inject_fault(self, fault: Optional[FaultConfig]) -> bool:
        """Check if fault should be injected based on probability."""
        if fault is None:
            return False
        return random.random() < fault.probability

    def invoke(self, user_message: str, conversation_id: str, fault: Optional[FaultConfig] = None) -> str:
        """
        Invoke the agent with a user message.
        
        This method creates an invoke_agent span following gen-ai semantic conventions.
        
        Args:
            user_message: User's question
            conversation_id: Conversation/session identifier
            fault: Optional fault injection configuration
        
        Returns:
            Agent's response
        """
        start_time = time.time()
        
        # System instructions (separate from chat history per spec)
        system_instructions = [
            {"type": "text", "content": "You are a helpful weather assistant."}
        ]
        
        # Create invoke_agent span with gen-ai semantic conventions
        with self.tracer.start_as_current_span(
            f"invoke_agent {self.agent_name}",
            kind=trace.SpanKind.CLIENT
        ) as span:
            try:
                # Required attributes
                span.set_attribute("gen_ai.operation.name", "invoke_agent")
                span.set_attribute("gen_ai.provider.name", "openai")
                
                # Conditionally required attributes
                span.set_attribute("gen_ai.agent.id", self.agent_id)
                span.set_attribute("gen_ai.agent.name", self.agent_name)
                span.set_attribute("gen_ai.agent.description", self.agent_description)
                span.set_attribute("gen_ai.conversation.id", conversation_id)
                span.set_attribute("gen_ai.request.model", self.model)
                span.set_attribute("gen_ai.output.type", "text")
                
                # Recommended attributes
                span.set_attribute("gen_ai.request.temperature", 0.7)
                span.set_attribute("gen_ai.request.max_tokens", 1024)
                span.set_attribute("server.address", "api.openai.com")
                span.set_attribute("server.port", 443)
                
                # Opt-in attributes (content capture)
                # See schema definitions: https://github.com/open-telemetry/semantic-conventions/tree/e126ea9105b15912ccd80deab98929025189b696/docs/gen-ai
                span.set_attribute("gen_ai.system_instructions", json.dumps(system_instructions))
                span.set_attribute("gen_ai.tool.definitions", json.dumps(self.tools))
                
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
                
                # Prepare input messages following gen-ai-input-messages.json schema
                # See: https://github.com/open-telemetry/semantic-conventions/tree/e126ea9105b15912ccd80deab98929025189b696/docs/gen-ai
                input_messages = [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "content": user_message}]
                    }
                ]
                
                # Opt-in: Record input messages as attribute
                span.set_attribute("gen_ai.input.messages", json.dumps(input_messages))
                
                # Check for pre-LLM faults
                if self._should_inject_fault(fault):
                    if fault.delay_ms:
                        time.sleep(fault.delay_ms / 1000)
                    
                    if fault.type == "rate_limited":
                        span.set_status(Status(StatusCode.ERROR, "Rate limit exceeded"))
                        span.set_attribute("error.type", "rate_limit_exceeded")
                        raise RateLimitError("Rate limit exceeded. Retry after 60 seconds.")
                    
                    if fault.type == "hallucination":
                        # Skip tool call, return fabricated response
                        hallucinated_response = f"The weather is 22°C and sunny with light winds."
                        span.set_attribute("gen_ai.response.model", self.model)
                        span.set_attribute("gen_ai.response.id", f"chatcmpl-hallucinated-{conversation_id[:8]}")
                        span.set_attribute("gen_ai.response.finish_reasons", ["stop"])
                        span.set_attribute("gen_ai.usage.input_tokens", 50)
                        span.set_attribute("gen_ai.usage.output_tokens", 20)
                        output_messages = [{"role": "assistant", "parts": [{"type": "text", "content": hallucinated_response}], "finish_reason": "stop"}]
                        span.set_attribute("gen_ai.output.messages", json.dumps(output_messages))
                        span.set_status(Status(StatusCode.OK))
                        return hallucinated_response
                
                # Prepare messages for LLM call (internal format)
                messages = [
                    {"role": "system", "content": system_instructions[0]["content"]},
                    {"role": "user", "content": user_message}
                ]
                
                # Call LLM
                llm_response = call_llm(self.model, messages, self.tools)
                
                # Check for token_limit_exceeded fault (simulates truncated response)
                if self._should_inject_fault(fault) and fault.type == "token_limit_exceeded":
                    span.set_attribute("gen_ai.response.model", llm_response["model"])
                    span.set_attribute("gen_ai.response.id", llm_response["id"])
                    span.set_attribute("gen_ai.response.finish_reasons", ["length"])
                    span.set_attribute("gen_ai.usage.input_tokens", llm_response["usage"]["prompt_tokens"])
                    span.set_attribute("gen_ai.usage.output_tokens", 1024)  # Hit limit
                    truncated_response = "The weather in the requested location is currently showing temperatures around—"
                    output_messages = [{"role": "assistant", "parts": [{"type": "text", "content": truncated_response}], "finish_reason": "length"}]
                    span.set_attribute("gen_ai.output.messages", json.dumps(output_messages))
                    span.set_status(Status(StatusCode.OK))
                    return truncated_response
                
                # Recommended response attributes
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
                
                # Execute tool if requested
                tool_call = llm_response["choices"][0]["message"].get("tool_calls", [None])[0]
                tool_call_id = tool_call["id"] if tool_call else None
                
                if tool_call:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    
                    # wrong_tool fault: swap the tool being called
                    if self._should_inject_fault(fault) and fault.type == "wrong_tool":
                        wrong_tools = {"get_current_weather": "get_forecast", "get_forecast": "get_historical_weather", "get_historical_weather": "get_current_weather"}
                        tool_name = wrong_tools.get(tool_name, tool_name)
                        # Adjust args for the wrong tool
                        if tool_name == "get_historical_weather":
                            tool_args["date"] = "2026-01-25"
                    
                    # Pass fault config to execute_tool for tool-specific faults
                    tool_result = self.execute_tool(tool_name, tool_args, tool_call_id, fault)
                    
                    # Generate final response based on tool result
                    if "temperature" in tool_result:
                        final_response = f"The weather in {tool_result['location']} is {tool_result['condition']} with a temperature of {tool_result['temperature']}."
                    elif "forecast" in tool_result:
                        days = tool_result["forecast"]
                        final_response = f"Forecast for {tool_result['location']}: Day 1: {days[0]['condition']}, high {days[0]['high']}."
                    elif "date" in tool_result:
                        final_response = f"On {tool_result['date']} in {tool_result['location']}: {tool_result['condition']}, high {tool_result['high']}."
                    else:
                        final_response = f"Weather data for {tool_result.get('location', 'unknown')}: {tool_result}"
                else:
                    final_response = "I couldn't determine what you're asking about."
                
                # Opt-in: Record output messages following gen-ai-output-messages.json schema
                # See: https://github.com/open-telemetry/semantic-conventions/tree/e126ea9105b15912ccd80deab98929025189b696/docs/gen-ai
                output_messages = [
                    {
                        "role": "assistant",
                        "parts": [{"type": "text", "content": final_response}],
                        "finish_reason": "stop"
                    }
                ]
                span.set_attribute("gen_ai.output.messages", json.dumps(output_messages))
                
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
                span.set_attribute("error.type", type(e).__name__)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], tool_call_id: str = None, fault: Optional[FaultConfig] = None) -> Dict[str, Any]:
        """
        Execute a tool with proper instrumentation.
        
        This method creates an execute_tool span following gen-ai semantic conventions.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            tool_call_id: The tool call identifier from the LLM response
            fault: Optional fault injection configuration
        
        Returns:
            Tool execution result
        """
        # Create execute_tool span with gen-ai semantic conventions
        with self.tracer.start_as_current_span(
            f"execute_tool {tool_name}",
            kind=trace.SpanKind.INTERNAL
        ) as span:
            try:
                # Required attribute
                span.set_attribute("gen_ai.operation.name", "execute_tool")
                
                # Recommended attributes
                span.set_attribute("gen_ai.tool.name", tool_name)
                span.set_attribute("gen_ai.tool.type", "function")
                if tool_call_id:
                    span.set_attribute("gen_ai.tool.call.id", tool_call_id)
                
                # Find tool description
                tool_def = next((t for t in self.tools if t["function"]["name"] == tool_name), None)
                if tool_def:
                    span.set_attribute("gen_ai.tool.description", tool_def["function"]["description"])
                
                # Opt-in: Record tool call arguments
                span.set_attribute("gen_ai.tool.call.arguments", json.dumps(arguments))
                
                # Check for tool-specific faults
                if self._should_inject_fault(fault) and fault.type in ("tool_timeout", "tool_error", "high_latency"):
                    target_tool = fault.tool or tool_name
                    if target_tool == tool_name:
                        if fault.delay_ms:
                            time.sleep(fault.delay_ms / 1000)
                        
                        if fault.type == "tool_timeout":
                            span.set_status(Status(StatusCode.ERROR, "Tool execution timed out"))
                            span.set_attribute("error.type", "timeout")
                            raise ToolTimeoutError(f"Tool '{tool_name}' timed out after 30000ms")
                        
                        if fault.type == "tool_error":
                            span.set_status(Status(StatusCode.ERROR, "Tool execution failed"))
                            span.set_attribute("error.type", "tool_error")
                            raise ToolExecutionError(f"Tool '{tool_name}' failed: External API returned 503")
                        
                        # high_latency: delay already applied, continue normally
                
                # Log tool execution start
                self.logger.info(
                    f"Executing tool: {tool_name}",
                    extra={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": tool_name,
                        "gen_ai.tool.call.id": tool_call_id,
                        "gen_ai.tool.call.arguments": json.dumps(arguments)
                    }
                )
                
                # Execute the actual tool
                if tool_name == "get_current_weather":
                    result = get_weather(arguments["location"])
                elif tool_name == "get_forecast":
                    result = get_forecast(arguments["location"], arguments.get("days", 3))
                elif tool_name == "get_historical_weather":
                    result = get_historical_weather(arguments["location"], arguments.get("date", "2026-01-01"))
                # Legacy support
                elif tool_name == "get_weather":
                    result = get_weather(arguments["location"])
                else:
                    raise ValueError(f"Unknown tool: {tool_name}")
                
                # Opt-in: Record tool call result
                span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
                
                # Log tool execution completion
                self.logger.info(
                    f"Tool execution completed: {tool_name}",
                    extra={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": tool_name,
                        "gen_ai.tool.call.id": tool_call_id,
                        "gen_ai.tool.call.result": json.dumps(result)
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
                span.set_attribute("error.type", type(e).__name__)
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
    print("✓ Telemetry exported to AgentOps stack")
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
