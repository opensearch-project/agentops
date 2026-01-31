# Onboarding to AgentOps: Migration & Instrumentation Guide

This guide helps customers adopt AgentOps with minimal friction, whether starting fresh or migrating from existing observability platforms.

## Quick Start: Find Your Path

| Where are you today? | Path to AgentOps | Effort |
|----------------------|------------------|--------|
| **No observability yet** | Add instrumentation library → point to AgentOps | Low |
| **Using Langfuse** | Change OTLP endpoint | **Zero** |
| **Using Braintrust** | Change OTLP endpoint + optional transform | **Minimal** |
| **Using Arize Phoenix** | Change OTLP endpoint + transform | **Low** (tracing) / **High** (evals) |
| **Custom OpenTelemetry** | Point exporter to AgentOps | **Zero** |

---

## Part 1: New Customers (No Existing Observability)

### 1.1 Choosing an Instrumentation Library

| Library | Maintainer | Best For | GenAI SemConv Alignment |
|---------|------------|----------|-------------------------|
| **OTel Contrib GenAI** | OpenTelemetry Project | OpenAI, Anthropic SDK users | ✅ Full |
| **OpenLLMetry** | Traceloop | LangChain, LlamaIndex, Bedrock | ✅ High |
| **OpenInference** | Arize AI | Existing Phoenix users | ⚠️ Low (requires transform) |
| **Manual OTel** | You | Custom agents, full control | ✅ Full |

**Recommendation**: Use **OTel Contrib GenAI** or **OpenLLMetry** for fastest onboarding with best SemConv alignment.

### 1.2 Framework Support Matrix

| Framework | OTel Contrib | OpenLLMetry | OpenInference |
|-----------|--------------|-------------|---------------|
| OpenAI SDK | ✅ | ✅ | ✅ |
| Anthropic SDK | ✅ | ✅ | ✅ |
| AWS Bedrock | ❌ | ✅ | ✅ |
| LangChain | ✅ (unreleased) | ✅ | ✅ |
| LlamaIndex | ❌ | ✅ | ✅ |
| CrewAI | ❌ | ✅ | ✅ |

### 1.3 Quick Setup Examples

**OpenLLMetry (LangChain/Bedrock)**
```python
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Point to AgentOps
exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)

# Auto-instrument
LangchainInstrumentor().instrument()
```

**OTel Contrib (OpenAI)**
```python
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
OpenAIInstrumentor().instrument()
```

---

## Part 2: Migrating from Existing Platforms

### 2.1 Platform Comparison

| Platform | OTLP Native? | Tracing Migration | Evals Migration |
|----------|--------------|-------------------|-----------------|
| **Langfuse** | ✅ Yes | Change endpoint | Change endpoint |
| **Braintrust** | ✅ Yes | Change endpoint | Change endpoint + transform |
| **Arize Phoenix** | ✅ Yes | Change endpoint + transform | ❌ Not portable (Phoenix DB) |

### 2.2 Langfuse → AgentOps

**Effort: Zero** (tracing) / **Minimal** (evals with unified dashboards)

Langfuse uses standard OTLP and GenAI SemConv-aligned attributes.

```python
# Before: Langfuse
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"

# After: AgentOps - just change the endpoint
exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
```

**What flows through automatically:**
- `gen_ai.request.model` ✅
- `gen_ai.usage.input_tokens` ✅
- `gen_ai.usage.output_tokens` ✅
- `langfuse.score.*` (eval scores)
- `langfuse.user.id`, `langfuse.session.id`

### 2.3 Braintrust → AgentOps

**Effort: Minimal** (token counts need transform for unified dashboards)

```python
# Before: Braintrust
from braintrust.otel import BraintrustSpanProcessor
provider.add_span_processor(BraintrustSpanProcessor())

# After: AgentOps
exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
```

**What flows through automatically:**
- `gen_ai.request.model` ✅
- `braintrust.scores.*` (eval scores)
- `braintrust.input`, `braintrust.output`

**Requires transform for unified dashboards:**
- `braintrust.metrics.prompt_tokens` → `gen_ai.usage.input_tokens`
- `braintrust.metrics.completion_tokens` → `gen_ai.usage.output_tokens`

### 2.4 Arize Phoenix → AgentOps

**Effort: Low** (tracing) / **High** (evals)

Phoenix uses OpenInference which has its own `llm.*` namespace.

```python
# Before: Phoenix
from openinference.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument()
# Traces go to Phoenix

# After: AgentOps - same instrumentation, different endpoint
exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
```

**Requires transform:**
- `llm.provider` → `gen_ai.system`
- `llm.model_name` → `gen_ai.request.model`
- `llm.token_count.prompt` → `gen_ai.usage.input_tokens`
- `llm.token_count.completion` → `gen_ai.usage.output_tokens`

**⚠️ Phoenix Evals Limitation**: Phoenix stores evaluation scores in its own database, NOT as OTLP span attributes. Migration options:
1. Continue using Phoenix for evals (hybrid approach)
2. Implement custom instrumentation to emit eval spans
3. Export from Phoenix DB and re-ingest

---

## Part 3: Attribute Landscape

### 3.1 Tracing Attributes

| Concept | GenAI SemConv (Target) | Langfuse | Braintrust | Phoenix/OpenInference |
|---------|------------------------|----------|------------|----------------------|
| Provider | `gen_ai.system` | ✅ | ✅ | `llm.provider` |
| Model | `gen_ai.request.model` | ✅ | ✅ | `llm.model_name` |
| Input tokens | `gen_ai.usage.input_tokens` | ✅ | `braintrust.metrics.prompt_tokens` | `llm.token_count.prompt` |
| Output tokens | `gen_ai.usage.output_tokens` | ✅ | `braintrust.metrics.completion_tokens` | `llm.token_count.completion` |

### 3.2 Evaluation Attributes

| Concept | Proposed Standard | Langfuse | Braintrust | Phoenix |
|---------|-------------------|----------|------------|---------|
| Scores | `gen_ai.eval.score.<name>` | `langfuse.score.<name>` | `braintrust.scores.<name>` | Phoenix DB only |
| Experiment | `gen_ai.eval.experiment.name` | `langfuse.experiment.name` | `braintrust.experiment.name` | Phoenix DB only |
| Test input | `gen_ai.eval.input` | `langfuse.observation.input` | `braintrust.input` | Phoenix DB only |
| Expected | `gen_ai.eval.expected` | N/A | `braintrust.expected` | Phoenix DB only |

> **Proposed Standard**: We recommend normalizing to `gen_ai.eval.*` namespace. This proposal can be submitted to the [OpenTelemetry GenAI SemConv SIG](https://github.com/open-telemetry/community?tab=readme-ov-file#sig-genai-instrumentation) for standardization.

---

## Part 4: Data Prepper Transforms

For unified dashboards across all migration paths, apply these transforms:

### 4.1 OpenInference (Phoenix) Normalization

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.system"], attributes["llm.provider"]) where attributes["llm.provider"] != nil
        - set(attributes["gen_ai.request.model"], attributes["llm.model_name"]) where attributes["llm.model_name"] != nil
        - set(attributes["gen_ai.usage.input_tokens"], attributes["llm.token_count.prompt"]) where attributes["llm.token_count.prompt"] != nil
        - set(attributes["gen_ai.usage.output_tokens"], attributes["llm.token_count.completion"]) where attributes["llm.token_count.completion"] != nil
```

### 4.2 Braintrust Normalization

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.usage.input_tokens"], attributes["braintrust.metrics.prompt_tokens"]) where attributes["braintrust.metrics.prompt_tokens"] != nil
        - set(attributes["gen_ai.usage.output_tokens"], attributes["braintrust.metrics.completion_tokens"]) where attributes["braintrust.metrics.completion_tokens"] != nil
```

### 4.3 OpenLLMetry Model Name Fix

OpenLLMetry has a bug where `gen_ai.request.model` is "unknown" for Bedrock. Fix:

```yaml
transform:
  trace_statements:
    - context: span
      statements:
        - set(attributes["gen_ai.request.model"], attributes["traceloop.association.properties.ls_model_name"]) where attributes["gen_ai.request.model"] == "unknown" and attributes["traceloop.association.properties.ls_model_name"] != nil
```

---

## Part 5: Known Issues & Gotchas

### 5.1 Package Naming Collision

`pip install opentelemetry-instrumentation-langchain` installs **Traceloop/OpenLLMetry**, NOT the official OTel package (which is unreleased).

### 5.2 OpenLLMetry Package Conflict

Do NOT use `traceloop-sdk` together with `opentelemetry-instrumentation-{framework}`. The SDK interferes with framework instrumentation.

### 5.3 Phoenix Evals Not Portable

Phoenix stores experiment results in its own database. Only LLM traces flow through OTLP—eval scores do not.

---

## Appendix: Raw Span Evidence

### Langfuse Span
```json
{
  "attributes": {
    "gen_ai.request.model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "gen_ai.usage.input_tokens": 150,
    "gen_ai.usage.output_tokens": 50,
    "langfuse.score.tool_selection": 1.0,
    "langfuse.user.id": "test-user-123"
  }
}
```

### Braintrust Span
```json
{
  "attributes": {
    "gen_ai.request.model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "braintrust.metrics.prompt_tokens": 150,
    "braintrust.metrics.completion_tokens": 50,
    "braintrust.scores.tool_match": 1.0
  }
}
```

### OpenInference (Phoenix) Span
```json
{
  "attributes": {
    "llm.model_name": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "llm.token_count.prompt": 714,
    "llm.token_count.completion": 96,
    "llm.provider": "amazon_bedrock"
  }
}
```

---

## References

- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OpenTelemetry GenAI SemConv SIG](https://github.com/open-telemetry/community?tab=readme-ov-file#sig-genai-instrumentation)
- [OpenLLMetry](https://github.com/traceloop/openllmetry)
- [OpenInference](https://github.com/Arize-ai/openinference)
- [Langfuse OpenTelemetry Docs](https://langfuse.com/docs/opentelemetry)
- [Braintrust OpenTelemetry Docs](https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry)
