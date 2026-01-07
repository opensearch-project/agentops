# Multi-Agent Travel Planner

A multi-agent example demonstrating distributed agent orchestration with OpenTelemetry instrumentation and fault injection.

## Architecture

```
                    ┌─────────────────┐
     Canary ──────▶ │ travel-planner  │ :8003
                    └────────┬────────┘
                             │
                        ┌────┴────┐  [fan-out]
                        ▼         ▼
                    ┌───────┐ ┌───────┐
                    │weather│ │events │
                    │ agent │ │ agent │
                    └───────┘ └───────┘
                      :8000     :8002
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| travel-planner | 8003 | Orchestrator - fans out to sub-agents, synthesizes response |
| weather-agent | 8000 | Weather lookup (simulated) |
| events-agent | 8002 | Local events lookup (simulated) |
| canary | - | Periodic test client with fault injection |

## Features

- **Trace context propagation**: All services share the same trace via W3C TraceContext headers
- **Fault injection**: Test error handling at orchestrator and sub-agent levels
- **Graceful degradation**: Partial failures return available data with error details
- **Service map**: Shows 3 connected services in OpenSearch Dashboards

## Running

From repository root:

```bash
docker compose up -d
```

The multi-agent planner starts automatically with the example services.

## API

### POST /plan

```bash
curl -X POST http://localhost:8003/plan \
  -H "Content-Type: application/json" \
  -d '{"destination": "Paris"}'
```

Response:
```json
{
  "destination": "Paris",
  "weather": {"response": "The weather in Paris is sunny..."},
  "events": [{"name": "Louvre Late Night", "type": "museum", "venue": "Louvre Museum"}],
  "recommendation": "Great choice! Paris looks wonderful...",
  "partial": false,
  "errors": []
}
```

### Fault Injection

Inject faults to test error handling:

```bash
# Sub-agent fault (events-agent returns error)
curl -X POST http://localhost:8003/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Paris",
    "fault": {
      "events": {"type": "error"}
    }
  }'

# Orchestrator fault (random partial failure)
curl -X POST http://localhost:8003/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Paris",
    "fault": {
      "orchestrator": "partial_failure"
    }
  }'
```

#### Available Faults

**Sub-agent faults** (weather/events):
- `error` - Returns an error response
- `rate_limited` - Simulates rate limiting
- `high_latency` - Adds delay (use `delay_ms` parameter)
- `timeout` - Simulates timeout

**Orchestrator faults**:
- `partial_failure` - Randomly skip one sub-agent call

## Telemetry

View in OpenSearch Dashboards (http://localhost:5601):

- **Trace Analytics**: See full request flow across all 3 services
- **Service Map**: Visualize service dependencies
- **Span attributes**:
  - `destination` - Requested city
  - `response.partial` - True if any sub-agent failed
  - `response.errors_count` - Number of failed sub-agents
  - `status.code` - 2 (ERROR) for partial failures

## Canary

The canary service automatically generates traffic with fault injection:

- Cycles through destinations: Paris, Tokyo, London, Berlin, Sydney, New York, Mumbai, Seattle
- Injects faults based on configured weights (50% normal, 50% various faults)
- Logs success rate and fault types

View canary logs:
```bash
docker compose logs -f canary
```
