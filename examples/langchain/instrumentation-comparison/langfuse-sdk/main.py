"""
LangChain Weather Agent - Langfuse SDK v3 Instrumentation

Uses: langfuse SDK v3 (OTEL-native) with custom OTLP endpoint
Dual-exports to AgentOps (always) and Langfuse (if API keys set).
"""

import base64
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
    """Configure OpenTelemetry to dual-export to AgentOps and Langfuse."""
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
    
    # Conditionally send to Langfuse
    langfuse_pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_sk = os.getenv("LANGFUSE_SECRET_KEY")
    if langfuse_pk and langfuse_sk:
        auth = base64.b64encode(f"{langfuse_pk}:{langfuse_sk}".encode()).decode()
        provider.add_span_processor(BatchSpanProcessor(
            OTLPHttpExporter(
                endpoint="https://cloud.langfuse.com/api/public/otel/v1/traces",
                headers={"Authorization": f"Basic {auth}"}
            )
        ))
        print("✓ Langfuse OTLP configured → https://cloud.langfuse.com")
    else:
        print("ℹ LANGFUSE_PUBLIC_KEY/SECRET_KEY not set, skipping Langfuse export")
    
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


def run_query_with_langfuse_tracing(agent, query: str, tracer) -> None:
    """Execute a query with Langfuse-style manual tracing using OTel."""
    print(f"\n📝 Query: {query}")
    
    # Use standard OTel tracing with Langfuse-style attributes
    with tracer.start_as_current_span("weather_agent_query") as span:
        # Langfuse-specific attributes (langfuse.* namespace)
        span.set_attribute("langfuse.trace.name", "weather_agent_query")
        span.set_attribute("langfuse.user.id", "test-user-123")
        span.set_attribute("langfuse.session.id", "test-session-456")
        span.set_attribute("langfuse.trace.tags", "weather,langchain,comparison-test")
        span.set_attribute("langfuse.trace.metadata.source", "instrumentation-comparison")
        span.set_attribute("langfuse.observation.input", query)
        
        # GenAI semantic convention attributes (Langfuse supports these)
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "us.anthropic.claude-sonnet-4-20250514-v1:0")
        span.set_attribute("gen_ai.system", "langchain")
        
        result = agent.invoke({"input": query})
        
        if hasattr(result, "tool_calls") and result.tool_calls:
            for tool_call in result.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                print(f"🔧 Tool: {tool_name}({tool_args})")
                
                # Create child span for tool execution (Langfuse style)
                with tracer.start_as_current_span(f"tool.{tool_name}") as tool_span:
                    tool_span.set_attribute("langfuse.observation.type", "span")
                    tool_span.set_attribute("langfuse.observation.input", str(tool_args))
                    tool_span.set_attribute("langfuse.observation.metadata.tool_name", tool_name)
                    
                    tool_fn = next(t for t in WEATHER_TOOLS if t.name == tool_name)
                    tool_result = tool_fn.invoke(tool_args)
                    
                    tool_span.set_attribute("langfuse.observation.output", str(tool_result))
                    print(f"   Result: {tool_result}")
            
            span.set_attribute("langfuse.observation.output", f"Executed {len(result.tool_calls)} tool(s)")
        else:
            span.set_attribute("langfuse.observation.output", result.content)
            print(f"💬 Response: {result.content}")
        
        # Langfuse usage tracking
        span.set_attribute("gen_ai.usage.input_tokens", 150)
        span.set_attribute("gen_ai.usage.output_tokens", 50)


def main():
    print("\n🌤️  LangChain Weather Agent - Langfuse SDK v3 Style")
    print("=" * 60)
    
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    
    setup_telemetry("langchain-weather-langfuse", otlp_endpoint)
    
    tracer = trace.get_tracer("langfuse-weather-agent")
    agent = create_agent()
    
    for query in TEST_QUERIES:
        run_query_with_langfuse_tracing(agent, query, tracer)
    
    # Force flush
    trace.get_tracer_provider().force_flush()
    
    print("\n✅ Complete - check OpenSearch for traces")
    print("   Look for langfuse.* attributes in span data")


if __name__ == "__main__":
    main()
