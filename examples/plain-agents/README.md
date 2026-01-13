# Plain Python Agent Examples

This directory contains plain Python agent examples with OpenTelemetry instrumentation for the ATLAS observability stack.

## Examples

### Weather Agent

A simple weather assistant that demonstrates:
- OTLP exporter configuration for traces, metrics, and logs
- Gen-AI semantic convention attributes
- Tool execution tracing
- Token usage metrics

[View Weather Agent →](./weather-agent/)

## Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- ATLAS stack running (see [docker-compose README](../../docker-compose/README.md))

## Quick Start

1. Start the ATLAS stack:
```bash
cd ../../docker-compose
docker compose up -d
```

2. Run an example:
```bash
cd weather-agent
uv run python main.py
```

3. View telemetry data:
- OpenSearch Dashboards: http://localhost:5601
- Prometheus: http://localhost:9090

## Learn More

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [ATLAS Documentation](../../README.md)
