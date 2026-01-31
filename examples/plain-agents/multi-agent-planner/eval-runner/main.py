#!/usr/bin/env python3
"""
Eval Runner - Continuous evaluation for travel-planner.
Sends telemetry to AgentOps, optionally dual-sends to Langfuse if configured.
"""

import os
import time
import requests
from datetime import datetime
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind, Status, StatusCode

# Configuration
TRAVEL_PLANNER_URL = os.getenv("TRAVEL_PLANNER_URL", "http://travel-planner:8000")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
EVAL_INTERVAL = int(os.getenv("EVAL_INTERVAL", "60"))
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

# Test dataset with expected outputs
EVAL_DATASET = [
    {
        "destination": "Paris",
        "expected": {
            "weather": True,
            "events": True,
            "event_venues": ["Louvre", "Seine", "Caveau"],  # Must contain one of these
            "recommendation_keywords": ["paris", "french", "eiffel", "cuisine", "louvre"],
        },
    },
    {
        "destination": "Tokyo",
        "expected": {
            "weather": True,
            "events": True,
            "event_venues": ["Shibuya", "Tsukiji", "Shinjuku"],
            "recommendation_keywords": ["tokyo", "japan", "sushi", "temple", "shibuya"],
        },
    },
    {
        "destination": "London",
        "expected": {
            "weather": True,
            "events": True,
            "event_venues": ["West End", "Borough", "British Museum"],
            "recommendation_keywords": ["london", "british", "thames", "museum", "tea"],
        },
    },
    {
        "destination": "Seattle",
        "expected": {
            "weather": True,
            "events": True,
            "event_venues": ["Pike Place", "Space Needle", "Capitol Hill"],
            "recommendation_keywords": ["seattle", "coffee", "pike", "space needle", "rain"],
        },
    },
]


def setup_telemetry():
    """Configure OpenTelemetry with optional Langfuse dual-send."""
    resource = Resource.create({
        "service.name": "eval-runner",
        "service.version": "1.0.0",
    })
    tracer_provider = TracerProvider(resource=resource)
    
    # Always send to AgentOps via OTLP
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True))
    )
    
    # Optionally dual-send to Langfuse
    if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
        try:
            from langfuse.opentelemetry import LangfuseSpanProcessor
            tracer_provider.add_span_processor(LangfuseSpanProcessor())
            print("✓ Langfuse dual-send enabled")
        except ImportError:
            print("⚠ Langfuse not installed, skipping dual-send")
    else:
        print("ℹ Langfuse keys not set, sending to AgentOps only")
    
    trace.set_tracer_provider(tracer_provider)
    return trace.get_tracer("eval-runner")


def score_response(response: dict, expected: dict, latency: float) -> dict:
    """Score a travel-planner response against expected outputs."""
    scores = {}
    exp = expected["expected"]
    dest = expected["destination"].lower()
    
    # Weather presence
    has_weather = response.get("weather") is not None
    scores["has_weather"] = has_weather
    scores["weather_correct"] = has_weather == exp["weather"]
    
    # Events presence and correctness
    events = response.get("events", [])
    has_events = len(events) > 0
    scores["has_events"] = has_events
    scores["events_correct"] = has_events == exp["events"]
    
    # Check event venues match expected city (not wrong city)
    if has_events and exp.get("event_venues"):
        event_text = " ".join(str(e) for e in events).lower()
        scores["events_from_correct_city"] = any(v.lower() in event_text for v in exp["event_venues"])
    else:
        scores["events_from_correct_city"] = not exp["events"]  # OK if we didn't expect events
    
    # Recommendation quality
    rec = response.get("recommendation", "").lower()
    scores["has_recommendation"] = len(rec) > 20
    scores["recommendation_mentions_destination"] = dest in rec
    
    # Check recommendation keywords
    if exp.get("recommendation_keywords"):
        keyword_matches = sum(1 for kw in exp["recommendation_keywords"] if kw in rec)
        scores["recommendation_relevant"] = keyword_matches >= 2
    else:
        scores["recommendation_relevant"] = True
    
    # Error checks
    scores["no_partial_failure"] = not response.get("partial", False)
    scores["no_errors"] = len(response.get("errors", [])) == 0
    
    # Latency
    scores["latency_under_5s"] = latency < 5.0
    
    # Overall pass: critical checks
    critical = [
        scores["weather_correct"],
        scores["events_correct"],
        scores["events_from_correct_city"],
        scores["has_recommendation"],
    ]
    scores["pass"] = all(critical)
    scores["score"] = sum(1 for v in scores.values() if v is True) / len(scores)
    
    return scores


def run_eval_case(tracer, test_case: dict) -> Optional[dict]:
    """Run a single eval case and record results."""
    destination = test_case["destination"]
    expected = test_case["expected"]
    
    with tracer.start_as_current_span(
        "eval.travel_planner",
        kind=SpanKind.CLIENT,
        attributes={
            "eval.dataset": "travel-planner-v1",
            "eval.destination": destination,
            "eval.expect_weather": expected["weather"],
            "eval.expect_events": expected["events"],
        },
    ) as span:
        try:
            start = time.time()
            resp = requests.post(
                f"{TRAVEL_PLANNER_URL}/plan",
                json={"destination": destination},
                timeout=30,
            )
            latency = time.time() - start
            
            span.set_attribute("eval.latency_ms", int(latency * 1000))
            span.set_attribute("eval.status_code", resp.status_code)
            
            if resp.status_code != 200:
                span.set_status(Status(StatusCode.ERROR, f"HTTP {resp.status_code}"))
                span.set_attribute("eval.pass", False)
                return None
            
            response = resp.json()
            scores = score_response(response, test_case, latency)
            
            # Record all scores as span attributes
            for key, value in scores.items():
                if isinstance(value, bool):
                    span.set_attribute(f"eval.{key}", value)
                elif isinstance(value, float):
                    span.set_attribute(f"eval.{key}", round(value, 3))
            
            if not scores["pass"]:
                span.set_status(Status(StatusCode.ERROR, "Eval failed"))
            
            return scores
            
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("eval.pass", False)
            span.set_attribute("eval.error", str(e)[:200])
            return None


def run_eval_suite(tracer) -> dict:
    """Run full eval suite and return summary."""
    with tracer.start_as_current_span(
        "eval.suite",
        kind=SpanKind.INTERNAL,
        attributes={
            "eval.suite_name": "travel-planner-v1",
            "eval.case_count": len(EVAL_DATASET),
        },
    ) as span:
        results = []
        passed = 0
        
        for test_case in EVAL_DATASET:
            scores = run_eval_case(tracer, test_case)
            if scores:
                results.append(scores)
                if scores["pass"]:
                    passed += 1
        
        pass_rate = passed / len(EVAL_DATASET) if EVAL_DATASET else 0
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        
        span.set_attribute("eval.passed", passed)
        span.set_attribute("eval.failed", len(EVAL_DATASET) - passed)
        span.set_attribute("eval.pass_rate", round(pass_rate, 3))
        span.set_attribute("eval.avg_score", round(avg_score, 3))
        
        if pass_rate < 1.0:
            span.set_status(Status(StatusCode.ERROR, f"Pass rate: {pass_rate:.0%}"))
        
        return {
            "passed": passed,
            "failed": len(EVAL_DATASET) - passed,
            "pass_rate": pass_rate,
            "avg_score": avg_score,
        }


def wait_for_service():
    """Wait for travel-planner to be ready."""
    print(f"Waiting for travel-planner at {TRAVEL_PLANNER_URL}...")
    for i in range(30):
        try:
            resp = requests.get(f"{TRAVEL_PLANNER_URL}/health", timeout=5)
            if resp.status_code == 200:
                print("✓ Travel planner is ready")
                return True
        except:
            pass
        time.sleep(2)
    print("✗ Travel planner not ready")
    return False


def main():
    print("=" * 50)
    print("Eval Runner - Travel Planner Evaluation")
    print("=" * 50)
    print(f"Target: {TRAVEL_PLANNER_URL}")
    print(f"OTLP Endpoint: {OTLP_ENDPOINT}")
    print(f"Eval Interval: {EVAL_INTERVAL}s")
    print(f"Test Cases: {len(EVAL_DATASET)}")
    print("=" * 50)
    
    tracer = setup_telemetry()
    
    if not wait_for_service():
        return
    
    print("\nStarting continuous evaluation...\n")
    
    while True:
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Running eval suite...")
            
            summary = run_eval_suite(tracer)
            
            status = "✓" if summary["pass_rate"] == 1.0 else "✗"
            print(f"[{timestamp}] {status} Pass: {summary['passed']}/{summary['passed'] + summary['failed']} "
                  f"({summary['pass_rate']:.0%}) Avg Score: {summary['avg_score']:.2f}")
            print()
            
            time.sleep(EVAL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\nEval runner stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(EVAL_INTERVAL)


if __name__ == "__main__":
    main()
