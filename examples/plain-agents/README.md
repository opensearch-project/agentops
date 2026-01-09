# Python Agent Instrumentation Examples

This directory contains Python examples demonstrating how to instrument AI agent applications with OpenTelemetry to send telemetry data to the ATLAS observability stack.

## Overview

The examples show how to:
- Configure OTLP exporters for traces, metrics, and logs
- Implement gen-ai semantic convention attributes
- Instrument agent invocations with `invoke_agent` spans
- Instrument tool executions with `execute_tool` spans
- Add custom attributes for agent context
- Use structured logging with trace correlation
- Record token usage and operation duration metrics

## Prerequisites

1. **ATLAS Stack Running**: Ensure the ATLAS observability stack is running:
   ```bash
   cd ../../docker-compose
   docker-compose up -d
   ```

2. **Python 3.8+**: These examples require Python 3.8 or later

3. **Dependencies**: Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Examples

### weather_agent.py

A complete example of an AI agent that answers weather questions with full OpenTelemetry instrumentation.

**Features demonstrated:**
- OTLP exporter configuration (gRPC)
- Resource attributes for service identification
- `invoke_agent` spans with gen-ai semantic conventions
- `execute_tool` spans for tool execution tracing
- Span events for operation details
- Token usage metrics (counters)
- Operation duration metrics (histograms)
- Structured logging with trace correlation
- Error handling and exception recording

**Run the example:**
```bash
python weather_agent.py
```

**Expected output:**
```
Weather Agent Example - OpenTelemetry Instrumentation
============================================================

Setting up OpenTelemetry with OTLP exporters...
✓ OpenTelemetry configured

Creating Weather Agent...
✓ Agent created: Weather Assistant (ID: asst_weather_001)

User: What's the weather in Paris?

Invoking agent...
Agent: The weather in Paris is rainy with a temperature of 57°F.

Waiting for telemetry export...
✓ Telemetry exported to ATLAS stack

============================================================
Example complete!

View telemetry data:
  - OpenSearch Dashboards: http://localhost:5601
  - Prometheus: http://localhost:9090
```

## Viewing Telemetry Data

After running the examples, view the telemetry data in:

### OpenSearch Dashboards (http://localhost:5601)

1. **Discover Logs:**
   - Navigate to "Discover"
   - Select the logs index pattern
   - Filter by `service.name: weather-agent`
   - View structured logs with trace correlation

2. **Explore Traces:**
   - Navigate to "Observability" → "Traces"
   - View the complete trace hierarchy:
     - `invoke_agent Weather Assistant` (parent span)
       - `execute_tool get_weather` (child span)
   - Click on spans to see attributes and events

3. **View Span Attributes:**
   - `gen_ai.operation.name`: Operation type (invoke_agent, execute_tool)
   - `gen_ai.agent.id`: Agent identifier
   - `gen_ai.agent.name`: Agent name
   - `gen_ai.provider.name`: AI provider (openai)
   - `gen_ai.request.model`: Model requested
   - `gen_ai.response.model`: Actual model used
   - `gen_ai.usage.input_tokens`: Input token count
   - `gen_ai.usage.output_tokens`: Output token count
   - `gen_ai.tool.name`: Tool being executed

### Prometheus (http://localhost:9090)

1. **Query Token Usage:**
   ```promql
   gen_ai_client_token_usage_total{service_name="weather-agent"}
   ```

2. **Query Operation Duration:**
   ```promql
   gen_ai_client_operation_duration_bucket{service_name="weather-agent"}
   ```

3. **Calculate Average Duration:**
   ```promql
   rate(gen_ai_client_operation_duration_sum[5m]) / rate(gen_ai_client_operation_duration_count[5m])
   ```

## Gen-AI Semantic Conventions

These examples follow the OpenTelemetry Gen-AI Semantic Conventions for agent observability.

### Key Attributes

**Agent Attributes:**
- `gen_ai.agent.id`: Unique identifier for the agent
- `gen_ai.agent.name`: Human-readable agent name
- `gen_ai.agent.description`: Description of the agent's purpose

**Operation Attributes:**
- `gen_ai.operation.name`: Operation type (invoke_agent, execute_tool, chat)
- `gen_ai.provider.name`: AI provider (openai, anthropic, aws.bedrock, etc.)
- `gen_ai.conversation.id`: Conversation/session identifier

**Model Attributes:**
- `gen_ai.request.model`: Model requested (e.g., "gpt-4")
- `gen_ai.response.model`: Actual model used (e.g., "gpt-4-0613")
- `gen_ai.response.id`: Response identifier
- `gen_ai.response.finish_reasons`: Completion finish reasons

**Usage Attributes:**
- `gen_ai.usage.input_tokens`: Input token count
- `gen_ai.usage.output_tokens`: Output token count
- `gen_ai.token.type`: Token type (input or output) for metrics

**Tool Attributes:**
- `gen_ai.tool.name`: Name of the tool being executed
- `gen_ai.tool.description`: Description of the tool

### Span Types

**invoke_agent Span:**
- Represents a complete agent invocation
- Includes LLM calls and tool executions as child spans
- Records token usage and operation duration

**execute_tool Span:**
- Represents a single tool execution
- Child of invoke_agent span
- Includes tool input/output as span events

## Customization

### Changing OTLP Endpoint

Modify the `otlp_endpoint` parameter in `setup_telemetry()`:

```python
tracer, meter, logger = setup_telemetry(
    service_name="my-agent",
    service_version="1.0.0",
    otlp_endpoint="http://my-collector:4317"  # Change this
)
```

### Adding Custom Attributes

Add custom attributes to spans for additional context:

```python
span.set_attribute("custom.user.id", user_id)
span.set_attribute("custom.session.type", "interactive")
span.set_attribute("custom.agent.mode", "production")
```

### Adding Custom Metrics

Create additional metrics for your use case:

```python
# Counter for agent invocations
invocation_counter = meter.create_counter(
    name="agent.invocations",
    description="Number of agent invocations",
    unit="invocation"
)

# Histogram for tool execution duration
tool_duration = meter.create_histogram(
    name="agent.tool.duration",
    description="Tool execution duration",
    unit="s"
)
```

### Structured Logging

Add structured logs with custom fields:

```python
logger.info(
    "Custom event occurred",
    extra={
        "event.type": "user_feedback",
        "event.rating": 5,
        "gen_ai.agent.id": agent_id,
        "custom.field": "value"
    }
)
```

## Integration with Real Agents

To integrate this instrumentation with your real agent application:

1. **Install dependencies:**
   ```bash
   pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
   ```

2. **Set up telemetry at application startup:**
   ```python
   from opentelemetry import trace, metrics
   
   tracer, meter, logger = setup_telemetry(
       service_name="my-agent",
       service_version="1.0.0"
   )
   ```

3. **Wrap agent invocations:**
   ```python
   with tracer.start_as_current_span("invoke_agent MyAgent") as span:
       span.set_attribute("gen_ai.operation.name", "invoke_agent")
       span.set_attribute("gen_ai.agent.id", agent_id)
       # ... your agent logic
   ```

4. **Wrap tool executions:**
   ```python
   with tracer.start_as_current_span(f"execute_tool {tool_name}") as span:
       span.set_attribute("gen_ai.operation.name", "execute_tool")
       span.set_attribute("gen_ai.tool.name", tool_name)
       # ... your tool logic
   ```

5. **Record metrics:**
   ```python
   token_counter.add(
       token_count,
       attributes={
           "gen_ai.operation.name": "invoke_agent",
           "gen_ai.token.type": "input"
       }
   )
   ```

## Troubleshooting

### Connection Refused Error

If you see `Connection refused` errors:
1. Verify ATLAS stack is running: `docker-compose ps`
2. Check OpenTelemetry Collector is accessible: `curl http://localhost:4317`
3. Verify port 4317 is exposed in docker-compose.yml

### No Data in OpenSearch Dashboards

If telemetry data doesn't appear:
1. Check OpenTelemetry Collector logs: `docker-compose logs otel-collector`
2. Check Data Prepper logs: `docker-compose logs data-prepper`
3. Verify indices exist: `curl http://localhost:9200/_cat/indices?v`
4. Wait a few seconds for data to be processed and indexed

### No Metrics in Prometheus

If metrics don't appear:
1. Check Prometheus targets: http://localhost:9090/targets
2. Verify OTLP endpoint is configured correctly
3. Check OpenTelemetry Collector metrics pipeline configuration

## Additional Resources

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
- [ATLAS Repository](../../README.md)

## Next Steps

- Explore JavaScript/TypeScript examples in `../javascript/`
- Check out agent framework integrations in `../frameworks/`
- Create custom dashboards in OpenSearch Dashboards
- Set up alerts based on agent metrics
