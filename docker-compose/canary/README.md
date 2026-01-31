# Canary Service

The canary service is a periodic test client that invokes the weather-agent API to generate continuous telemetry data, including fault injection scenarios for testing observability and debugging workflows.

## Purpose

- Validates the observability pipeline end-to-end
- Generates synthetic agent traffic with realistic fault patterns
- Provides telemetry data for debugging demonstrations
- Monitors weather-agent availability and success rate

## Files

- `canary.py`: Main canary implementation with fault injection
- `Dockerfile`: Container build configuration

## Configuration

Environment variables (set in `../.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `CANARY_INTERVAL` | 30 | Seconds between invocations |
| `WEATHER_AGENT_URL` | `http://weather-agent:8000` | Weather agent endpoint |
| `FAULT_WEIGHTS` | See below | JSON object with fault probabilities |

### Fault Weights

Default distribution (configurable via `FAULT_WEIGHTS` env var):

```json
{
  "none": 0.55,
  "high_latency": 0.1,
  "tool_timeout": 0.07,
  "tool_error": 0.07,
  "token_limit_exceeded": 0.05,
  "rate_limited": 0.04,
  "hallucination": 0.04,
  "wrong_tool": 0.08
}
```

## Fault Types

| Fault | Description | Telemetry Signal |
|-------|-------------|------------------|
| `none` | Normal request | Successful spans |
| `high_latency` | 3s delay, succeeds | Long duration spans |
| `tool_timeout` | Tool execution times out | `error.type: timeout` on tool span |
| `tool_error` | Tool returns 503 | `error.type: tool_error` on tool span |
| `token_limit_exceeded` | Response truncated | `finish_reasons: ["length"]` |
| `rate_limited` | Model API 429 | `error.type: rate_limit_exceeded` |
| `hallucination` | Skips tool, fabricates answer | No child `execute_tool` span |
| `wrong_tool` | Calls wrong tool for query | Tool name doesn't match query intent |

## Sample Queries

The canary randomly selects from queries covering all three tools:

**Current Weather:**
- "What's the weather in Paris?"
- "What's the temperature in Berlin?"

**Forecast:**
- "What's the forecast for Seattle?"
- "What will the weather be like tomorrow in NYC?"

**Historical:**
- "What was the weather yesterday in Mumbai?"
- "How was the weather last week in Chicago?"

## Usage

The canary runs by default with the stack:

```bash
docker compose up -d
```

View logs:
```bash
docker compose logs -f canary
```

Override fault weights:
```bash
FAULT_WEIGHTS='{"none": 0.9, "tool_timeout": 0.1}' docker compose up -d canary
```

## Investigating Faults

### Find Error Spans
```bash
curl -s -k -u admin:'My_password_123!@#' \
  'https://localhost:9200/otel-v1-apm-span-*/_search' \
  -H "Content-Type: application/json" \
  -d '{"query": {"term": {"status.code": 2}}}' | jq '.hits.hits[]._source.attributes.error_type'
```

### Find Hallucinations (no tool span)
Look for `invoke_agent` spans with no child `execute_tool` spans.

### Find Wrong Tool Calls
Compare `gen_ai.input.messages` (user query) with `gen_ai.tool.name` (tool called).

## Modifying

After editing `canary.py`, rebuild and restart:

```bash
docker compose build --no-cache example-canary
docker compose up -d example-canary
```
