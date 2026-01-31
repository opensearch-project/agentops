# OpenSearch Repository Request - Working Document

## Basic Information

**Are you requesting a new GitHub Repository within opensearch-project GitHub Organization?**
- [x] Yes, requesting new repository
- [ ] No, I have an existing repository

**If existing repository, provide URL:**
N/A

---

## GitHub Repository Proposal
*(Enter 'N/A' if you already have a GitHub Repository)*

**Proposal Requirements:**
1. Review the OpenSearch Software Foundation [charter](https://foundation.opensearch.org/assets/media/OpenSearch%20Project%20Technical%20Charter%20Final%209-13-2024.docx.pdf)
2. Open a proposal issue with [this template](https://github.com/opensearch-project/.github/issues/new?template=PROPOSAL_TEMPLATE.md)
3. Attach the proposal issue URL below

**Proposal Issue URL:**
https://github.com/opensearch-project/.github/issues/439

---

## GitHub Repository Additional Information
*(Enter 'N/A' if you already have a GitHub Repository)*

**1. What is the new GitHub repository name?**
agentops

**2. Project description and community value?**
AgentOps is an open-source observability stack designed for modern distributed systems. Built on OpenTelemetry, OpenSearch, and Prometheus, AgentOps provides a complete, pre-configured infrastructure for monitoring microservices, web applications, and AI agents—with first-class support for agent observability through OpenTelemetry Gen-AI Semantic Conventions.

The project provides immediate value to the community by:
- Offering a 1-click observability stack that "just works" out of the box
- Demonstrating OpenSearch as a unified observability platform with correlated Logs, Traces and Metrics.
- Providing reference implementations for instrumenting AI agents with OpenTelemetry
- Including Docker Compose and OpenSearch configurations for easy deployment

**3. What user problem are you trying to solve with this new repository?**
When building AI agents and distributed systems, developers need to quickly set up observability infrastructure to monitor, debug, and optimize their applications. Currently this requires significant effort to configure and integrate multiple components (OpenSearch, Dashboards, Data Prepper, OpenTelemetry Collector, Prometheus, etc.). Other existing observability stacks have far less onboarding friction (e.g. Grafana [LGTM](https://grafana.com/go/webinar/getting-started-with-grafana-lgtm-stack/))

AgentOps solves this by providing a pre-configured observability stack that developers can deploy with a single command (`docker compose up -d`), allowing them to focus on building their applications rather than infrastructure setup.

**4. Why do we create a new repo at this time?**
This aligns with the OpenSearch product roadmap to position OpenSearch as a unified observability platform. AgentOps demonstrates OpenSearch's capabilities for logs, traces, and metrics in a cohesive, easy-to-deploy package, particularly for the emerging AI agent development space.

**5. Is there any existing projects that is similar to your proposal?**
There is AgentEval currently hosted under the dashboards-traces repository (https://github.com/opensearch-project/dashboards-traces), but that project is supplementary to this repository and focuses on evaluation rather than observability infrastructure.

**6. Should this project be in OpenSearch Core/OpenSearch Dashboards Core? If no, why not? Or, shall we combine this project to an existing repo source code in opensearch-project GitHub Org?**
No, this should be a standalone repository. AgentOps is a deployment/configuration project that orchestrates multiple OpenSearch components (OpenSearch, Data Prepper, OpenSearch Dashboards) along with external tools (OpenTelemetry Collector, Prometheus). It is not core functionality but rather a reference architecture and quickstart solution. Keeping it separate allows for independent versioning and clearer scope.

**7. Is this project an OpenSearch/OpenSearch Dashboards plugin to be included as part of the OpenSearch release?**
No. This is a standalone deployment project that uses OpenSearch and OpenSearch Dashboards as components, not a plugin.

---

## GitHub Repository Owners
*(Enter 'N/A' if you already have a GitHub Repository)*

**1. Who will be supporting this repo going forward?**
Amazon OpenSearch Service team, with Kyle Hounslow ([kylehounslow](https://github.com/kylehounslow)) as the initial maintainer.

**2. What is your plan (including staffing) to be responsive to the community?**
Following the standard OpenSearch maintainer responsibilities as defined in [opensearch-project/.github/RESPONSIBILITIES.md](https://github.com/opensearch-project/.github/blob/main/RESPONSIBILITIES.md#maintainer-responsibilities):
- Respond to enhancement requests, issues, and forum posts as they come in
- Review and provide actionable feedback on pull requests
- Triage and label issues regularly
- Maintain overall health of the repository
- Promote additional maintainers from active contributors

**3. Initial Maintainers List (max 3 users, provide GitHub aliases):**
- ([kylehounslow](https://github.com/kylehounslow))

---

## GitHub Repository Source Code / License / Libraries
*(Enter 'N/A' if you already have a GitHub Repository)*

**1. Please provide the URL to the source code.**
https://github.com/kylehounslow/agentops

**2. What is the license for the source code?**
Apache License 2.0

**3. Does the source code include any third-party code that is not compliant with the Apache License 2.0?**
No. The repository primarily contains configuration files (YAML, Docker Compose, Helm charts) and example Python code. All Python dependencies are Apache 2.0 or MIT licensed (which is compatible with Apache 2.0):
- opentelemetry-* packages: Apache 2.0
- fastapi, uvicorn: MIT
- boto3: Apache 2.0
- langchain*: MIT
- strands-agents*: Apache 2.0

---

## Publication Target(s)

**Select all publication targets you plan to use:**
- [ ] DockerHub Staging
- [ ] DockerHub Production
- [ ] ECR Staging
- [ ] ECR Production
- [ ] Maven Snapshots / Sonatype Nexus
- [ ] Maven Central
- [ ] NPM
- [ ] RubyGems
- [ ] PyPI
- [ ] GO Pkg
- [ ] NuGet
- [ ] PHP Packagist
- [ ] Rust Crates
- [ ] Terraform Provider
- [ ] HuggingFace
- [x] Others: _None - this is a source-code only repository_

---

## Process Overview

### For New Repository Requests:
1. Build Interest Group (BIG) reviews proposal
2. Technical Steering Committee (TSC) votes (needs 3+ positive votes, no vetoes)
3. Linux Foundation creates repository
4. Admin Team configures repository settings

### For Existing Repository + New Publication Targets:
1. Admin Team reviews request and follows up

**Track progress:** https://github.com/orgs/opensearch-project/projects/208/views/33

**Estimated timeline:** 14-21 days from request submission
