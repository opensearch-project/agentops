#!/usr/bin/env python3
"""
Canary Service - Periodic Weather Agent Invocation

This service periodically invokes the weather-agent API to generate
telemetry data for testing and demonstration purposes.
"""

import os
import time
import random
import requests
from datetime import datetime


# Configuration from environment variables
WEATHER_AGENT_URL = os.getenv("WEATHER_AGENT_URL", "http://weather-agent:8000")
CANARY_INTERVAL = int(os.getenv("CANARY_INTERVAL", "30"))

# Sample weather queries for variety
SAMPLE_QUERIES = [
    "What's the weather in Paris?",
    "How's the weather in Tokyo?",
    "Tell me the weather in New York",
    "What's the weather like in London?",
    "Is it raining in Seattle?",
    "What's the temperature in Berlin?",
    "How's the weather in Sydney?",
    "What's the weather in Mumbai?",
]


def check_health():
    """Check if the weather-agent is healthy"""
    try:
        response = requests.get(f"{WEATHER_AGENT_URL}/health", timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"✓ Weather agent is healthy: {data['agent_name']}")
        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False


def invoke_agent(message: str):
    """Invoke the weather agent with a message"""
    try:
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] Invoking agent: {message}")

        response = requests.post(
            f"{WEATHER_AGENT_URL}/invoke",
            json={"message": message},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        print(f"[{timestamp}] Response: {data['response']}")
        print(f"[{timestamp}] Conversation ID: {data['conversation_id']}")
        return True

    except Exception as e:
        print(f"✗ Invocation failed: {e}")
        return False


def main():
    """Main canary loop"""
    print("=" * 60)
    print("Canary Service - Weather Agent Testing")
    print("=" * 60)
    print(f"Weather Agent URL: {WEATHER_AGENT_URL}")
    print(f"Invocation Interval: {CANARY_INTERVAL} seconds")
    print("=" * 60)
    print()

    # Wait for weather-agent to be ready
    print("Waiting for weather-agent to be ready...")
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        if check_health():
            print("✓ Weather agent is ready")
            break
        retry_count += 1
        print(f"Retrying in 2 seconds... ({retry_count}/{max_retries})")
        time.sleep(2)
    else:
        print("✗ Weather agent failed to become ready. Exiting.")
        return

    print()
    print("Starting periodic invocations...")
    print()

    # Main loop - periodically invoke the agent
    invocation_count = 0
    success_count = 0

    while True:
        try:
            invocation_count += 1
            message = random.choice(SAMPLE_QUERIES)

            print(f"--- Invocation #{invocation_count} ---")
            if invoke_agent(message):
                success_count += 1

            success_rate = (success_count / invocation_count) * 100
            print(f"Success rate: {success_rate:.1f}% "
                  f"({success_count}/{invocation_count})")
            print()

            # Wait for next invocation
            time.sleep(CANARY_INTERVAL)

        except KeyboardInterrupt:
            print()
            print("Canary service stopped by user")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(CANARY_INTERVAL)


if __name__ == "__main__":
    main()
