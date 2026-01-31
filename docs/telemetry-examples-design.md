# Telemetry Examples Design

> Design document for extending AgentOps agent telemetry examples.
> Status: Draft - Iterating

## Current State

The weather-agent example demonstrates:
- Manual OTel instrumentation (traces, metrics, logs)
- `invoke_agent` and `execute_tool` spans
- Gen-AI semantic conventions (token usage, model info, conversation ID)
- Single agent → single tool flow

**Limitation**: Service map shows only 2-3 nodes. No real distributed calls, no multi-agent patterns.

---

## Goals

1. Richer service map visualizations (more nodes, real relationships)
2. Wider coverage of OTel Gen-AI semantic conventions
3. Support for multiple instrumentation libraries (openinference, openllmetry)
4. No API keys required for LLMs (keep examples self-contained)

---

## Proposed Extensions

### 1. Multi-Agent Architecture

**Decision**: Remote multi-agents (separate containers) with hybrid fan-out/chain pattern.

#### Architecture

```
┌─────────────────┐
│  Orchestrator   │ :8000
└────────┬────────┘
         ▼
┌─────────────────┐
│  Intent Parser  │ [chain] - determines what info is needed
└────────┬────────┘
         │
    ┌────┴────┐     [fan-out] - parallel data gathering
    ▼         ▼
┌───────┐ ┌───────┐
│Weather│ │Events │ :8001, :8002
│ Agent │ │ Agent │
└───┬───┘ └───┬───┘
    └────┬────┘
         ▼
┌─────────────────┐
│ Recommendation  │ [chain] - synthesize and respond
│     Agent       │
└─────────────────┘
```

#### Why Hybrid Pattern

| Pattern | Service Map | Trace View | Metrics Story |
|---------|-------------|------------|---------------|
| Fan-out | Star topology | Concurrent spans | Throughput per agent |
| Chain | Linear graph | Waterfall | Bottleneck identification |
| Hybrid | Mixed graph | Both patterns | Most realistic |

#### Deployment

Separate containers communicating via HTTP:
- `orchestrator:8000` - entry point, contains intent parser + recommendation logic
- `weather-agent:8001` - existing, reused
- `events-agent:8002` - new, calls free events API

Benefits:
- Service map shows distinct nodes with edges
- Demonstrates W3C trace context propagation over HTTP
- Realistic microservices pattern
- Shows cross-service latency, errors, retries

#### Use Case

"Trip Planner" - User asks about travel, orchestrator:
1. Parses intent (chain)
2. Gathers weather + local events in parallel (fan-out)
3. Synthesizes recommendation (chain)

### 2. Real External Service Calls

Replace simulated calls with free APIs (no keys required):
- **Weather**: Open-Meteo, wttr.in
- **Geocoding**: Nominatim (OpenStreetMap)
- **Time/Timezone**: WorldTimeAPI

Benefits: Real HTTP client spans, actual latency/errors.

### 3. Instrumentation Library Coverage

**Goal**: Cover bulk surface area of existing customer use-cases. Evaluate how much normalization is needed to get a unified view in OpenSearch Dashboards.

| Library | Purpose | Frameworks Supported |
|---------|---------|---------------------|
| openinference (Arize) | Auto-instrumentation | LangChain, LlamaIndex, OpenAI, CrewAI, Bedrock |
| openllmetry (Traceloop) | Auto-instrumentation | LangChain, LlamaIndex, OpenAI, CrewAI, Bedrock |
| Manual OTel (current) | Direct OTel SDK | Any (full control) |
| otel-instrumentation-httpx | HTTP client spans | N/A |
| otel-instrumentation-sqlalchemy | DB spans | N/A |

#### Instrumentation Comparison Deep Dive (TODO)

Need to compare attribute schemas across the three approaches:

| Attribute | OTel GenAI SemConv | openinference | openllmetry |
|-----------|-------------------|---------------|-------------|
| `gen_ai.operation.name` | ✓ | ? | ? |
| `gen_ai.agent.name` | ✓ | ? | ? |
| `gen_ai.usage.input_tokens` | ✓ | ? | ? |
| ... | ... | ... | ... |

**Action item**: Build same agent with all 3 instrumentation approaches, compare raw span output.

#### Data Prepper Normalization (Potential)

If attribute schemas differ significantly, may need custom Data Prepper pipeline processors to normalize:
- openinference attributes → OTel GenAI SemConv
- openllmetry attributes → OTel GenAI SemConv

This would provide unified querying/visualization in OpenSearch regardless of instrumentation library used.

#### CrewAI as Test Framework

CrewAI is a good candidate for the comparison because:
- Inherently multi-agent (rich telemetry surface)
- Popular framework (represents real customer usage)
- Supported by both openinference and openllmetry
- Demonstrates sequential and hierarchical agent patterns

**Caveat**: Requires real LLM (Bedrock, OpenAI, or Ollama for local/free).

### 4. Gen-AI Semantic Convention Gaps

| Pattern | Implementation |
|---------|---------------|
| RAG (retrieval) | Vector store lookup with `gen_ai.operation.name: retrieve` |
| Embeddings | `gen_ai.operation.name: embeddings` |
| Multi-turn conversations | Persist state, show `gen_ai.conversation.id` across requests |
| Streaming responses | `gen_ai.response.streaming: true` with chunked events |
| Agent handoffs | `gen_ai.agent.handoff.target_agent_id` |
| Error scenarios | Rate limits, timeouts, content filtering |

### 5. Evaluation Platform Integration

**Goal**: Demonstrate migration path for customers using existing eval/observability platforms, and validate AgentOps covers their telemetry use-cases.

#### Target Platforms

| Platform | OTLP Native? | Notes |
|----------|--------------|-------|
| Braintrust | No (custom SDK) | Exports to their backend; need to check if OTLP export possible |
| Langfuse | Yes (via OTEL SDK) | Has OpenTelemetry integration |
| Arize Phoenix | Yes | Built on OpenInference, OTLP-first |

#### What Eval Telemetry Looks Like

Unlike production traffic, eval runs produce:
- Batch of spans (entire test suite in short window)
- Ground truth labels / expected outputs
- Scores and assertions (pass/fail, similarity scores)
- Dataset metadata (eval set name, version)

#### Integration Approaches

1. **Dual-write during migration** - Send to both existing platform and AgentOps
2. **OTLP redirect** - Point OTLP exporter at AgentOps instead of vendor
3. **Export & replay** - Export historical eval data, replay into AgentOps

#### Open Questions

- [ ] Which platforms support OTLP export natively?
- [ ] What attributes do eval platforms add beyond GenAI SemConv?
- [ ] Do we need eval-specific dashboards in OpenSearch?

---

## Proposed Directory Structure

```
examples/
├── plain-agents/
│   ├── weather-agent/          # (existing) Basic manual instrumentation
│   ├── multi-agent-planner/    # Multi-agent orchestration
│   └── rag-agent/              # RAG with embeddings + retrieval
├── langchain/
│   ├── openinference-demo/     # Auto-instrumentation with openinference
│   └── bedrock-financial/      # (existing)
├── strands/
│   └── code-assistant/         # (existing)
└── instrumentation-comparison/
    └── same-agent-3-ways/      # Same logic, different instrumentation libs
```

---

## Canary Enhancements

Current: Only hits weather-agent with random queries.

Proposed:
- Cycle through different example agents
- Generate error scenarios (bad inputs, timeouts)
- Vary load patterns for metrics variety

---

## Priority Order

1. **Multi-agent example** - Biggest impact on service map visualization
2. **openinference integration** - Most popular GenAI auto-instrumentation
3. **Eval platform integration** - Migration path for existing customers

---

## Open Questions

- [ ] Should multi-agent example use HTTP calls between agents or in-process?
- [ ] Include database for conversation persistence?
- [ ] How to handle examples that need real LLM (Bedrock) vs fully simulated?

---

## Next Steps

### Phase 1: Instrumentation Comparison Spike (2-4 hrs)

> **Working doc**: [instrumentation-comparison.md](./instrumentation-comparison.md)

**Goal**: Understand attribute schema differences across instrumentation libraries.

**Tasks**:
1. Pick one simple agent task (e.g., "answer a question with one tool call")
2. Implement 3 ways:
   - Manual OTel (existing weather-agent as baseline)
   - openinference auto-instrumentation
   - openllmetry auto-instrumentation
3. Capture raw span JSON from each
4. Diff attribute names/structures
5. Fill in comparison table in this doc

**Output**: Data to decide if Data Prepper normalization is needed.

### Phase 2: Multi-Agent Planner (1-2 days)

**Goal**: Prove service map and trace visualization story.

**Tasks**:
1. Build orchestrator service (intent parser + recommendation logic)
2. Build events-agent service (calls free API)
3. Reuse existing weather-agent
4. Add to docker-compose.examples.yml
5. Update canary to hit orchestrator

**Output**: Rich service map with 3+ nodes, hybrid trace patterns.

### Phase 3: CrewAI Example with openinference (1 day)

**Goal**: Validate real-world framework coverage.

**Tasks**:
1. Create CrewAI example with 2-3 agents
2. Instrument with openinference
3. Document attribute mapping to GenAI SemConv
4. Add to examples/crewai/

**Output**: Working CrewAI example sending telemetry to AgentOps stack.

### Phase 4: Data Prepper Normalization (if needed)

**Goal**: Unified querying regardless of instrumentation library.

**Tasks**:
1. Based on Phase 1 findings, identify attributes needing normalization
2. Add transform processors to Data Prepper pipelines
3. Test unified queries in OpenSearch Dashboards

**Output**: Consistent attribute schema across all instrumentation approaches.

---

## Future Work: Expanded Multi-Agent Planner

Additional sub-agents to make the travel planner more realistic:

| Agent | Purpose | Interesting Failure Modes |
|-------|---------|---------------------------|
| flights-agent | Search flights, prices, availability | No availability, price changes, API rate limits |
| hotels-agent | Accommodation options and rates | Sold out, price fluctuations, booking conflicts |
| restaurants-agent | Dining recommendations, reservations | Fully booked, closed, dietary restrictions |
| transport-agent | Local transit, car rentals, ride shares | Surge pricing, no availability |
| currency-agent | Exchange rates, budget conversion | Stale rates, API failures |
| safety-agent | Travel advisories, visa requirements | Advisory changes, missing data |

**Implementation options**:
- Plain agents (like current weather/events) - simulated responses
- CrewAI multi-agent framework - real LLM coordination, richer telemetry
- Mix: Plain agents for data gathering, CrewAI for orchestration/reasoning

**CrewAI benefits**:
- Inherently multi-agent with sequential/hierarchical patterns
- Supported by openinference and openllmetry
- Demonstrates real agent collaboration and handoffs
- Richer trace patterns (agent reasoning, tool selection)

**Caveat**: CrewAI requires real LLM (Bedrock, OpenAI, or Ollama for local).

---

## Changelog

- 2026-01-27: Phase 2 complete - multi-agent planner with travel-planner, weather-agent, events-agent. Fault injection at orchestrator and sub-agent levels. Canary updated.
- 2026-01-27: Phase 1 complete - instrumentation comparison findings in [Quip](https://quip-amazon.com/tMWMAakxYApw)
- 2026-01-26: Initial draft from brainstorming session
