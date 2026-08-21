---
title: Agent Evals
description: Measure the quality of your AI agents — score traces, run experiments against datasets, and bring in external eval frameworks
---

**Agent Evals** measure whether your AI agents are actually doing a good job — not just whether they ran, but whether their outputs are correct, relevant, safe, and on-task. Where [Agent Observability](/docs/ai-observability/) shows you *what an agent did* (traces, spans, the execution graph), Agent Evals put a **quality score** on that behavior so you can track it, compare versions, and catch regressions.

Evaluation results flow through the same OTLP pipeline as your traces and land in the same OpenSearch indices, so scores are queryable right alongside the agent spans they describe.

## What you can do

- **Score traces** — attach quality scores to individual agent traces or spans, either inline as the agent runs or after the fact.
- **Run experiments** — evaluate an agent against a dataset with automated scorer functions and compare results across runs or agent versions.
- **Bring your own framework** — upload pre-computed results from external evaluation tools (DeepEval, RAGAS, MLflow, pytest) so they surface in the same place as everything else.

## Core concepts

| Term | Meaning |
|---|---|
| **Score** | A quality measurement attached to a trace or span — for example a correctness, relevance, or toxicity rating. |
| **Scorer** | A function that produces a score, whether an LLM-as-judge, a heuristic, or an external metric. |
| **Experiment** | An agent run against a fixed dataset, scored automatically, so you can measure quality over a representative set of inputs. |
| **Benchmark** | The bridge that uploads results from any evaluation framework into the stack as OTel spans. |

## In this section

- **[Evaluation & Scoring](/docs/agent-evals/evaluation/)** — the SDK APIs: `score()` to rate traces, `evaluate()` to run experiments, and `Benchmark` to upload results.
- **[Evaluation Integrations](/docs/agent-evals/evaluation-integrations/)** — bring DeepEval, RAGAS, MLflow, and pytest results into the observability stack.

## Related

- [Agent Observability](/docs/ai-observability/) — trace and visualize agent execution, the data your evals score.
- [Send Data: AI Agents](/docs/send-data/ai-agents/) — instrument an agent so its traces (and evals) reach the stack.
