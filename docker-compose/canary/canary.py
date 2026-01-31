#!/usr/bin/env python3
"""
Canary Service - Periodic Travel Planner Invocation with Fault Injection
"""

import json
import os
import random
import time
import requests
from datetime import datetime


TRAVEL_PLANNER_URL = os.getenv("TRAVEL_PLANNER_URL", "http://travel-planner:8000")
CANARY_INTERVAL = int(os.getenv("CANARY_INTERVAL", "30"))

DESTINATIONS = ["Paris", "Tokyo", "London", "Berlin", "Sydney", "New York", "Mumbai", "Seattle"]

# Fault weights
DEFAULT_FAULT_WEIGHTS = {
    "none": 0.50,
    "weather_error": 0.10,
    "weather_rate_limited": 0.08,
    "weather_high_latency": 0.07,
    "events_error": 0.08,
    "events_rate_limited": 0.07,
    "partial_failure": 0.10,
}
FAULT_WEIGHTS = json.loads(os.getenv("FAULT_WEIGHTS", json.dumps(DEFAULT_FAULT_WEIGHTS)))

# Map fault names to config
FAULT_CONFIGS = {
    "none": None,
    "weather_error": {"weather": {"type": "tool_error"}},
    "weather_rate_limited": {"weather": {"type": "rate_limited"}},
    "weather_high_latency": {"weather": {"type": "high_latency", "delay_ms": 3000}},
    "events_error": {"events": {"type": "error"}},
    "events_rate_limited": {"events": {"type": "rate_limited"}},
    "partial_failure": {"orchestrator": "partial_failure"},
}


def select_fault():
    fault_types = list(FAULT_WEIGHTS.keys())
    weights = list(FAULT_WEIGHTS.values())
    selected = random.choices(fault_types, weights=weights, k=1)[0]
    return selected, FAULT_CONFIGS.get(selected)


def check_health():
    try:
        response = requests.get(f"{TRAVEL_PLANNER_URL}/health", timeout=5)
        response.raise_for_status()
        print(f"✓ Travel planner is healthy")
        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False


def invoke_planner(destination: str, fault_name: str, fault_config: dict):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        payload = {"destination": destination}
        if fault_config:
            payload["fault"] = fault_config

        print(f"[{timestamp}] {destination} (fault: {fault_name})")

        response = requests.post(f"{TRAVEL_PLANNER_URL}/plan", json=payload, timeout=60)
        data = response.json()

        if response.status_code == 200:
            status = "partial" if data.get("partial") else "ok"
            events_count = len(data.get("events", []))
            print(f"         → {status}, {events_count} events")
            return True
        else:
            print(f"         → error: {response.status_code}")
            return False

    except Exception as e:
        print(f"         → failed: {e}")
        return False


def main():
    print("=" * 50)
    print("Canary - Travel Planner with Fault Injection")
    print(f"URL: {TRAVEL_PLANNER_URL}")
    print(f"Interval: {CANARY_INTERVAL}s")
    print("=" * 50)

    # Wait for service
    for i in range(30):
        if check_health():
            break
        time.sleep(2)
    else:
        print("✗ Service not ready")
        return

    print("\nStarting invocations...\n")
    count, success = 0, 0

    while True:
        try:
            count += 1
            destination = random.choice(DESTINATIONS)
            fault_name, fault_config = select_fault()

            if invoke_planner(destination, fault_name, fault_config):
                success += 1

            print(f"         Success: {success}/{count} ({100*success/count:.0f}%)\n")
            
            # Sleep after first invocation (not before) so data appears immediately on startup
            time.sleep(CANARY_INTERVAL)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(CANARY_INTERVAL)


if __name__ == "__main__":
    main()
