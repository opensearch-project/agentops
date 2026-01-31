"""
Code Assistant Agent - OpenTelemetry Instrumentation Example
Adapted from https://github.com/strands-agents/samples/tree/1dbb06f1d2a408b65793410ba7fce06d1c44114d/02-samples/06-code-assistant

This example demonstrates how to instrument a Strands AI agent application
with OpenTelemetry to send telemetry data to an OLTP endpoint.
StrandsTelemetry automatically applies OpenTelemetry GenAI Semantic Conventions.
"""

import os
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

from utils.tools import (
    code_generator,
    code_reviewer,
    code_writer_agent,
    code_execute,
    project_reader,
)
from utils.prompts import CODE_ASSISTANT_PROMPT

# ============================================================================
# CONFIGURATION
# ============================================================================

# Enable rich UI for tool execution visualization in CLI
# This provides better visibility into tool calls during development
os.environ["STRANDS_TOOL_CONSOLE_MODE"] = "enabled"

# ============================================================================
# OPENTELEMETRY SETUP - OTLP EXPORTER CONFIGURATION
# ============================================================================

# Initialize Strands telemetry integration
# StrandsTelemetry automatically instruments agent operations with
# OpenTelemetry, creating spans for:
# - Agent invocations (gen_ai.operation.name = "invoke_agent")
# - Tool executions (gen_ai.operation.name = "execute_tool")
# - Model inference calls (gen_ai.operation.name = "chat")
telemetry = StrandsTelemetry()

# Configure OTLP gRPC exporter to send traces to AgentOps stack
# The exporter sends telemetry data to the OpenTelemetry Collector
# running at localhost:4317 (default OTLP gRPC port)
#
# Configuration details:
# - endpoint: OTLP collector gRPC endpoint (localhost:4317)
# - insecure: Use insecure connection (no TLS) for local development
#
# In production, you would:
# - Use a secure endpoint with TLS
# - Configure authentication/authorization
# - Set appropriate timeout and retry policies
grpc_exporter = GRPCSpanExporter(
    endpoint="localhost:4317",
    insecure=True
)

# Add the OTLP exporter to the tracer provider using BatchSpanProcessor
# BatchSpanProcessor batches spans before export for better performance:
# - Reduces network overhead by batching multiple spans
# - Configurable batch size and timeout
# - Handles export failures with retry logic
#
# The telemetry data flow:
# 1. Strands agent operations create spans
# 2. BatchSpanProcessor collects spans in memory
# 3. Periodically exports batches to OTLP collector
# 4. OTLP collector processes and routes to OpenSearch via Data Prepper
telemetry.tracer_provider.add_span_processor(
    BatchSpanProcessor(grpc_exporter)
)

# ============================================================================
# MODEL CONFIGURATION - AWS BEDROCK
# ============================================================================

# Initialize AWS Bedrock model (Claude Sonnet 4)
# Strands automatically instruments Bedrock API calls with OpenTelemetry,
# capturing:
# - gen_ai.provider.name = "aws_bedrock"
# - gen_ai.request.model = "us.anthropic.claude-sonnet-4-20250514-v1:0"
# - gen_ai.response.model = actual model used
# - gen_ai.usage.input_tokens = prompt tokens consumed
# - gen_ai.usage.output_tokens = completion tokens generated
# - gen_ai.operation.name = "chat"
#
# These attributes follow OpenTelemetry Gen-AI semantic conventions
# and enable analysis of:
# - Model performance and latency
# - Token usage and costs
# - Error rates and types
# - Request/response patterns
claude_sonnet_4 = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
)

# ============================================================================
# AGENT CONFIGURATION - CODE ASSISTANT
# ============================================================================

# Create the Code Assistant agent with OpenTelemetry instrumentation
# The Strands Agent class automatically creates spans for:
#
# 1. Agent Invocations (gen_ai.operation.name = "invoke_agent"):
#    - Captures full agent execution from input to output
#    - Includes agent metadata (name, description, tools available)
#    - Records conversation context and session information
#    - Tracks overall latency and success/failure status
#
# 2. Tool Executions (gen_ai.operation.name = "execute_tool"):
#    - Each tool call creates a child span under the agent invocation
#    - Captures tool name, arguments, and results
#    - Records tool execution latency
#    - Enables debugging of tool selection and execution
#
# 3. Model Inference (gen_ai.operation.name = "chat"):
#    - LLM API calls create spans with token usage
#    - Captures prompt and completion details
#    - Records model-specific attributes
#
# Tools provided to the agent:
# - project_reader: Read and analyze project files
# - code_generator: Generate new code based on requirements
# - code_reviewer: Review and provide feedback on code
# - code_writer_agent: Write code to files
# - code_execute: Execute code and return results
#
# Each tool execution is automatically traced, creating a complete
# observability picture of the agent's decision-making and actions.
code_assistant = Agent(
    system_prompt=CODE_ASSISTANT_PROMPT,
    model=claude_sonnet_4,
    tools=[
        project_reader,
        code_generator,
        code_reviewer,
        code_writer_agent,
        code_execute,
    ],
)
# ============================================================================
# INTERACTIVE CLI - AGENT EXECUTION WITH TELEMETRY
# ============================================================================

# Example usage demonstrating agent invocation with automatic telemetry
if __name__ == "__main__":
    print("\n💻 Code Assistant Agent 💻\n")
    print("This agent helps with programming tasks")
    print("Type your code question or task below or 'exit' to quit.\n")
    print("Example commands:")
    print("  - Run: print('Hello, World!')")
    print(
        "  - Explain: def fibonacci(n): "
        "a,b=0,1; for _ in range(n): a,b=b,a+b; return a"
    )
    print("  - Create a Python script that sorts a list")
    print("\n📊 Telemetry: All operations are traced to AgentOps stack")
    print("   View traces at: http://localhost:5601 (OpenSearch Dashboards)")

    # Interactive loop - each agent invocation creates telemetry spans
    while True:
        try:
            user_input = input("\n> ")
            if user_input.lower() == "exit":
                print("\nGoodbye! 👋")
                break

            # Process the input as a coding question/task
            # This single call creates a complete trace including:
            # 1. invoke_agent span (parent)
            # 2. chat span for LLM inference (child)
            # 3. execute_tool spans for each tool used (children)
            # 4. Additional chat spans if multi-turn reasoning occurs
            #
            # All spans include:
            # - Gen-AI semantic convention attributes
            # - Timing information (start, duration, end)
            # - Status (OK, ERROR)
            # - Events for key operations
            # - Links to related spans
            #
            # The telemetry data flows:
            # Agent → StrandsTelemetry → BatchSpanProcessor →
            # OTLP Exporter → OTel Collector → Data Prepper → OpenSearch
            code_assistant(user_input)

        except KeyboardInterrupt:
            print("\n\nExecution interrupted. Exiting...")
            break
        except Exception as e:  # noqa: BLE001
            # Errors are automatically captured in span status and events
            # The span will have:
            # - status.code = ERROR
            # - status.message = error description
            # - exception event with stack trace
            print(f"\nAn error occurred: {str(e)}")
            print("Please try asking a different question.")
            print("Check OpenSearch Dashboards for error traces.")
