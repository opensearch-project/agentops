# Weather Agent - Plain Python Example

This example demonstrates how to instrument a plain Python AI agent with OpenTelemetry to send telemetry data to the AgentOps observability stack.

## Features

- OTLP exporter configuration for traces, metrics, and logs
- Gen-AI semantic convention attributes (invoke_agent, execute_tool)
- Custom attributes for agent context
- Structured logging with trace correlation
- Tool execution tracing
- Token usage metrics

## Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- AgentOps stack running (see [docker-compose README](../../../docker-compose/README.md))

## Quick Start

1. Make sure the AgentOps stack is running:
```bash
cd ../../../docker-compose
docker compose up -d
```

2. Run the weather agent (choose one):

**Option A: Direct execution**
```bash
uv run python main.py
```

**Option B: API Server**
```bash
uv run python server.py
```

The API server will start on `http://localhost:8000`. You can then invoke the agent via REST API:

```bash
# Health check
curl http://localhost:8000/health

# Invoke agent
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Paris?"}'
```

The agent will:
- Set up OpenTelemetry with OTLP exporters
- Process weather queries
- Send traces, metrics, and logs to the AgentOps stack

## View Telemetry Data

After running the agent, view the telemetry data:

- **OpenSearch Dashboards**: http://localhost:5601
- **Prometheus**: http://localhost:9090

## What's Happening

The weather agent demonstrates:

1. **Agent Invocation**: Creates an `invoke_agent` span with gen-ai semantic conventions
2. **Tool Execution**: Creates an `execute_tool` span for the weather API call
3. **Metrics**: Records token usage and operation duration
4. **Logs**: Structured logging with trace correlation

## Code Structure

- `main.py`: Main agent implementation with OpenTelemetry instrumentation
- `server.py`: FastAPI server that exposes the agent through REST API

## Customization

You can customize the agent by:

- Changing the OTLP endpoint in `setup_telemetry()` (default: `http://localhost:4317`)
- Adding more tools to the agent
- Modifying the agent's behavior and responses
- Adding custom attributes and metrics

## Learn More

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [AgentOps Documentation](../../../README.md)
