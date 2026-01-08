"""
Configurable Agent with OpenTelemetry instrumentation.

This module provides the ConfigurableAgent class that accepts pluggable
LLM and tool providers via dependency injection. The agent uses the same
instrumentation patterns as the weather_agent.py example to ensure canary
validation accurately reflects production behavior.
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter
)
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter
)
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter
)
from opentelemetry.trace import Status, StatusCode

from .providers import LLMProvider, ToolProvider
from .exceptions import ChildAgentNotFoundError


class ConfigurableAgent:
    """
    Agent that accepts pluggable LLM and tool providers.

    This is the same agent structure as WeatherAgent from weather_agent.py,
    but with dependency injection for providers. This allows:
    1. weather_agent.py to use it with hardcoded providers
    2. Canary system to use it with mock/real providers

    Uses the same instrumentation patterns as weather_agent.py to ensure
    canary validation accurately reflects production behavior.

    The agent initializes its own OpenTelemetry exporters, just like a
    production agent would.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_provider: ToolProvider,
        agent_id: str = "canary_agent_001",
        agent_name: str = "Canary Agent",
        otlp_endpoint: str = "http://localhost:4317",
        span_kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        child_agents: Optional[Dict[str, "ConfigurableAgent"]] = None,
    ):
        """
        Initialize configurable agent with providers.

        Args:
            llm_provider: LLM provider implementation (mock or real)
            tool_provider: Tool provider implementation (mock or real)
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            otlp_endpoint: OTLP collector endpoint
            span_kind: SpanKind for this agent's invoke_agent span
                      (INTERNAL for in-process, CLIENT for remote-like)
            child_agents: Dictionary mapping child agent names to agent instances
        """
        self.llm_provider = llm_provider
        self.tool_provider = tool_provider
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.model = "gpt-4"
        self.otlp_endpoint = otlp_endpoint
        self.span_kind = span_kind
        self.child_agents = child_agents or {}

        # Initialize OpenTelemetry (same as weather_agent.py)
        self.tracer, self.meter, self.logger = self._setup_telemetry(
            service_name=agent_name,
            otlp_endpoint=otlp_endpoint
        )

        # Create metrics (same as weather_agent.py)
        self.token_counter = self.meter.create_counter(
            name="gen_ai.client.token.usage",
            description="Number of tokens used in LLM operations",
            unit="token"
        )

        self.operation_duration = self.meter.create_histogram(
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

    def _setup_telemetry(
        self,
        service_name: str,
        otlp_endpoint: str
    ) -> tuple:
        """
        Set up OpenTelemetry with OTLP exporters.

        This mirrors the setup_telemetry() function from weather_agent.py.

        Args:
            service_name: Name of the service/agent
            otlp_endpoint: OTLP collector endpoint (gRPC)

        Returns:
            Tuple of (tracer, meter, logger)
        """
        # Create resource with service information
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": "development"
        })

        # Set up tracing
        trace_provider = TracerProvider(resource=resource)
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True
        )
        trace_provider.add_span_processor(
            BatchSpanProcessor(otlp_trace_exporter)
        )
        trace.set_tracer_provider(trace_provider)
        tracer = trace.get_tracer(__name__)

        # Set up metrics
        otlp_metric_exporter = OTLPMetricExporter(
            endpoint=otlp_endpoint,
            insecure=True
        )
        # Export metrics every 2 seconds for faster demo feedback
        metric_reader = PeriodicExportingMetricReader(
            otlp_metric_exporter,
            export_interval_millis=2000
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(meter_provider)
        meter = metrics.get_meter(__name__)

        # Set up logging
        logger_provider = LoggerProvider(resource=resource)
        otlp_log_exporter = OTLPLogExporter(
            endpoint=otlp_endpoint,
            insecure=True
        )
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(otlp_log_exporter)
        )
        set_logger_provider(logger_provider)

        # Configure Python logging to use OpenTelemetry
        handler = LoggingHandler(
            level=logging.INFO,
            logger_provider=logger_provider
        )
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        logger = logging.getLogger(__name__)

        return tracer, meter, logger

    def invoke(self, user_message: str, conversation_id: str) -> str:
        """
        Invoke the agent with a user message.

        This method creates an invoke_agent span following gen-ai semantic
        conventions. Implementation mirrors weather_agent.py
        WeatherAgent.invoke() exactly.

        Args:
            user_message: User's question
            conversation_id: Conversation/session identifier

        Returns:
            Agent's response
        """
        start_time = time.time()

        # Create invoke_agent span with gen-ai semantic conventions
        with self.tracer.start_as_current_span(
            f"invoke_agent {self.agent_name}", kind=self.span_kind
        ) as span:
            try:
                # Set gen-ai semantic convention attributes
                span.set_attribute("gen_ai.operation.name", "invoke_agent")
                span.set_attribute(
                    "gen_ai.provider.name",
                    self.llm_provider.provider_name
                )
                span.set_attribute("gen_ai.agent.id", self.agent_id)
                span.set_attribute("gen_ai.agent.name", self.agent_name)
                span.set_attribute(
                    "gen_ai.agent.description",
                    "Helps users get weather information for any location"
                )
                span.set_attribute(
                    "gen_ai.conversation.id",
                    conversation_id
                )
                span.set_attribute("gen_ai.request.model", self.model)
                span.set_attribute("server.address", "api.openai.com")
                span.set_attribute("server.port", 443)

                # Custom agent context attributes
                span.set_attribute("agent.tools.count", len(self.tools))
                span.set_attribute(
                    "agent.tools.available",
                    json.dumps([t["function"]["name"] for t in self.tools])
                )

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
                    {
                        "role": "system",
                        "content": "You are a helpful weather assistant."
                    },
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

                # Call LLM (using injected provider instead of call_llm())
                llm_response = self.llm_provider.call(
                    self.model,
                    messages,
                    self.tools
                )

                # Set response attributes
                span.set_attribute(
                    "gen_ai.response.model",
                    llm_response["model"]
                )
                span.set_attribute("gen_ai.response.id", llm_response["id"])
                span.set_attribute(
                    "gen_ai.response.finish_reasons",
                    [llm_response["choices"][0]["finish_reason"]]
                )
                span.set_attribute(
                    "gen_ai.usage.input_tokens",
                    llm_response["usage"]["prompt_tokens"]
                )
                span.set_attribute(
                    "gen_ai.usage.output_tokens",
                    llm_response["usage"]["completion_tokens"]
                )

                # Record token usage metrics
                self.token_counter.add(
                    llm_response["usage"]["prompt_tokens"],
                    attributes={
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.provider.name": self.llm_provider.provider_name,
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
                        "gen_ai.provider.name": self.llm_provider.provider_name,
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
                        "gen_ai.output.messages": json.dumps(
                            [llm_response["choices"][0]["message"]]
                        )
                    }
                )

                # Execute tool if requested
                tool_call = llm_response["choices"][0]["message"].get(
                    "tool_calls",
                    [None]
                )[0]
                if tool_call:
                    tool_result = self.execute_tool(
                        tool_call["function"]["name"],
                        json.loads(tool_call["function"]["arguments"])
                    )

                    # Generate final response
                    final_response = (
                        f"The weather in {tool_result['location']} is "
                        f"{tool_result['condition']} with a temperature of "
                        f"{tool_result['temperature']}."
                    )
                else:
                    final_response = (
                        "I couldn't determine what you're asking about."
                    )

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
                        "gen_ai.provider.name": self.llm_provider.provider_name,
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

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool with proper instrumentation.

        This method creates an execute_tool span following gen-ai semantic
        conventions. Implementation mirrors weather_agent.py
        WeatherAgent.execute_tool() exactly.

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
                tool_def = next(
                    (t for t in self.tools
                     if t["function"]["name"] == tool_name),
                    None
                )
                if tool_def:
                    span.set_attribute(
                        "gen_ai.tool.description",
                        tool_def["function"]["description"]
                    )

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

                # Execute the actual tool (using injected provider)
                result = self.tool_provider.execute(tool_name, arguments)

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

    def invoke_child_agent(
        self, child_name: str, message: str, conversation_id: str
    ) -> str:
        """
        Invoke a child agent with trace context propagation.

        This method retrieves a child agent by name and invokes it with the
        provided message and conversation ID. The current OpenTelemetry trace
        context is automatically propagated to the child agent, ensuring that
        the child's invoke_agent span becomes a child of the current span.

        Trace Context Propagation:
        - The child agent's invoke_agent span will be a child of the current
          span due to OpenTelemetry's automatic context propagation within
          the same process
        - The trace_id is preserved across the parent-child invocation
        - The parent_span_id of the child's span will match the current span_id

        Span Kind Behavior:
        - The child agent's span_kind (INTERNAL or CLIENT) is determined by
          the child agent's configuration, not by this method
        - INTERNAL: Represents in-process agent invocations (e.g., LangChain,
          CrewAI agents)
        - CLIENT: Represents remote agent service calls (e.g., OpenAI
          Assistants API, AWS Bedrock Agents)

        Args:
            child_name: Name of the child agent to invoke (must exist in
                       self.child_agents dictionary)
            message: Message to send to the child agent
            conversation_id: Conversation ID to maintain continuity across
                           the agent hierarchy

        Returns:
            Child agent's response string

        Raises:
            ChildAgentNotFoundError: If child_name is not found in the
                                    child_agents dictionary
        """
        # Retrieve child agent from dictionary
        if child_name not in self.child_agents:
            available_children = list(self.child_agents.keys())
            raise ChildAgentNotFoundError(child_name, available_children)

        child_agent = self.child_agents[child_name]

        # Invoke child agent - trace context is automatically propagated
        # by OpenTelemetry within the same process
        child_response = child_agent.invoke(message, conversation_id)

        return child_response
