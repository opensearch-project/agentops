# Plain Python Agent Examples

This directory contains plain Python agent examples with OpenTelemetry instrumentation for the AgentOps observability stack.

## Examples

### Multi-Agent Travel Planner

A distributed multi-agent system demonstrating orchestration patterns:
- **travel-planner** (port 8003): Orchestrator that fans out to sub-agents
- **weather-agent** (port 8000): Weather lookup with fault injection
- **events-agent** (port 8002): Local events lookup

Features trace context propagation, fault injection, and graceful degradation.

[View Multi-Agent Planner →](./multi-agent-planner/)

### Weather Agent

A standalone weather assistant demonstrating full Gen-AI semantic convention coverage:
- Three tools: current weather, forecast, historical
- Fault injection for debugging scenarios
- OTLP traces, metrics, and logs
- Token usage metrics

[View Weather Agent →](./weather-agent/)

## Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- AgentOps stack running (see root [README](../../README.md))

## Quick Start

1. Start the AgentOps stack (includes all examples by default):
```bash
docker compose up -d
```

2. View telemetry data:
- OpenSearch Dashboards: http://localhost:5601
- Prometheus: http://localhost:9090

3. To run an example standalone:
```bash
cd weather-agent
uv run python main.py
```

## Learn More

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [AgentOps Documentation](../../README.md)
