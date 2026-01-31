"""
LangChain Weather Agent - Braintrust SDK Instrumentation

Uses: braintrust SDK with custom OTLP endpoint
Dual-exports to AgentOps (always) and Braintrust (if API key set).
"""

import os
import sys
sys.path.append("..")

from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpExporter
from opentelemetry.sdk.resources import Resource

from shared.weather_tools import WEATHER_TOOLS, SYSTEM_PROMPT, TEST_QUERIES


def setup_telemetry(service_name: str, otlp_endpoint: str) -> None:
    """Configure OpenTelemetry to dual-export to AgentOps and Braintrust."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0"
    })
    provider = TracerProvider(resource=resource)
    
    # Always send to AgentOps
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    ))
    print(f"✓ AgentOps OTLP configured → {otlp_endpoint}")
    
    # Conditionally send to Braintrust
    braintrust_api_key = os.getenv("BRAINTRUST_API_KEY")
    braintrust_parent = os.getenv("BRAINTRUST_PARENT", "project_name:agentops-comparison")
    if braintrust_api_key:
        provider.add_span_processor(BatchSpanProcessor(
            OTLPHttpExporter(
                endpoint="https://api.braintrust.dev/otel/v1/traces",
                headers={
                    "Authorization": f"Bearer {braintrust_api_key}",
                    "x-bt-parent": braintrust_parent
                }
            )
        ))
        print(f"✓ Braintrust OTLP configured → https://api.braintrust.dev ({braintrust_parent})")
    else:
        print("ℹ BRAINTRUST_API_KEY not set, skipping Braintrust export")
    
    trace.set_tracer_provider(provider)


def create_agent(model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"):
    """Create LangChain agent with Bedrock."""
    llm = ChatBedrockConverse(model_id=model_id, temperature=0)
    llm_with_tools = llm.bind_tools(WEATHER_TOOLS)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    
    return prompt | llm_with_tools


def run_query(agent, query: str, tracer) -> None:
    """Execute a query with Braintrust-style manual tracing."""
    print(f"\n📝 Query: {query}")
    
    # Braintrust uses gen_ai.* and braintrust.* namespaces
    with tracer.start_as_current_span("weather_agent_query") as span:
        # Braintrust-specific attributes
        span.set_attribute("braintrust.input", query)
        span.set_attribute("braintrust.metadata.source", "instrumentation-comparison")
        span.set_attribute("braintrust.tags", ["weather", "langchain", "comparison-test"])
        
        # GenAI semantic convention attributes (Braintrust supports these)
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "us.anthropic.claude-sonnet-4-20250514-v1:0")
        span.set_attribute("gen_ai.system", "langchain")
        
        result = agent.invoke({"input": query})
        
        if hasattr(result, "tool_calls") and result.tool_calls:
            for tool_call in result.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                print(f"🔧 Tool: {tool_name}({tool_args})")
                
                # Create child span for tool execution (Braintrust style)
                with tracer.start_as_current_span(f"tool.{tool_name}") as tool_span:
                    tool_span.set_attribute("gen_ai.operation.name", "execute_tool")
                    tool_span.set_attribute("gen_ai.tool.name", tool_name)
                    tool_span.set_attribute("braintrust.input", str(tool_args))
                    tool_span.set_attribute("braintrust.span_attributes.type", "tool")
                    
                    tool_fn = next(t for t in WEATHER_TOOLS if t.name == tool_name)
                    tool_result = tool_fn.invoke(tool_args)
                    
                    tool_span.set_attribute("braintrust.output", str(tool_result))
                    print(f"   Result: {tool_result}")
            
            span.set_attribute("braintrust.output", f"Executed {len(result.tool_calls)} tool(s)")
        else:
            span.set_attribute("braintrust.output", result.content)
            print(f"💬 Response: {result.content}")
        
        # Braintrust metrics
        span.set_attribute("braintrust.metrics.prompt_tokens", 150)
        span.set_attribute("braintrust.metrics.completion_tokens", 50)


def main():
    print("\n🌤️  LangChain Weather Agent - Braintrust SDK Style")
    print("=" * 60)
    
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    
    setup_telemetry("langchain-weather-braintrust", otlp_endpoint)
    
    tracer = trace.get_tracer("braintrust-weather-agent")
    agent = create_agent()
    
    for query in TEST_QUERIES:
        run_query(agent, query, tracer)
    
    # Force flush
    trace.get_tracer_provider().force_flush()
    
    print("\n✅ Complete - check OpenSearch for traces")
    print("   Look for braintrust.* attributes in span data")


if __name__ == "__main__":
    main()
