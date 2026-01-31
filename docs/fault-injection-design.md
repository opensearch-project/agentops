# Fault Injection Design

## Overview

Add fault injection capabilities to weather-agent to simulate debugging scenarios, controlled via API input and exercised by canary service.

## Goals

1. Demonstrate observability value during failure scenarios
2. Cover `error.type` and error-related GenAI SemConv attributes
3. Generate realistic failure telemetry for dashboard development
4. Enable chaos testing patterns

## API Design

### Request Schema

```python
POST /invoke
{
  "message": "What's the weather in Paris?",
  "fault": {                          # optional
    "type": "tool_timeout",           # required if fault specified
    "delay_ms": 5000,                 # optional: inject latency before/during fault
    "probability": 1.0,               # optional: 0.0-1.0, default 1.0 (always)
    "tool": "get_weather"             # optional: target specific tool
  }
}
```

### Response (on fault)

```python
{
  "response": null,
  "error": {
    "type": "tool_timeout",
    "message": "Tool 'get_weather' timed out after 30000ms"
  },
  "conversation_id": "conv-xxx",
  "trace_id": "abc123"
}
```

## Fault Types

### Phase 1 - Core Scenarios

| Fault Type | Description | Span Attributes |
|------------|-------------|-----------------|
| `token_limit_exceeded` | Response truncated due to max tokens | `gen_ai.response.finish_reasons: ["length"]` |
| `tool_timeout` | Tool execution times out | `error.type: "timeout"` on tool span |
| `tool_error` | Tool returns error | `error.type: "tool_error"`, tool span status ERROR |
| `rate_limited` | Model API rate limited | `error.type: "rate_limit_exceeded"` |
| `high_latency` | Slow but successful response | Normal attributes, just delayed |
| `hallucination` | Agent returns fabricated data | `gen_ai.output.type: "text"` (no tool call made) |

### Phase 2 - Advanced Scenarios

| Fault Type | Description | Span Attributes |
|------------|-------------|-----------------|
| `content_filtered` | Safety filter triggered | `gen_ai.response.finish_reasons: ["content_filter"]` |
| `max_iterations` | Agent loop limit reached | `error.type: "max_iterations_exceeded"` |
| `malformed_response` | Unparseable model output | `error.type: "parse_error"` |
| `partial_failure` | Some tools succeed, others fail | Mixed span statuses |
| `context_overflow` | Input too long | `error.type: "context_length_exceeded"` |

## Implementation

### Weather Agent Changes

```python
# main.py - Add to WeatherAgent class

class FaultConfig:
    type: str
    delay_ms: int = 0
    probability: float = 1.0
    tool: str | None = None

def _should_inject_fault(self, fault: FaultConfig) -> bool:
    return random.random() < fault.probability

def _inject_fault(self, fault: FaultConfig, span: Span) -> None:
    if fault.delay_ms:
        time.sleep(fault.delay_ms / 1000)
    
    match fault.type:
        case "token_limit_exceeded":
            self._fault_token_limit(span)
        case "tool_timeout":
            self._fault_tool_timeout(span, fault.tool)
        case "tool_error":
            self._fault_tool_error(span, fault.tool)
        case "rate_limited":
            self._fault_rate_limited(span)
        case "high_latency":
            pass  # delay already applied
        case "hallucination":
            self._fault_hallucination(span)
```

### Fault Implementations

```python
def _fault_token_limit(self, span: Span) -> AgentResponse:
    """Simulate response truncated due to token limit."""
    span.set_attribute("gen_ai.response.finish_reasons", ["length"])
    span.set_attribute("gen_ai.usage.output_tokens", 1024)  # hit limit
    truncated = "The weather in Paris is currently 18°C with partly cloudy skies. The forecast for the next few days shows—"
    return AgentResponse(response=truncated, truncated=True)

def _fault_tool_timeout(self, span: Span, tool: str) -> None:
    """Simulate tool execution timeout."""
    span.set_status(StatusCode.ERROR, "Tool execution timed out")
    span.set_attribute("error.type", "timeout")
    raise ToolTimeoutError(f"Tool '{tool or 'get_weather'}' timed out after 30000ms")

def _fault_tool_error(self, span: Span, tool: str) -> None:
    """Simulate tool returning an error."""
    span.set_status(StatusCode.ERROR, "Tool execution failed")
    span.set_attribute("error.type", "tool_error")
    raise ToolExecutionError(f"Tool '{tool or 'get_weather'}' failed: External API returned 503")

def _fault_rate_limited(self, span: Span) -> None:
    """Simulate model API rate limiting."""
    span.set_status(StatusCode.ERROR, "Rate limit exceeded")
    span.set_attribute("error.type", "rate_limit_exceeded")
    raise RateLimitError("Rate limit exceeded. Retry after 60 seconds.")

def _fault_hallucination(self, span: Span) -> AgentResponse:
    """Simulate agent hallucinating without calling tools."""
    # Don't call any tools, just return fabricated data
    span.set_attribute("gen_ai.output.type", "text")
    # No tool spans created - agent "knew" the answer
    return AgentResponse(
        response="The weather in Paris is 22°C and sunny with light winds from the northwest.",
        hallucinated=True
    )
```

### Server Changes

```python
# server.py - Update invoke endpoint

class InvokeRequest(BaseModel):
    message: str
    fault: FaultConfig | None = None

@app.post("/invoke")
async def invoke(request: InvokeRequest):
    try:
        result = agent.invoke(request.message, fault=request.fault)
        return {"response": result.response, "conversation_id": result.conversation_id}
    except AgentError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "response": None,
                "error": {"type": e.error_type, "message": str(e)},
                "conversation_id": e.conversation_id,
                "trace_id": e.trace_id
            }
        )
```

### Canary Changes

```python
# canary.py - Add fault injection scenarios

FAULT_SCENARIOS = [
    None,  # normal request (baseline)
    {"type": "high_latency", "delay_ms": 3000},
    {"type": "tool_timeout"},
    {"type": "tool_error"},
    {"type": "token_limit_exceeded"},
    {"type": "rate_limited"},
    {"type": "hallucination"},
]

async def run_scenario():
    fault = random.choice(FAULT_SCENARIOS)
    message = random.choice(WEATHER_QUERIES)
    
    response = await client.post("/invoke", json={
        "message": message,
        "fault": fault
    })
    
    # Log scenario result for observability
    logger.info(
        "Scenario completed",
        extra={
            "fault_type": fault["type"] if fault else "none",
            "status_code": response.status_code,
            "success": response.status_code == 200
        }
    )
```

## Telemetry Examples

### Successful Request (Baseline)
```
invoke_agent Weather Assistant [OK]
  └── execute_tool get_weather [OK]
```

### Token Limit Exceeded
```
invoke_agent Weather Assistant [OK]
  ├── execute_tool get_weather [OK]
  └── attributes:
        gen_ai.response.finish_reasons: ["length"]
        gen_ai.usage.output_tokens: 1024
```

### Tool Timeout
```
invoke_agent Weather Assistant [ERROR]
  └── execute_tool get_weather [ERROR]
        error.type: "timeout"
        duration: 30000ms
```

### Hallucination
```
invoke_agent Weather Assistant [OK]
  └── (no tool spans - agent didn't call tools)
      gen_ai.output.type: "text"
```

## Testing

### Manual Testing
```bash
# Normal request
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in Tokyo?"}'

# Inject tool timeout
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in Tokyo?", "fault": {"type": "tool_timeout"}}'

# Inject high latency
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in Tokyo?", "fault": {"type": "high_latency", "delay_ms": 5000}}'
```

### Canary Automated Testing
Canary will cycle through scenarios automatically, generating mixed telemetry for dashboard development.

## Dashboard Queries

### Error Rate by Type
```sql
SELECT error.type, COUNT(*) 
FROM spans 
WHERE serviceName = 'weather-agent-api' 
GROUP BY error.type
```

### Latency Distribution
```sql
SELECT 
  PERCENTILE(durationInNanos/1000000, 50) as p50_ms,
  PERCENTILE(durationInNanos/1000000, 95) as p95_ms,
  PERCENTILE(durationInNanos/1000000, 99) as p99_ms
FROM spans
WHERE name LIKE 'invoke_agent%'
```

### Hallucination Detection
```sql
SELECT * FROM spans
WHERE name LIKE 'invoke_agent%'
  AND attributes.gen_ai.output.type = 'text'
  AND NOT EXISTS (
    SELECT 1 FROM spans child 
    WHERE child.parentSpanId = spans.spanId 
    AND child.name LIKE 'execute_tool%'
  )
```

## Rollout Plan

### Phase 1 ✅ COMPLETE
1. ✅ Add FaultConfig model to server.py
2. ✅ Implement core 6 fault types in main.py
3. ✅ Update canary to cycle through scenarios with weighted selection
4. ✅ Test manually and verify telemetry

### Phase 2
1. Add advanced fault types (content_filtered, max_iterations, malformed_response, partial_failure, context_overflow)
2. Add probabilistic fault injection
3. Add fault targeting (specific tools)
4. Create dashboard templates for fault analysis

## Open Questions

1. ~~Should faults be injectable via HTTP headers instead of body?~~ **Decision: Use body**
2. ~~Should we add a `/faults` endpoint to list available fault types?~~ **Decision: Skip, document in README**
3. ~~Should canary have configurable fault distribution weights?~~ **Decision: Yes, via FAULT_WEIGHTS env var**

## Changelog

- 2026-01-26: Phase 1 implementation complete
- 2026-01-26: Initial design
