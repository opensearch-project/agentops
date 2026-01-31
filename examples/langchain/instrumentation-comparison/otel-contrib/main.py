"""
LangChain Weather Agent - OTel Contrib Instrumentation

Uses: opentelemetry-instrumentation-openai-v2 (Official OpenTelemetry)

Note: The official OTel contrib LangChain instrumentation is not yet released.
This example uses the OpenAI instrumentation which captures the underlying
LLM calls made by LangChain when using OpenAI-compatible models.
"""

import sys
sys.path.append("..")

from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# Official OTel contrib - note: Bedrock instrumentation not yet available
# Using manual spans to demonstrate the expected attribute format
from shared.weather_tools import WEATHER_TOOLS, SYSTEM_PROMPT, TEST_QUERIES


def setup_telemetry(service_name: str, otlp_endpoint: str) -> trace.Tracer:
    """Configure OpenTelemetry with official contrib patterns."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
    })
    
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    
    # Note: Would use OpenAIInstrumentor().instrument() for OpenAI
    # Bedrock instrumentation not yet available in otel-contrib
    # This example shows manual instrumentation following GenAI SemConv
    
    print(f"✓ OTel Contrib style instrumentation configured (manual for Bedrock)")
    return trace.get_tracer("langchain-weather-otel-contrib")


def create_agent(model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"):
    """Create LangChain agent with Bedrock."""
    llm = ChatBedrockConverse(model_id=model_id, temperature=0)
    llm_with_tools = llm.bind_tools(WEATHER_TOOLS)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    
    return prompt | llm_with_tools


def run_query(agent, query: str, tracer: trace.Tracer) -> None:
    """Execute a query with manual instrumentation following OTel contrib patterns."""
    print(f"\n📝 Query: {query}")
    
    # Manual instrumentation following GenAI SemConv (as OTel contrib does)
    with tracer.start_as_current_span(
        "chat us.anthropic.claude-sonnet-4-20250514-v1:0",
        kind=trace.SpanKind.CLIENT
    ) as span:
        # GenAI SemConv attributes (same as OTel contrib openai-v2)
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.system", "aws.bedrock")
        span.set_attribute("gen_ai.request.model", "us.anthropic.claude-sonnet-4-20250514-v1:0")
        span.set_attribute("gen_ai.request.temperature", 0)
        
        result = agent.invoke({"input": query})
        
        # Response attributes
        if hasattr(result, "response_metadata"):
            usage = result.response_metadata.get("usage", {})
            if "input_tokens" in usage:
                span.set_attribute("gen_ai.usage.input_tokens", usage["input_tokens"])
            if "output_tokens" in usage:
                span.set_attribute("gen_ai.usage.output_tokens", usage["output_tokens"])
        
        if hasattr(result, "tool_calls") and result.tool_calls:
            for i, tool_call in enumerate(result.tool_calls):
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                print(f"🔧 Tool: {tool_name}({tool_args})")
                
                # Tool execution span
                with tracer.start_as_current_span(
                    f"{tool_name}",
                    kind=trace.SpanKind.INTERNAL
                ) as tool_span:
                    tool_span.set_attribute("gen_ai.tool.name", tool_name)
                    
                    tool_fn = next(t for t in WEATHER_TOOLS if t.name == tool_name)
                    tool_result = tool_fn.invoke(tool_args)
                    print(f"   Result: {tool_result}")
        else:
            print(f"💬 Response: {result.content}")


def main():
    print("\n🌤️  LangChain Weather Agent - OTel Contrib Style Instrumentation")
    print("=" * 60)
    print("Note: Using manual instrumentation following GenAI SemConv")
    print("      (Official Bedrock instrumentation not yet in otel-contrib)")
    
    import os
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    
    tracer = setup_telemetry("langchain-weather-otel-contrib", otlp_endpoint)
    
    agent = create_agent()
    
    for query in TEST_QUERIES:
        run_query(agent, query, tracer)
    
    print("\n✅ Complete - check OpenSearch for traces")


if __name__ == "__main__":
    main()
