---
title: AI Observability
description: Observe, debug, and evaluate AI agent workflows with OpenTelemetry GenAI conventions
---

The Observability Stack provides end-to-end tooling for AI agent observability - from instrumenting your code to viewing traces, scoring quality, and running evaluations.

## End-to-end platform

```mermaid
flowchart LR
    subgraph instrument["1 &nbsp; Instrument"]
        direction TB
        A1["<b>GenAI SDK</b><br/>@observe, enrich(),<br/>auto-instrument LLMs"]
    end
    subgraph normalize["2 &nbsp; Normalize"]
        direction TB
        B1["<b>OTEL Collector</b><br/>Standardize spans,<br/>semantic conventions"]
    end
    subgraph local["3 &nbsp; Local Tooling"]
        direction TB
        C1["<b>Agent Health</b><br/>Debugging, scoring,<br/>evaluations"]
    end
    subgraph process["4 &nbsp; Process"]
        direction TB
        D1["<b>Data Prepper</b><br/>Service maps, trace<br/>correlation, aggregation"]
    end
    subgraph analyze["5 &nbsp; Analyze"]
        direction TB
        E1["<b>OpenSearch Dashboards</b><br/>Agent traces, graphs,<br/>evals, APM"]
    end
    instrument --> normalize --> process --> analyze
    normalize --> local
    local --> process
```

## Capabilities

- **Agent tracing** - visualize LLM agent execution as trace trees, DAG graphs, and timelines
- **GenAI semantic conventions** - standard `gen_ai.*` attributes for model, tokens, tools, and sessions
- **Evaluation & scoring** - attach quality scores to traces, run experiments against datasets
- **Trace retrieval** - query stored traces from OpenSearch for evaluation pipelines
- **Auto-instrumentation** - OpenAI, Anthropic, Bedrock, LangChain, and 20+ libraries traced automatically
- **MCP server** - query OpenSearch from AI agents via the built-in Model Context Protocol server

## Getting started

Start here for a hands-on walkthrough from `pip install` to seeing traces and scoring quality:

- **[Getting Started](/docs/ai-observability/getting-started/)** - instrument an agent, view traces, score quality in 5 minutes

## Instrument

Send agent trace data to the observability stack:

- [Python SDK](/docs/send-data/ai-agents/python/) - `@observe`, `enrich()`, auto-instrumentation, AWS SigV4
- [TypeScript SDK](/docs/send-data/ai-agents/typescript/) - coming soon
- [AI Agents overview](/docs/send-data/ai-agents/) - why use the SDK vs manual OTel

## Analyze

Explore traces in OpenSearch Dashboards:

- [Agent Tracing](/docs/ai-observability/agent-tracing/) - the Agent Traces UI, span tables, detail flyouts
- [Agent Graph & Path](/docs/ai-observability/agent-tracing/graph/) - DAG visualization, trace tree, and timeline views

## Evaluate

Score agent quality and run experiments:

- [Evaluation & Scoring](/docs/agent-evals/evaluation/) - `score()`, `evaluate()`, `Benchmark`, trace retrieval
- **[Agent Health](/docs/agent-health/)** - Golden Path trajectory comparison, LLM judge scoring, batch experiments via UI and CLI

## Connect

- [MCP Server](/docs/mcp/) - query OpenSearch from AI agents via MCP
