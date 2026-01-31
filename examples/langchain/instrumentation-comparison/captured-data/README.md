# Instrumentation Library Comparison - Captured Data

This directory contains real span data captured from 4 different instrumentation approaches,
all sending telemetry to the AgentOps stack via OTLP.

## Test Setup

All examples run the same LangChain weather agent with Bedrock Claude, executing 3 queries:
1. "What's the current weather in Seattle?"
2. "What's the forecast for Tokyo for the next 3 days?"
3. "What was the weather like in London yesterday?"

## Attribute Comparison (Actual Captured Data)

### Model Name
| Library | Attribute | Value |
|---------|-----------|-------|
| OpenLLMetry | `gen_ai.request.model` | `"unknown"` ❌ |
| OpenLLMetry | `traceloop.association.properties.ls_model_name` | `"us.anthropic.claude-sonnet-4-20250514-v1:0"` ✅ |
| OpenInference | `llm.model_name` | `"us.anthropic.claude-sonnet-4-20250514-v1:0"` ✅ |
| Langfuse-style | `gen_ai.request.model` | `"us.anthropic.claude-sonnet-4-20250514-v1:0"` ✅ |
| Braintrust-style | `gen_ai.request.model` | `"us.anthropic.claude-sonnet-4-20250514-v1:0"` ✅ |

### Token Usage
| Library | Input Tokens Attr | Output Tokens Attr |
|---------|-------------------|-------------------|
| OpenLLMetry | `gen_ai.usage.input_tokens` | `gen_ai.usage.output_tokens` |
| OpenInference | `llm.token_count.prompt` | `llm.token_count.completion` |
| Langfuse-style | `gen_ai.usage.input_tokens` | `gen_ai.usage.output_tokens` |
| Braintrust-style | `braintrust.metrics.prompt_tokens` | `braintrust.metrics.completion_tokens` |

### Provider/System
| Library | Attribute | Value |
|---------|-----------|-------|
| OpenLLMetry | `gen_ai.system` | `"AWS"` |
| OpenLLMetry | `traceloop.association.properties.ls_provider` | `"amazon_bedrock"` |
| OpenInference | `llm.provider` | `"amazon_bedrock"` |
| Langfuse-style | `gen_ai.system` | `"langchain"` |
| Braintrust-style | `gen_ai.system` | `"langchain"` |

### Input/Output
| Library | Input Attribute | Output Attribute |
|---------|-----------------|------------------|
| OpenLLMetry | `gen_ai.completion.0.role/content` | (flattened array) |
| OpenInference | `input.value` (JSON) | `output.value` (JSON) |
| OpenInference | `llm.input_messages.*.message.*` | `llm.output_messages.*.message.*` |
| Langfuse-style | `langfuse.observation.input` | `langfuse.observation.output` |
| Braintrust-style | `braintrust.input` | `braintrust.output` |

### Vendor-Specific Attributes

#### Langfuse Namespace (`langfuse.*`)
```json
{
  "langfuse.trace.name": "weather_agent_query",
  "langfuse.user.id": "test-user-123",
  "langfuse.session.id": "test-session-456",
  "langfuse.trace.tags": "weather,langchain,comparison-test",
  "langfuse.trace.metadata.source": "instrumentation-comparison",
  "langfuse.observation.input": "...",
  "langfuse.observation.output": "..."
}
```

#### Braintrust Namespace (`braintrust.*`)
```json
{
  "braintrust.input": "...",
  "braintrust.output": "...",
  "braintrust.metadata.source": "instrumentation-comparison",
  "braintrust.tags": ["weather", "langchain", "comparison-test"],
  "braintrust.metrics.prompt_tokens": 150,
  "braintrust.metrics.completion_tokens": 50
}
```

#### OpenLLMetry/Traceloop Namespace (`traceloop.*`)
```json
{
  "traceloop.workflow.name": "RunnableSequence",
  "traceloop.entity.path": "",
  "traceloop.association.properties.ls_model_name": "us.anthropic.claude-sonnet-4-20250514-v1:0",
  "traceloop.association.properties.ls_provider": "amazon_bedrock",
  "traceloop.association.properties.ls_model_type": "chat",
  "traceloop.association.properties.ls_temperature": 0.0
}
```

#### OpenInference Namespace (`openinference.*`, `llm.*`)
```json
{
  "openinference.span.kind": "LLM",
  "llm.model_name": "us.anthropic.claude-sonnet-4-20250514-v1:0",
  "llm.provider": "amazon_bedrock",
  "llm.token_count.prompt": 714,
  "llm.token_count.completion": 104,
  "llm.token_count.total": 818
}
```

## Migration Implications

### From Langfuse → AgentOps
- **Zero friction** if using OpenLLMetry/OpenLIT (just change OTLP endpoint)
- **Minimal friction** if using Langfuse SDK v3 (OTEL-native, change endpoint)
- **Data Prepper transformation needed** to map `langfuse.*` attributes to GenAI SemConv

### From Braintrust → AgentOps
- **Zero friction** if using OpenLLMetry (just change OTLP endpoint)
- **Minimal friction** if using Braintrust SDK (change to standard OTLP exporter)
- **Data Prepper transformation needed** to map `braintrust.*` attributes to GenAI SemConv

## Files

- `openllmetry-span.json` - Full span from OpenLLMetry instrumentation
- `openinference-span.json` - Full span from OpenInference instrumentation
- `langfuse-span.json` - Full span with Langfuse-style attributes
- `braintrust-span.json` - Full span with Braintrust-style attributes
