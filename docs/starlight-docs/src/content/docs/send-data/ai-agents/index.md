---
title: "AI Agents"
description: "Instrument AI agent applications with the GenAI Observability SDKs"
---

The GenAI Observability SDKs provide purpose-built instrumentation for AI agent applications. They handle the gap between general-purpose OpenTelemetry and what agent developers actually need: tracing orchestration logic, capturing GenAI semantic attributes, and scoring agent quality - all through the standard OTLP pipeline.

## Why use the SDK?

General OTel instrumentation (covered in the [Python](/docs/send-data/applications/python/) and [Node.js](/docs/send-data/applications/nodejs/) guides) traces HTTP calls, database queries, and framework handlers. But it doesn't know about your agent's decision-making, tool calls, or LLM interactions.

The GenAI SDKs add:

- **One-line OTEL setup** - `register()` configures the tracer provider, exporter, and auto-instrumentation in one call
- **`@observe` decorator** - trace agents, tools, and LLM calls with GenAI semantic convention attributes automatically
- **`enrich()`** - set model, tokens, provider, and other GenAI attributes on the active span without manual `set_attribute()` calls
- **Auto-instrumentation** - OpenAI, Anthropic, Bedrock, LangChain, and 20+ libraries traced with zero code changes
- **Evaluation scoring** - `score()` attaches quality metrics to traces through the same OTLP pipeline
- **AWS SigV4** - production-ready signing for OpenSearch Ingestion and OpenSearch Service

## Available SDKs

| Language | Package | Status |
|---|---|---|
| Python | [`opensearch-genai-observability-sdk-py`](https://github.com/opensearch-project/genai-observability-sdk-py) | Available |
| JavaScript / TypeScript | [`@opensearch-project/genai-observability-sdk-ts`](https://github.com/opensearch-project/genai-observability-sdk-ts) | Available |

## Quick example

```python
from opensearch_genai_observability_sdk_py import register, observe, Op, enrich

register(service_name="my-agent")

@observe(op=Op.EXECUTE_TOOL)
def search(query: str) -> list:
    return search_api.query(query)

@observe(op=Op.INVOKE_AGENT)
def agent(question: str) -> str:
    enrich(model="gpt-4o", provider="openai")
    results = search(question)
    return summarize(results)
```

This produces a trace with `gen_ai.operation.name`, `gen_ai.agent.name`, `gen_ai.tool.name`, input/output capture, and token usage - all with standard OTel semantic conventions.

## Next steps

- [Python SDK reference](/docs/send-data/ai-agents/python/) - full API documentation
- [TypeScript SDK reference](/docs/send-data/ai-agents/typescript/) - full API documentation
- [AI Observability - Getting Started](/docs/ai-observability/getting-started/) - end-to-end walkthrough from install to seeing traces
- [Evaluation & Scoring](/docs/agent-evals/evaluation/) - score traces, run experiments, compare agent versions
