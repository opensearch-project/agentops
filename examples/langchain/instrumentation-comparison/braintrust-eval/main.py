"""
Braintrust Evaluation Example - Dual OTLP Export

Sends traces to both AgentOps (local OpenSearch) and Braintrust (cloud) via OTLP.
Uses braintrust.* namespace attributes per Braintrust OTLP documentation.

Environment variables:
- OTEL_EXPORTER_OTLP_ENDPOINT: AgentOps endpoint (default: http://localhost:4317)
- BRAINTRUST_API_KEY: Braintrust API key (optional, enables Braintrust export)
- BRAINTRUST_PARENT: Braintrust parent (default: project_name:agentops-comparison)
"""

import os
import sys
sys.path.append("..")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpExporter
from opentelemetry.sdk.resources import Resource

from langchain_aws import ChatBedrockConverse
from shared.weather_tools import WEATHER_TOOLS


EVAL_DATA = [
    {
        "input": "What's the weather in Seattle?",
        "expected": {"tool": "get_current_weather", "location": "Seattle"},
        "tags": ["current-weather"],
    },
    {
        "input": "Give me a 3-day forecast for Tokyo",
        "expected": {"tool": "get_forecast", "location": "Tokyo"},
        "tags": ["forecast"],
    },
    {
        "input": "What was the weather in London on 2024-01-15?",
        "expected": {"tool": "get_historical_weather", "location": "London"},
        "tags": ["historical"],
    },
]


def setup_telemetry(service_name: str) -> TracerProvider:
    """Configure dual OTLP export to AgentOps and Braintrust."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": "evaluation",
    })
    provider = TracerProvider(resource=resource)
    
    # Export to AgentOps (gRPC)
    agentops_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=agentops_endpoint, insecure=True)
    ))
    print(f"✓ AgentOps OTLP → {agentops_endpoint}")
    
    # Export to Braintrust (HTTP with auth) - only if API key is set
    braintrust_api_key = os.getenv("BRAINTRUST_API_KEY")
    if braintrust_api_key:
        braintrust_parent = os.getenv("BRAINTRUST_PARENT", "project_name:agentops-comparison")
        provider.add_span_processor(BatchSpanProcessor(
            OTLPHttpExporter(
                endpoint="https://api.braintrust.dev/otel/v1/traces",
                headers={
                    "Authorization": f"Bearer {braintrust_api_key}",
                    "x-bt-parent": braintrust_parent,
                },
            )
        ))
        print(f"✓ Braintrust OTLP → {braintrust_parent}")
    
    trace.set_tracer_provider(provider)
    return provider


def run_task(llm, query: str) -> dict:
    """Run the weather agent task."""
    result = llm.invoke(query)
    if hasattr(result, "tool_calls") and result.tool_calls:
        tc = result.tool_calls[0]
        return {"tool": tc["name"], "location": tc["args"].get("location", ""), "args": tc["args"]}
    return {"tool": None, "location": None, "response": result.content}


def score_tool_match(output: dict, expected: dict) -> float:
    """Score: Did we select the correct tool?"""
    return 1.0 if output.get("tool") == expected.get("tool") else 0.0


def score_location_match(output: dict, expected: dict) -> float:
    """Score: Did we extract the correct location?"""
    if not output.get("location"):
        return 0.0
    return 1.0 if expected["location"].lower() in output["location"].lower() else 0.0


def run_eval(experiment_name: str = "weather-agent-bt-001"):
    """Run Braintrust-style evaluation with dual export."""
    
    provider = setup_telemetry("braintrust-eval-weather")
    tracer = trace.get_tracer("braintrust-eval")
    
    print(f"\n🧪 Running: {experiment_name}")
    print("=" * 60)
    
    llm = ChatBedrockConverse(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0
    ).bind_tools(WEATHER_TOOLS)
    
    results = []
    
    # Root span for the experiment
    with tracer.start_as_current_span("experiment_run") as exp_span:
        exp_span.set_attribute("braintrust.experiment_name", experiment_name)
        exp_span.set_attribute("braintrust.metadata.dataset", "weather-tools-v1")
        
        for i, case in enumerate(EVAL_DATA):
            with tracer.start_as_current_span(f"eval_case_{i}") as case_span:
                # Braintrust input/expected/output attributes
                case_span.set_attribute("braintrust.input", case["input"])
                case_span.set_attribute("braintrust.expected", str(case["expected"]))
                
                # Run task
                output = run_task(llm, case["input"])
                case_span.set_attribute("braintrust.output", str(output))
                
                # Compute scores
                tool_score = score_tool_match(output, case["expected"])
                loc_score = score_location_match(output, case["expected"])
                
                # Braintrust scores namespace (maps to Braintrust scores field)
                case_span.set_attribute("braintrust.scores.tool_match", tool_score)
                case_span.set_attribute("braintrust.scores.location_match", loc_score)
                
                # Tags
                if case.get("tags"):
                    case_span.set_attribute("braintrust.tags", ",".join(case["tags"]))
                
                results.append({
                    "input": case["input"],
                    "output": output,
                    "scores": {"tool_match": tool_score, "location_match": loc_score}
                })
                
                status = "✓" if tool_score == 1.0 and loc_score == 1.0 else "✗"
                print(f"  {status} Case {i+1}: tool={tool_score:.0f} loc={loc_score:.0f}")
        
        # Summary metrics on experiment span
        avg_tool = sum(r["scores"]["tool_match"] for r in results) / len(results)
        avg_loc = sum(r["scores"]["location_match"] for r in results) / len(results)
        exp_span.set_attribute("braintrust.metrics.avg_tool_match", avg_tool)
        exp_span.set_attribute("braintrust.metrics.avg_location_match", avg_loc)
        exp_span.set_attribute("braintrust.metrics.total_cases", len(results))
    
    provider.force_flush()
    
    print(f"\n📊 Results: {len(results)}/{len(EVAL_DATA)} cases")
    print(f"   tool_match: {avg_tool*100:.0f}%")
    print(f"   location_match: {avg_loc*100:.0f}%")
    print("✓ Traces exported")


if __name__ == "__main__":
    run_eval()
