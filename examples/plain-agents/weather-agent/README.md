# Weather Agent - Plain Python Example

This example demonstrates how to instrument a plain Python AI agent with OpenTelemetry to send telemetry data to the Observability Stack, including fault injection for debugging scenarios.

## Features

- OTLP exporter configuration for traces, metrics, and logs
- Full Gen-AI semantic convention coverage (invoke_agent, execute_tool)
- Three weather tools: current, forecast, historical
- Fault injection for debugging demonstrations
- Structured logging with trace correlation
- Token usage metrics

## Tools

| Tool | Description | Example Query |
|------|-------------|---------------|
| `get_current_weather` | Current conditions | "What's the weather now?" |
| `get_forecast` | Multi-day forecast | "What's the forecast for next week?" |
| `get_historical_weather` | Past weather data | "What was the weather yesterday?" |

## Fault Injection

The agent supports fault injection via the `/invoke` API for testing observability:

| Fault Type | Description | HTTP Status |
|------------|-------------|-------------|
| `tool_timeout` | Tool execution times out | 504 |
| `tool_error` | Tool returns error | 502 |
| `rate_limited` | Model API rate limited | 429 |
| `token_limit_exceeded` | Response truncated | 200 |
| `hallucination` | Agent skips tool, fabricates answer | 200 |
| `wrong_tool` | Agent calls wrong tool for query | 200 |
| `high_latency` | Slow but successful response | 200 |

### Fault Injection Examples

```bash
# Normal request
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Paris?"}'

# Inject tool timeout
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in Tokyo?", "fault": {"type": "tool_timeout"}}'

# Inject hallucination (agent answers without calling tool)
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in London?", "fault": {"type": "hallucination"}}'

# Inject wrong tool (asks for current, gets forecast)
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Current weather in Berlin?", "fault": {"type": "wrong_tool"}}'

# Inject high latency with custom delay
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in NYC?", "fault": {"type": "high_latency", "delay_ms": 5000}}'
```

## Quick Start

1. Make sure the Observability Stack is running:
```bash
cd ../../../
docker compose up -d
```

2. The weather agent runs automatically as part of the stack. Test it:
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Paris?"}'
```

## View Telemetry Data

- **OpenSearch Dashboards**: http://localhost:5601
- **Prometheus**: http://localhost:9090

## Gen-AI Semantic Conventions

This agent implements the [OpenTelemetry Gen-AI Semantic Conventions](https://github.com/open-telemetry/semantic-conventions/tree/main/docs/gen-ai):

### invoke_agent Span
- `gen_ai.operation.name`: "invoke_agent"
- `gen_ai.agent.id`, `gen_ai.agent.name`, `gen_ai.agent.description`
- `gen_ai.request.model`, `gen_ai.response.model`
- `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- `gen_ai.system_instructions`, `gen_ai.tool.definitions`
- `gen_ai.input.messages`, `gen_ai.output.messages`

### execute_tool Span
- `gen_ai.operation.name`: "execute_tool"
- `gen_ai.tool.name`, `gen_ai.tool.description`, `gen_ai.tool.type`
- `gen_ai.tool.call.id`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`

## Code Structure

- `main.py`: Agent implementation with OpenTelemetry instrumentation and fault injection
- `server.py`: FastAPI server exposing the agent via REST API

## Development

After modifying the agent, rebuild and restart:
```bash
docker compose build --no-cache example-weather-agent
docker compose up -d example-weather-agent
```

## Learn More

- [OpenTelemetry Gen-AI Semantic Conventions](https://github.com/open-telemetry/semantic-conventions/tree/main/docs/gen-ai)
- [Fault Injection Design](../../../docs/fault-injection-design.md)
- [Observability Stack Documentation](../../../README.md)
