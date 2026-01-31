## What/Why

### What are you proposing?

AgentOps: an open-source observability stack for AI agents and distributed systems. Built on OpenTelemetry, OpenSearch, and Prometheus, AgentOps provides pre-configured infrastructure for monitoring applications with first-class support for agent observability through OpenTelemetry Gen-AI Semantic Conventions.

Core capabilities:
- Docker Compose configuration for local development
- Helm charts for Kubernetes deployment
- Pre-configured OpenTelemetry Collector, Data Prepper, OpenSearch, and Prometheus
- Example instrumentation code for AI agents (plain Python, LangChain, Strands)
- OpenSearch Dashboards with observability workspace auto-configuration

### What users have asked for this feature?

- Customers have expressed difficulties and frustration configuring OpenSearch and OpenSearch Dashboards for observability in self-hosted/cloud-native environments
- AI agent monitoring and evaluation is a rapidly growing space in 2026, with tools like Arize and Braintrust gaining significant traction
- The OpenTelemetry Gen-AI Semantic Conventions provide a standardized way to instrument AI agents, but there's no turnkey OpenSearch-based solution to receive and visualize this telemetry
- OpenSearch community members frequently ask for quickstart guides and reference architectures for observability use cases

### What problems are you trying to solve?

When **building AI agents or distributed systems**, a **developer** wants to **quickly set up observability infrastructure**, so they can **monitor, debug, and optimize their applications without spending days on configuration**.

When **evaluating OpenSearch for observability**, an **architect** wants to **see a working reference implementation**, so they can **understand how the components fit together and make informed technology decisions**.

When **instrumenting an AI agent with OpenTelemetry**, a **developer** wants to **see example code following Gen-AI semantic conventions**, so they can **correctly capture traces, metrics, and logs for their agent workflows**.

### What is the developer experience going to be?

This is a deployment/configuration project, not a library or API. The developer experience is:

```bash
# Clone and start
git clone https://github.com/opensearch-project/agentops.git
cd agentops
docker compose up -d

# Send telemetry to localhost:4317 (gRPC) or localhost:4318 (HTTP)
# View in OpenSearch Dashboards at localhost:5601
```

**Configuration options via `.env` file:**
- Component versions (OpenSearch, OTel Collector, Data Prepper, Prometheus)
- Ports and credentials
- Optional example services (example agents, canary traffic generator)

**No REST API changes** - this project uses existing OpenSearch and OpenTelemetry APIs.

#### Are there any security considerations?

The default configuration is for **development use only** and includes:
- Default credentials (admin/admin)
- Self-signed TLS certificates with verification disabled
- Permissive CORS settings
- All services exposed without network isolation

Documentation clearly warns users to harden security before production use. The README includes a "Production Readiness" section outlining required security hardening.

#### Are there any breaking changes to the API

No. This project does not modify any OpenSearch or OpenTelemetry APIs.

### What is the user experience going to be?

**Getting Started (< 5 minutes):**
1. Clone repository
2. Run `docker compose up -d`
3. Open OpenSearch Dashboards at localhost:5601
4. See example telemetry from included sample agents

**Instrumenting Your Application:**
1. Configure OTLP exporter to point to localhost:4317
2. Use OpenTelemetry SDK with Gen-AI semantic conventions
3. View traces, logs, and metrics in OpenSearch Dashboards

**User Stories:**
- As a developer, I can start a complete observability stack with one command, with pre-tuned defaults that work immediately
- As a developer, I can send OTLP telemetry and see it in OpenSearch Dashboards without configuring pipelines or index patterns
- As a developer, I can reference example code to instrument my AI agents
- As an operator, I can customize component versions and settings via environment variables while relying on battle-tested baseline configurations

#### Are there breaking changes to the User Experience?

No. This is a new project with no existing users.

### Why should it be built? Any reason not to?

**Value to OpenSearch community:**
- Positions OpenSearch as a unified observability platform
- Provides a quickstart for users evaluating OpenSearch for observability, with pre-tuned configurations that work out of the box
- Demonstrates integration of OpenSearch ecosystem components (OpenSearch, Data Prepper, Dashboards) with production-ready defaults
- Captures the growing AI agent observability market with Gen-AI semantic convention support
- Reduces barrier to entry—users can focus on their applications instead of wrestling with pipeline and index configuration

**Impact if not built:**
- Users continue to struggle with manual configuration
- OpenSearch loses mindshare to competitors with easier onboarding
- No reference implementation for AI agent observability with OpenSearch

**Reasons not to build:**
- Maintenance burden for keeping configurations up to date
- Risk of configurations becoming stale if not actively maintained

### What will it take to execute?

**Current state:** Working Docker Compose deployment with all core components, example agents, and documentation. Source code at https://github.com/kylehounslow/agentops

**Execution plan:**
1. Transfer repository to opensearch-project organization
2. Community feedback and iteration on configuration
3. Add Helm charts for Kubernetes deployment
4. Add CDK templates for AWS deployment

**Dependencies:**
- OpenSearch and OpenSearch Dashboards releases
- Data Prepper releases
- OpenTelemetry Collector releases
- No dependencies on unreleased OpenSearch features

**Risks:**
- Configuration drift as upstream components release new versions
- Mitigation: Automated testing and version pinning

### Any remaining open questions?

**Planned deployment tiers (future roadmap):**
1. **Local dev (current):** Docker Compose with OTel Collector, OpenSearch, OpenSearch Dashboards, Prometheus
2. **Cloud-native (planned):** Helm charts with OTel Collector, OpenSearch, OpenSearch Dashboards, Cortex or Prometheus
3. **AWS (planned):** CDK with ADOT, Amazon OpenSearch Service, OpenSearch UI, Amazon Managed Prometheus

**Open questions:**
- Should we include additional framework examples (CrewAI, AutoGen, etc.)?
