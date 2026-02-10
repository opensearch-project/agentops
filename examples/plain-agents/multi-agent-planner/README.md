# Multi-Agent Travel Planner

A multi-agent example demonstrating distributed agent orchestration with OpenTelemetry instrumentation, MCP (Model Context Protocol) tool calls, and fault injection.

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
                    └───┬───┘ └───┬───┘
                      :8000     :8002
                        │         │
                        └────┬────┘  [MCP tools/call]
                             ▼
                       ┌──────────┐
                       │mcp-server│
                       └──────────┘
                          :8004
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| travel-planner | 8003 | Orchestrator - fans out to sub-agents, synthesizes response |
| weather-agent | 8000 | Weather lookup via MCP + local tools (forecast) |
| events-agent | 8002 | Local events lookup via MCP |
| mcp-server | 8004 | MCP tool provider (fetch_weather_api, fetch_events_api) |
| canary | - | Periodic test client with fault injection |

## Features

- **Trace context propagation**: All 4 services share the same trace via W3C TraceContext headers
- **MCP semantic conventions**: Sub-agents call MCP server with proper CLIENT/SERVER span pairs
- **Local vs MCP tools**: Weather-agent uses both MCP tools and local tools (get_forecast)
- **Fault injection**: Test error handling at orchestrator and sub-agent levels
- **Graceful degradation**: Partial failures return available data with error details
- **Service map**: Shows 4 connected services in OpenSearch Dashboards

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

- **Trace Analytics**: See full request flow across all 4 services
- **Service Map**: Visualize service dependencies (travel-planner → weather/events → mcp-server)
- **Span attributes**:
  - `destination` - Requested city
  - `response.partial` - True if any sub-agent failed
  - `response.errors_count` - Number of failed sub-agents
  - `mcp.method.name` - MCP method (tools/call)
  - `mcp.session.id` - MCP session identifier
  - `gen_ai.tool.name` - Tool being executed

## Canary

The canary service automatically generates traffic with fault injection:

- Cycles through destinations: Paris, Tokyo, London, Berlin, Sydney, New York, Mumbai, Seattle
- Injects faults based on configured weights (50% normal, 50% various faults)
- Logs success rate and fault types

View canary logs:
```bash
docker compose logs -f canary
```

## Trace Structure

A typical trace shows the following span hierarchy:

```
travel-planner | invoke_agent (1745ms)
├── chat (113ms)                                    # Initial LLM "thinking"
├── invoke_agent weather-agent (1223ms)             # Sub-agent call
│   └── weather-agent | invoke_agent (1204ms)
│       └── execute_tool get_current_weather (196ms)
│           └── tools/call fetch_weather_api [CLIENT] (195ms)  # MCP call
│               └── mcp-server | tools/call [SERVER] (131ms)
│                   └── tool_call fetch_weather_api (131ms)
├── invoke_agent events-agent (270ms)               # Sub-agent call
│   └── events-agent | invoke_agent (244ms)
│       ├── chat (129ms)
│       └── tools/call fetch_events_api [CLIENT] (111ms)       # MCP call
│           └── mcp-server | tools/call [SERVER] (84ms)
│               └── tool_call fetch_events_api (84ms)
└── chat (108ms)                                    # Final response generation
```

**Span types:**
- `invoke_agent` - Agent invocation (orchestrator → sub-agent)
- `chat` - LLM call with token counts
- `execute_tool` - Tool execution wrapper
- `tools/call` - MCP protocol call (CLIENT/SERVER pair)
- `tool_call` - Actual tool execution in MCP server
- `local_tool` - Local tool execution (no MCP, e.g., get_forecast)
