"""
Langfuse Evaluation Example - Traces sent to AgentOps

Demonstrates running a Langfuse experiment/evaluation while
capturing all traces and spans in AgentOps via OTLP.

Key concepts:
- Dataset: Collection of test cases (input + expected output)
- Experiment: A run of your task against the dataset
- Scores: Evaluation metrics attached to traces
"""

import os
import sys
sys.path.append("..")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

from langchain_aws import ChatBedrockConverse
from shared.weather_tools import WEATHER_TOOLS


# Simple evaluation dataset
EVAL_DATASET = [
    {
        "id": "weather-1",
        "input": "What's the weather in Seattle?",
        "expected_tool": "get_current_weather",
        "expected_location": "Seattle",
    },
    {
        "id": "weather-2", 
        "input": "Give me a 3-day forecast for Tokyo",
        "expected_tool": "get_forecast",
        "expected_location": "Tokyo",
    },
    {
        "id": "weather-3",
        "input": "What was the weather in London on 2024-01-15?",
        "expected_tool": "get_historical_weather",
        "expected_location": "London",
    },
]


def setup_telemetry(service_name: str, otlp_endpoint: str) -> TracerProvider:
    """Configure OTLP export to AgentOps."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": "evaluation",
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider


def score_tool_selection(result, expected_tool: str) -> float:
    """Score whether the correct tool was selected."""
    if not hasattr(result, "tool_calls") or not result.tool_calls:
        return 0.0
    selected_tool = result.tool_calls[0]["name"]
    return 1.0 if selected_tool == expected_tool else 0.0


def score_location_extraction(result, expected_location: str) -> float:
    """Score whether the correct location was extracted."""
    if not hasattr(result, "tool_calls") or not result.tool_calls:
        return 0.0
    args = result.tool_calls[0].get("args", {})
    location = args.get("location", "")
    return 1.0 if expected_location.lower() in location.lower() else 0.0


def run_task(llm, query: str):
    """The task being evaluated - invoke LLM with tools."""
    return llm.invoke(query)


def run_evaluation(experiment_name: str = "weather-agent-eval-001"):
    """Run evaluation and capture traces in AgentOps."""
    
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
    provider = setup_telemetry("langfuse-eval-weather", otlp_endpoint)
    tracer = trace.get_tracer("langfuse-eval")
    
    print(f"\n🧪 Langfuse Evaluation: {experiment_name}")
    print("=" * 60)
    print(f"📊 Dataset: {len(EVAL_DATASET)} test cases")
    print(f"📡 OTLP Endpoint: {otlp_endpoint}")
    
    # Create LLM with tools
    llm = ChatBedrockConverse(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0
    ).bind_tools(WEATHER_TOOLS)
    
    # Track aggregate scores
    scores = {"tool_selection": [], "location_extraction": []}
    
    # Run evaluation - each item creates a trace
    for item in EVAL_DATASET:
        with tracer.start_as_current_span("eval_run") as experiment_span:
            # Langfuse experiment metadata
            experiment_span.set_attribute("langfuse.experiment.name", experiment_name)
            experiment_span.set_attribute("langfuse.experiment.run_id", item["id"])
            experiment_span.set_attribute("langfuse.dataset.item_id", item["id"])
            experiment_span.set_attribute("langfuse.trace.tags", "evaluation,weather-agent")
            
            # Input/expected
            experiment_span.set_attribute("langfuse.observation.input", item["input"])
            experiment_span.set_attribute("eval.expected_tool", item["expected_tool"])
            experiment_span.set_attribute("eval.expected_location", item["expected_location"])
            
            # GenAI attributes
            experiment_span.set_attribute("gen_ai.operation.name", "eval")
            experiment_span.set_attribute("gen_ai.request.model", "us.anthropic.claude-sonnet-4-20250514-v1:0")
            
            print(f"\n📝 [{item['id']}] {item['input']}")
            
            # Run the task
            with tracer.start_as_current_span("task") as task_span:
                task_span.set_attribute("gen_ai.operation.name", "chat")
                result = run_task(llm, item["input"])
                
                if hasattr(result, "tool_calls") and result.tool_calls:
                    tool_call = result.tool_calls[0]
                    task_span.set_attribute("gen_ai.tool.name", tool_call["name"])
                    task_span.set_attribute("gen_ai.tool.call.arguments", str(tool_call["args"]))
                    experiment_span.set_attribute("langfuse.observation.output", f"Tool: {tool_call['name']}")
                    print(f"   🔧 Tool: {tool_call['name']}({tool_call['args']})")
                else:
                    experiment_span.set_attribute("langfuse.observation.output", result.content[:100])
            
            # Score the result
            tool_score = score_tool_selection(result, item["expected_tool"])
            location_score = score_location_extraction(result, item["expected_location"])
            
            scores["tool_selection"].append(tool_score)
            scores["location_extraction"].append(location_score)
            
            # Attach scores to span (Langfuse style)
            experiment_span.set_attribute("langfuse.score.tool_selection", tool_score)
            experiment_span.set_attribute("langfuse.score.location_extraction", location_score)
            
            print(f"   ✅ tool_selection: {tool_score}, location_extraction: {location_score}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Evaluation Summary")
    print(f"   tool_selection:      {sum(scores['tool_selection'])/len(scores['tool_selection']):.1%}")
    print(f"   location_extraction: {sum(scores['location_extraction'])/len(scores['location_extraction']):.1%}")
    
    # Flush traces
    provider.force_flush()
    print("\n✅ Traces sent to AgentOps - check OpenSearch for:")
    print("   - langfuse.experiment.* attributes")
    print("   - langfuse.score.* attributes")


if __name__ == "__main__":
    run_evaluation()
