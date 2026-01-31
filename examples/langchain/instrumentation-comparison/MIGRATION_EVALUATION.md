# Customer Migration Evaluation

Strategy document for evaluating customer setups and scoping migration effort to AgentOps.

## Executive Summary

| Customer Situation | Tracing Effort | Eval Effort | Key Risk |
|---|---|---|---|
| Currently on Langfuse | **Zero** | **High** ⚠️ | Scores via separate API, not OTLP |
| Currently on Braintrust | **Minimal** | **Minimal** | None—scores in OTLP via `braintrust.scores.*` |
| Currently on Arize Phoenix | **Low** | **High** ⚠️ | Evals stored in Phoenix DB, not OTLP |

**Bottom Line:** Tracing migration is straightforward for all platforms (endpoint change). Evaluation migration varies significantly—only Braintrust sends scores via OTLP.

---

## Customer Assessment Framework

### By Current Platform

| Platform | What Changes | Tracing | Evals | Notes |
|---|---|---|---|---|
| **Langfuse** | OTLP endpoint only | Zero effort | **Export from Langfuse DB** | Scores via separate API, not in OTLP stream |
| **Braintrust** | Replace `BraintrustSpanProcessor` with `OTLPSpanExporter` | Minimal effort | Transform `braintrust.scores.*` → `gen_ai.eval.*` | Token counts need normalization |
| **Phoenix** | OTLP endpoint + Data Prepper transforms | Low effort | **Custom solution required** | Evals not in OTLP |

### By Instrumentation Library

| Library | Maintainer | GenAI SemConv Aligned | Transform Required | Framework Gaps |
|---|---|---|---|---|
| **Manual OTel** | N/A | ✅ Baseline | No | N/A |
| **OTel Contrib GenAI** | OpenTelemetry Project | ✅ Full | No | Bedrock, LlamaIndex, CrewAI |
| **OpenLLMetry** | Traceloop | ✅ High | Model name fix only | None |
| **OpenInference** | Arize AI | ⚠️ No (`llm.*`) | Full attribute remap | Haystack |

### Framework Coverage Matrix

| Framework | OTel Contrib | OpenLLMetry | OpenInference |
|---|---|---|---|
| OpenAI SDK | ✅ | ✅ | ✅ |
| Anthropic SDK | ✅ | ✅ | ✅ |
| AWS Bedrock | ❌ | ✅ | ✅ |
| LangChain | ✅ (unreleased) | ✅ | ✅ |
| LlamaIndex | ❌ | ✅ | ✅ |
| CrewAI | ❌ | ✅ | ✅ |
| Haystack | ❌ | ✅ | ❌ |
| Guardrails | ❌ | ❌ | ✅ |

---

## Gap Analysis

### What Works Today

- ✅ OTLP ingestion from Langfuse, Braintrust, Phoenix
- ✅ Tracing with minimal/no code changes
- ✅ GenAI SemConv attributes from OTel Contrib and OpenLLMetry
- ✅ Vendor-specific attributes preserved (queryable in OpenSearch)

### What Requires Work

| Gap | Effort | Solution |
|---|---|---|
| **Langfuse evals** | High | Export from Langfuse DB or call Langfuse Scores API |
| **Phoenix evals** | High | Custom instrumentation or Phoenix DB export |
| **Unified eval dashboards** | Medium | Data Prepper transforms to `gen_ai.eval.*` |
| **OpenInference attributes** | Low | Full attribute remap via Data Prepper |
| **OpenLLMetry model name bug** | Low | Transform `traceloop.association.properties.ls_model_name` → `gen_ai.request.model` |
| **Braintrust token counts** | Low | Transform `braintrust.metrics.*` → `gen_ai.usage.*` |

### Known Issues & Gotchas

1. **OpenLLMetry Model Name Bug**: Sets `gen_ai.request.model` to "unknown" for Bedrock. Actual value in `traceloop.association.properties.ls_model_name`.

2. **OpenLLMetry Package Conflict**: `traceloop-sdk` interferes with `opentelemetry-instrumentation-{framework}`. Causes missing tool spans.

3. **Package Naming Collision**: `pip install opentelemetry-instrumentation-langchain` installs Traceloop/OpenLLMetry, NOT official OTel package.

---

## Open Questions

| Question | Options | Recommendation |
|---|---|---|
| Propose `gen_ai.eval.*` to OTel SIG? | Yes / Keep vendor namespaces | Yes—enables cross-platform dashboards |
| Phoenix customers: hybrid approach? | Phoenix for evals + AgentOps for tracing | Acceptable interim solution |
| Support OpenInference long-term? | Full transforms / Recommend migration | Transforms for now, guide to OpenLLMetry |

---

## Technical Reference

### Attribute Mapping

| Concept | GenAI SemConv | OpenLLMetry | OpenInference | Langfuse | Braintrust |
|---|---|---|---|---|---|
| Provider | `gen_ai.system` | ✅ | `llm.provider` | ✅ | ✅ |
| Model | `gen_ai.request.model` | `traceloop.association.properties.ls_model_name` | `llm.model_name` | ✅ | ✅ |
| Input tokens | `gen_ai.usage.input_tokens` | ✅ | `llm.token_count.prompt` | ✅ | `braintrust.metrics.prompt_tokens` |
| Output tokens | `gen_ai.usage.output_tokens` | ✅ | `llm.token_count.completion` | ✅ | `braintrust.metrics.completion_tokens` |
| Eval scores | `gen_ai.eval.*` (proposed) | N/A | N/A | ❌ (separate API) | `braintrust.scores.*` |

### Evaluation Attribute Mapping

| Concept | Proposed Standard | Langfuse | Braintrust | Phoenix |
|---|---|---|---|---|
| Experiment name | `gen_ai.eval.experiment.name` | ❌ (separate API) | `braintrust.experiment.name` | `phoenix.experiment.name` |
| Item ID | `gen_ai.eval.dataset.item_id` | ❌ (separate API) | `braintrust.experiment.item_index` | `phoenix.dataset.example_id` |
| Input | `gen_ai.eval.input` | `langfuse.observation.input` | `braintrust.input` | `input.value` |
| Output | `gen_ai.eval.output` | `langfuse.observation.output` | `braintrust.output` | `output.value` |
| Expected | `gen_ai.eval.expected` | ❌ (in dataset) | `braintrust.expected` | `phoenix.expected` |
| Scores | `gen_ai.eval.score.<name>` | ❌ (separate API) | `braintrust.scores.<name>` | Phoenix DB only |

> **Note on Langfuse:** Langfuse scores are submitted via a separate [Scores API](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk), not as span attributes. The `langfuse.observation.*` attributes are for tracing only. To migrate Langfuse evals, you must either export from Langfuse's database or continue using their Scores API alongside AgentOps tracing.

---

## References

- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OpenTelemetry GenAI SemConv SIG](https://github.com/open-telemetry/community?tab=readme-ov-file#sig-genai-instrumentation)
- [OpenLLMetry](https://github.com/traceloop/openllmetry)
- [OpenInference](https://github.com/Arize-ai/openinference)
- [Langfuse OpenTelemetry Integration](https://langfuse.com/docs/opentelemetry)
- [Braintrust OpenTelemetry Integration](https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry)


---

## Appendix A: Data Prepper Transform Configs

### A.1 OpenInference → GenAI SemConv

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.system"], attributes["llm.provider"]) where attributes["llm.provider"] != nil
        - set(attributes["gen_ai.request.model"], attributes["llm.model_name"]) where attributes["llm.model_name"] != nil
        - set(attributes["gen_ai.usage.input_tokens"], attributes["llm.token_count.prompt"]) where attributes["llm.token_count.prompt"] != nil
        - set(attributes["gen_ai.usage.output_tokens"], attributes["llm.token_count.completion"]) where attributes["llm.token_count.completion"] != nil
        - set(attributes["gen_ai.tool.name"], attributes["tool.name"]) where attributes["tool.name"] != nil
```

### A.2 Braintrust Token Normalization

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.usage.input_tokens"], attributes["braintrust.metrics.prompt_tokens"]) where attributes["braintrust.metrics.prompt_tokens"] != nil
        - set(attributes["gen_ai.usage.output_tokens"], attributes["braintrust.metrics.completion_tokens"]) where attributes["braintrust.metrics.completion_tokens"] != nil
```

### A.3 OpenLLMetry Model Name Fix

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.request.model"], attributes["traceloop.association.properties.ls_model_name"]) where attributes["gen_ai.request.model"] == "unknown" and attributes["traceloop.association.properties.ls_model_name"] != nil
```

### A.4 Langfuse Observation Normalization (Tracing Only)

> **Note:** Langfuse scores are NOT available via OTLP. Only observation attributes (input/output) can be transformed.

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.eval.input"], attributes["langfuse.observation.input"]) where attributes["langfuse.observation.input"] != nil
        - set(attributes["gen_ai.eval.output"], attributes["langfuse.observation.output"]) where attributes["langfuse.observation.output"] != nil
```

### A.5 Braintrust Eval Normalization

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.eval.experiment.name"], attributes["braintrust.experiment.name"]) where attributes["braintrust.experiment.name"] != nil
        - set(attributes["gen_ai.eval.dataset.item_id"], attributes["braintrust.experiment.item_index"]) where attributes["braintrust.experiment.item_index"] != nil
        - set(attributes["gen_ai.eval.input"], attributes["braintrust.input"]) where attributes["braintrust.input"] != nil
        - set(attributes["gen_ai.eval.output"], attributes["braintrust.output"]) where attributes["braintrust.output"] != nil
        - set(attributes["gen_ai.eval.expected"], attributes["braintrust.expected"]) where attributes["braintrust.expected"] != nil
```

---

## Appendix B: Code Migration Examples

### B.1 Manual OpenTelemetry (Baseline)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("my-agent")

with tracer.start_as_current_span("chat claude-sonnet", kind=trace.SpanKind.CLIENT) as span:
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.system", "aws.bedrock")
    span.set_attribute("gen_ai.request.model", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    result = agent.invoke({"input": query})
```

### B.2 Migrating from Langfuse

```python
# Before: Sending to Langfuse
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-..."
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"

# After: Change OTLP endpoint only
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
# All langfuse.* attributes still flow through
```

### B.3 Migrating from Braintrust

```python
# Before: Using BraintrustSpanProcessor
from braintrust.otel import BraintrustSpanProcessor
provider.add_span_processor(BraintrustSpanProcessor())

# After: Replace with standard OTLP exporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
# All braintrust.* attributes still flow through
```

### B.4 OpenLLMetry (LangChain)

```python
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
LangchainInstrumentor().instrument()
# All LangChain calls auto-instrumented
```

### B.5 OpenInference (LangChain)

```python
from openinference.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument()
# All LangChain calls auto-instrumented (requires transforms)
```

---

## Appendix C: Captured Span Examples

### C.1 OpenLLMetry (LangChain + Bedrock)

```json
{
  "name": "ChatBedrockConverse.chat",
  "attributes": {
    "gen_ai.system": "AWS",
    "gen_ai.request.model": "unknown",
    "gen_ai.usage.input_tokens": 714,
    "gen_ai.usage.output_tokens": 96,
    "traceloop.association.properties.ls_model_name": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "traceloop.association.properties.ls_provider": "amazon_bedrock"
  }
}
```

### C.2 OpenInference (LangChain + Bedrock)

```json
{
  "name": "ChatBedrockConverse",
  "attributes": {
    "openinference.span.kind": "LLM",
    "llm.provider": "amazon_bedrock",
    "llm.model_name": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "llm.token_count.prompt": 714,
    "llm.token_count.completion": 96
  }
}
```

### C.3 Langfuse Tracing Span (Scores NOT in OTLP)

> **Important:** This shows tracing attributes only. Langfuse scores are submitted via a separate API and do NOT appear in OTLP spans.

```json
{
  "name": "generation",
  "serviceName": "langfuse-weather-agent",
  "attributes": {
    "langfuse.observation.input": "What was the weather in London on 2024-01-15?",
    "langfuse.observation.output": "Tool: get_historical_weather",
    "langfuse.user.id": "user-123",
    "langfuse.session.id": "session-456",
    "gen_ai.request.model": "us.anthropic.claude-sonnet-4-20250514-v1:0"
  }
}
```

To get scores from Langfuse, you must call their [Scores API](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk):
```python
langfuse.create_score(
    trace_id="...",
    name="tool_selection",
    value=1.0,
)
```

### C.4 Braintrust Evaluation Span

```json
{
  "name": "experiment_run",
  "serviceName": "braintrust-eval-weather",
  "attributes": {
    "braintrust.experiment.name": "weather-agent-bt-001",
    "braintrust.experiment.item_index": 2,
    "braintrust.input": "What was the weather in London on 2024-01-15?",
    "braintrust.expected": "{'tool': 'get_historical_weather', 'location': 'London'}",
    "braintrust.output": "{'tool': 'get_historical_weather', 'location': 'London', 'args': {'location': 'London', 'date': '2024-01-15'}}",
    "braintrust.scores.tool_match": 1.0,
    "braintrust.metrics.prompt_tokens": 150,
    "braintrust.metrics.completion_tokens": 50,
    "gen_ai.request.model": "us.anthropic.claude-sonnet-4-20250514-v1:0"
  }
}
```

### C.5 Arize Phoenix Evaluation Span

```json
{
  "name": "experiment_run",
  "serviceName": "arize-phoenix-eval-weather",
  "attributes": {
    "openinference.span.kind": "CHAIN",
    "phoenix.experiment.name": "weather-agent-phoenix-001",
    "phoenix.dataset.example_id": "weather-3",
    "phoenix.expected": "{'tool': 'get_historical_weather', 'location': 'London'}",
    "phoenix.eval.tool_match": 1.0,
    "phoenix.eval.location_match": 1.0,
    "input.value": "What was the weather in London on 2024-01-15?",
    "output.value": "{'tool': 'get_historical_weather', 'location': 'London', 'args': {'location': 'London', 'date': '2024-01-15'}}",
    "gen_ai.request.model": "us.anthropic.claude-sonnet-4-20250514-v1:0"
  }
}
```

---

## Appendix D: Test Methodology

- **LLM**: Claude Sonnet via AWS Bedrock
- **Tools**: `get_current_weather`, `get_forecast`, `get_historical_weather`
- **Framework**: LangChain
- **Test queries**: Current weather, forecast, historical (3 queries)

### Not Yet Tested

| Operation | Use Case |
|---|---|
| `embeddings` | Vector embedding generation |
| `retrieval` | RAG document retrieval |
| `create_agent` | OpenAI Assistants API |
| Error scenarios | Exception handling |
