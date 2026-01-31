"""
Arize Phoenix Evaluation Example

Demonstrates Phoenix's experiment framework with OpenInference instrumentation.
Sends traces to AgentOps via OTLP to capture what attributes flow through.

Key question: Do Phoenix experiment/eval attributes appear in OTLP spans?
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# Configure OTLP export to AgentOps
resource = Resource.create({
    "service.name": "arize-phoenix-eval-weather",
    "service.version": "1.0.0",
    "deployment.environment": "evaluation",
})

provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Now instrument with OpenInference
from openinference.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument(tracer_provider=provider)

# Import after instrumentation
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool

# Weather tools (same as other examples)
@tool
def get_current_weather(location: str) -> dict:
    """Get current weather for a location."""
    return {"location": location, "temp": "72°F", "condition": "sunny"}

@tool
def get_forecast(location: str, days: int = 3) -> dict:
    """Get weather forecast."""
    return {"location": location, "forecast": [{"day": i+1, "high": f"{70+i*2}°F"} for i in range(days)]}

@tool
def get_historical_weather(location: str, date: str) -> dict:
    """Get historical weather for a past date."""
    return {"location": location, "date": date, "temp": "65°F", "condition": "cloudy"}

TOOLS = [get_current_weather, get_forecast, get_historical_weather]

# Create LLM with tools
llm = ChatBedrockConverse(
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-west-2",
).bind_tools(TOOLS)

# Test dataset
TEST_CASES = [
    {
        "input": "What's the weather in Seattle right now?",
        "expected": {"tool": "get_current_weather", "location": "Seattle"},
        "tags": ["current"],
    },
    {
        "input": "Give me a 5-day forecast for Tokyo",
        "expected": {"tool": "get_forecast", "location": "Tokyo"},
        "tags": ["forecast"],
    },
    {
        "input": "What was the weather in London on 2024-01-15?",
        "expected": {"tool": "get_historical_weather", "location": "London"},
        "tags": ["historical"],
    },
]


def run_agent(query: str) -> dict:
    """Run the weather agent and extract tool call info."""
    response = llm.invoke(query)
    if response.tool_calls:
        tc = response.tool_calls[0]
        return {
            "tool": tc["name"],
            "location": tc["args"].get("location", ""),
            "args": tc["args"],
        }
    return {"tool": None, "location": None, "args": {}}


def evaluate_tool_match(output: dict, expected: dict) -> float:
    """Score 1.0 if correct tool selected."""
    return 1.0 if output.get("tool") == expected.get("tool") else 0.0


def evaluate_location_match(output: dict, expected: dict) -> float:
    """Score 1.0 if location extracted correctly."""
    return 1.0 if output.get("location") == expected.get("location") else 0.0


def main():
    """
    Run Phoenix-style experiment with manual OTLP span emission.
    
    Phoenix's run_experiment() stores results in Phoenix DB, not OTLP.
    To capture what a Phoenix user's traces look like, we:
    1. Use OpenInference instrumentation (what Phoenix recommends)
    2. Manually emit experiment spans with Phoenix-style attributes
    """
    tracer = trace.get_tracer("arize-phoenix-eval")
    
    print("=" * 60)
    print("Arize Phoenix Evaluation Example")
    print("=" * 60)
    
    experiment_name = "weather-agent-phoenix-001"
    
    for i, test_case in enumerate(TEST_CASES):
        print(f"\n[Test {i+1}] {test_case['input'][:50]}...")
        
        # Create experiment span with Phoenix/OpenInference style attributes
        with tracer.start_as_current_span("experiment_run") as span:
            # OpenInference span kind
            span.set_attribute("openinference.span.kind", "CHAIN")
            
            # Phoenix experiment attributes (hypothetical - testing what exists)
            span.set_attribute("phoenix.experiment.name", experiment_name)
            span.set_attribute("phoenix.experiment.run_index", i)
            span.set_attribute("phoenix.dataset.example_id", f"weather-{i+1}")
            
            # OpenInference standard attributes
            span.set_attribute("input.value", test_case["input"])
            span.set_attribute("input.mime_type", "text/plain")
            
            # Run the agent (OpenInference will create child LLM spans)
            output = run_agent(test_case["input"])
            
            # Record output
            span.set_attribute("output.value", str(output))
            span.set_attribute("output.mime_type", "text/plain")
            
            # Expected value (OpenInference pattern)
            span.set_attribute("phoenix.expected", str(test_case["expected"]))
            
            # Compute scores
            tool_score = evaluate_tool_match(output, test_case["expected"])
            location_score = evaluate_location_match(output, test_case["expected"])
            
            # Phoenix evaluation scores (testing attribute patterns)
            span.set_attribute("phoenix.eval.tool_match", tool_score)
            span.set_attribute("phoenix.eval.location_match", location_score)
            
            # Tags
            span.set_attribute("phoenix.tags", test_case["tags"])
            
            # GenAI SemConv
            span.set_attribute("gen_ai.operation.name", "eval")
            span.set_attribute("gen_ai.request.model", "us.anthropic.claude-sonnet-4-20250514-v1:0")
            
            print(f"  Tool: {output.get('tool')} (expected: {test_case['expected']['tool']})")
            print(f"  Location: {output.get('location')} (expected: {test_case['expected']['location']})")
            print(f"  Scores: tool={tool_score}, location={location_score}")
    
    # Force flush
    provider.force_flush()
    
    print("\n" + "=" * 60)
    print("Results Summary")
    print("=" * 60)
    print(f"Experiment: {experiment_name}")
    print(f"Test cases: {len(TEST_CASES)}")
    print("Traces sent to AgentOps via OTLP")
    print("\nQuery OpenSearch for spans with:")
    print('  serviceName: "arize-phoenix-eval-weather"')
    print('  attributes.phoenix.experiment.name: "weather-agent-phoenix-001"')


if __name__ == "__main__":
    main()
