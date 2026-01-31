"""
LangChain Weather Agent - OpenInference Instrumentation (Arize Phoenix)

Uses: openinference-instrumentation-langchain
"""

import sys
sys.path.append("..")

from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from openinference.instrumentation.langchain import LangChainInstrumentor

from shared.weather_tools import WEATHER_TOOLS, SYSTEM_PROMPT, TEST_QUERIES


def setup_telemetry(service_name: str, otlp_endpoint: str) -> None:
    """Configure OpenTelemetry with OpenInference LangChain instrumentation."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
    })
    
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    
    LangChainInstrumentor().instrument()
    print(f"✓ OpenInference LangChain instrumentation configured")


def create_agent(model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"):
    """Create LangChain agent with Bedrock."""
    llm = ChatBedrockConverse(model_id=model_id, temperature=0)
    llm_with_tools = llm.bind_tools(WEATHER_TOOLS)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    
    return prompt | llm_with_tools


def run_query(agent, query: str) -> None:
    """Execute a query and handle tool calls."""
    print(f"\n📝 Query: {query}")
    
    result = agent.invoke({"input": query})
    
    if hasattr(result, "tool_calls") and result.tool_calls:
        for tool_call in result.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"🔧 Tool: {tool_name}({tool_args})")
            
            # Execute tool
            tool_fn = next(t for t in WEATHER_TOOLS if t.name == tool_name)
            tool_result = tool_fn.invoke(tool_args)
            print(f"   Result: {tool_result}")
    else:
        print(f"💬 Response: {result.content}")


def main():
    print("\n🌤️  LangChain Weather Agent - OpenInference Instrumentation")
    print("=" * 60)
    
    import os
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    
    setup_telemetry("langchain-weather-openinference", otlp_endpoint)
    
    agent = create_agent()
    
    for query in TEST_QUERIES:
        run_query(agent, query)
    
    print("\n✅ Complete - check OpenSearch for traces")


if __name__ == "__main__":
    main()
