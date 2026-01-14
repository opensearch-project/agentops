"""
LangChain Bedrock Agent - OpenTelemetry Instrumentation Example

This example demonstrates how to instrument a LangChain agent application
with OpenTelemetry to send telemetry data to the ATLAS observability stack
using OTLP protocol.
"""

from typing import Any

from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


# ============================================================================
# OPENTELEMETRY SETUP - OTLP EXPORTER CONFIGURATION
# ============================================================================


def setup_telemetry(
    service_name: str = "langchain-bedrock-agent",
    service_version: str = "1.0.0",
    otlp_endpoint: str = "http://localhost:4317",
) -> None:
    """
    Set up OpenTelemetry with OTLP exporter and LangChain instrumentation.

    Configures TracerProvider, OTLP gRPC exporter, and LangchainInstrumentor
    to automatically capture LLM operations with Gen-AI semantic conventions.

    LangchainInstrumentor wraps LangChain's callback manager to inject
    telemetry handler, creating spans for:
    - LLM invocations (gen_ai.operation.name = "chat")
    - Token usage (gen_ai.usage.input_tokens, gen_ai.usage.output_tokens)
    - Tool calls with arguments and results

    Args:
        service_name: Name of the service/agent
        service_version: Version of the service
        otlp_endpoint: OTLP collector endpoint (gRPC)
    """
    # Create resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": "development",
    })

    # Set up TracerProvider and OTLP exporter
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Configure OTLP gRPC exporter (sends traces to ATLAS stack)
    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,  # No TLS for local development
    )

    # Add BatchSpanProcessor for efficient span export
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)

    # Instrument LangChain - injects callback handler for automatic tracing
    LangchainInstrumentor().instrument()

    print("✓ OpenTelemetry configured with LangChain instrumentation")
    print(f"  - Service: {service_name} v{service_version}")
    print(f"  - OTLP Endpoint: {otlp_endpoint}")
    print("  - Instrumentation: LangChain callback handler injected")
    print()


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================


@tool
def calculate_growth(initial_value: float, rate: float, years: int) -> float:
    """
    Calculates compound interest growth.

    This tool demonstrates how LangChain automatically instruments tool
    execution with OpenTelemetry, creating spans with:
    - gen_ai.operation.name = "execute_tool"
    - gen_ai.tool.name = "calculate_growth"
    - Tool input arguments and output results

    Args:
        initial_value: The starting amount.
        rate: The annual interest rate as a decimal (e.g., 0.05 for 5%).
        years: The number of years to compound.

    Returns:
        The final value after compound growth.
    """
    return initial_value * (1 + rate) ** years


# ============================================================================
# AGENT CONFIGURATION
# ============================================================================


def create_agent(
    model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
) -> Any:
    """
    Creates a LangChain agent with AWS Bedrock and OpenTelemetry.

    LangChain automatically instruments the agent with OpenTelemetry when
    the langchain-opentelemetry package is installed and configured.
    This creates spans for:

    1. Agent Invocations:
       - Captures full agent execution from input to output
       - Records reasoning steps and tool selection decisions

    2. LLM Calls (gen_ai.operation.name = "chat"):
       - gen_ai.provider.name = "aws_bedrock"
       - gen_ai.request.model = model_id
       - gen_ai.usage.input_tokens = prompt tokens
       - gen_ai.usage.output_tokens = completion tokens

    3. Tool Executions (gen_ai.operation.name = "execute_tool"):
       - gen_ai.tool.name = tool name
       - Tool arguments and results

    Args:
        model_id: AWS Bedrock model identifier

    Returns:
        Configured LangChain agent runnable
    """
    # Initialize AWS Bedrock model with Converse API
    # LangChain will automatically instrument Bedrock API calls
    llm = ChatBedrockConverse(
        model_id=model_id,
        temperature=0,
    )

    # Bind tools to the model
    # This enables the model to call tools during execution
    tools = [calculate_growth]
    llm_with_tools = llm.bind_tools(tools)

    # Create prompt template
    # The agent will use this to structure its reasoning
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a helpful financial assistant. "
            "Use tools for precise math calculations.",
        ),
        ("human", "{input}"),
    ])

    # Create the agent chain
    # LangChain will automatically trace each step in the chain
    agent = prompt | llm_with_tools

    return agent


# ============================================================================
# AGENT EXECUTION WITH TELEMETRY
# ============================================================================


def run_agent(query: str) -> None:
    """
    Executes the agent with a query and automatic telemetry.

    Each agent invocation creates a complete trace including:
    - Agent invocation span (parent)
    - LLM inference spans with token usage
    - Tool execution spans
    - Chain step spans

    The telemetry data flows:
    LangChain → OpenTelemetry → OTLP Exporter →
    OTel Collector → Data Prepper → OpenSearch

    Args:
        query: User's question or task
    """
    print(f"\n📝 Query: {query}\n")

    # Create agent
    agent = create_agent()

    # Configure runnable with callbacks for better observability
    config = RunnableConfig(
        run_name="financial_assistant",
        tags=["finance", "calculator"],
    )

    try:
        # Invoke the agent
        # This creates a complete trace with all operations
        result = agent.invoke({"input": query}, config=config)

        # Extract the response
        # Handle both tool calls and direct responses
        if hasattr(result, "tool_calls") and result.tool_calls:
            print("🔧 Tool calls made:")
            for tool_call in result.tool_calls:
                print(f"  - {tool_call['name']}: {tool_call['args']}")

            # Execute tools and get final response
            # In a real implementation, you'd use AgentExecutor
            # or implement a tool execution loop
            tool_results = []
            for tool_call in result.tool_calls:
                if tool_call["name"] == "calculate_growth":
                    tool_result = calculate_growth.invoke(tool_call["args"])
                    tool_results.append(tool_result)
                    print(f"  → Result: ${tool_result:,.2f}")

            print(f"\n✅ Final Answer: ${tool_results[0]:,.2f}")
        else:
            # Direct response without tool calls
            print(f"✅ Response: {result.content}")

    except Exception as e:  # noqa: BLE001
        # Errors are automatically captured in span status
        # The span will have:
        # - status.code = ERROR
        # - status.message = error description
        # - exception event with stack trace
        print(f"\n❌ Error: {e}")
        print("Check OpenSearch Dashboards for error traces.")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main() -> None:
    """
    Main function demonstrating LangChain agent with OpenTelemetry.

    This example shows the complete setup:
    1. Configure OpenTelemetry with OTLP exporter
    2. Instrument LangChain with LangChainInstrumentor
    3. Create and run agent with automatic telemetry

    All LangChain operations are automatically traced with Gen-AI
    semantic conventions and exported to the ATLAS stack.
    """
    print("\n💰 LangChain Bedrock Financial Assistant 💰")
    print("=" * 60)
    print()

    # Step 1: Set up OpenTelemetry instrumentation
    # This configures the OTLP exporter and instruments LangChain
    print("Setting up OpenTelemetry instrumentation...")
    setup_telemetry(
        service_name="langchain-bedrock-agent",
        service_version="1.0.0",
        otlp_endpoint="http://localhost:4317",
    )

    print("📊 Telemetry enabled - all operations will be traced")
    print("   View traces at: http://localhost:5601")
    print("   (OpenSearch Dashboards)\n")

    # Step 2: Run the agent
    # LangChain operations are automatically instrumented via callback handler
    query = "If I invest $10,000 at 7% for 5 years, what will it be worth?"
    run_agent(query)

    # Step 3: Clean up instrumentation
    # Uninstrument LangChain to remove callback handler
    print("\nCleaning up instrumentation...")
    LangchainInstrumentor().uninstrument()
    print("✓ LangChain uninstrumented")

    print("\n" + "=" * 60)
    print("✅ Example complete!")
    print("\nView telemetry data:")
    print("  - Traces: http://localhost:5601 (OpenSearch Dashboards)")
    print("\nTelemetry includes:")
    print("  - LLM invocation spans with Gen-AI attributes")
    print("  - Token usage (input/output tokens)")
    print("  - Tool call information")
    print("  - Request/response timing")
    print()


if __name__ == "__main__":
    main()
