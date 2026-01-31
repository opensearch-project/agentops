# Instrumentation Library Comparison

This directory contains working examples comparing different GenAI instrumentation libraries,
all sending telemetry to the AgentOps stack.

## Libraries Tested

| Directory | Library | Source | Namespace |
|-----------|---------|--------|-----------|
| `openllmetry/` | OpenLLMetry | Traceloop | `gen_ai.*`, `traceloop.*` |
| `openinference/` | OpenInference | Arize AI | `llm.*`, `openinference.*` |
| `langfuse-sdk/` | Langfuse SDK v3 | Langfuse | `gen_ai.*`, `langfuse.*` |
| `braintrust-sdk/` | Braintrust SDK | Braintrust | `gen_ai.*`, `braintrust.*` |

## Quick Start

```bash
# 1. Start AgentOps stack (from repo root)
cd /path/to/agentops
docker compose up -d  # or: finch compose up -d

# 2. Run any example
cd examples/langchain/instrumentation-comparison/openllmetry
uv venv && uv pip install -e .
source .venv/bin/activate
python main.py

# 3. View traces in OpenSearch Dashboards
open http://localhost:5601
```

## Captured Data

The `captured-data/` directory contains actual span JSON captured from each library.
See `captured-data/README.md` for detailed attribute comparison.

## Key Findings

### GenAI Semantic Convention Compliance

| Library | `gen_ai.request.model` | `gen_ai.usage.*` | Notes |
|---------|------------------------|------------------|-------|
| OpenLLMetry | ❌ `"unknown"` for Bedrock | ✅ | Model in `traceloop.association.properties.ls_model_name` |
| OpenInference | ❌ Uses `llm.model_name` | ❌ Uses `llm.token_count.*` | Requires transformation |
| Langfuse-style | ✅ | ✅ | Also has `langfuse.*` namespace |
| Braintrust-style | ✅ | ❌ Uses `braintrust.metrics.*` | Also has `braintrust.*` namespace |

### Migration Path to AgentOps

| Current Setup | Migration Effort |
|---------------|------------------|
| OpenLLMetry → Langfuse/Braintrust | **Zero** - change OTLP endpoint |
| Langfuse SDK v3 (OTEL-native) | **Minimal** - change OTLP endpoint |
| Braintrust SDK | **Minimal** - swap to standard OTLPSpanExporter |
| OpenInference → Arize | **Low** - change endpoint + Data Prepper transform |

## Data Prepper Transformations

To normalize all libraries to GenAI SemConv, add these processors to Data Prepper:

```yaml
# OpenLLMetry: Fix model name bug
- rename_keys:
    entries:
      - from_key: "traceloop.association.properties.ls_model_name"
        to_key: "gen_ai.request.model"
        overwrite_if_to_key_exists: true

# OpenInference: Transform llm.* to gen_ai.*
- rename_keys:
    entries:
      - from_key: "llm.model_name"
        to_key: "gen_ai.request.model"
      - from_key: "llm.token_count.prompt"
        to_key: "gen_ai.usage.input_tokens"
      - from_key: "llm.token_count.completion"
        to_key: "gen_ai.usage.output_tokens"
      - from_key: "llm.provider"
        to_key: "gen_ai.system"

# Braintrust: Transform braintrust.metrics.* to gen_ai.usage.*
- rename_keys:
    entries:
      - from_key: "braintrust.metrics.prompt_tokens"
        to_key: "gen_ai.usage.input_tokens"
      - from_key: "braintrust.metrics.completion_tokens"
        to_key: "gen_ai.usage.output_tokens"
```

## Shared Components

- `shared/weather_tools.py` - Common LangChain tools used by all examples
- `captured-data/` - Actual span JSON from each library
