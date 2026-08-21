# AGENTS.md - AI-Optimized Repository Documentation

This document provides structured information about the Observability Stack repository specifically designed for AI coding assistants. It explains the repository structure, conventions, and common development tasks to enable efficient code generation and modification.

## Repository Purpose

Observability Stack is a configuration-based repository that provides a quickstart observability stack for AI agent development. The repository contains:

- Docker Compose configurations for local deployment
- Helm charts for Kubernetes deployment
- Configuration files for OpenTelemetry, Data Prepper, OpenSearch, Prometheus, and OpenSearch Dashboards
- Example code for instrumenting agent applications
- Documentation optimized for both humans and AI assistants

## Repository Structure

```
observability-stack/
├── docker-compose.yml           # Main Docker Compose service definitions
├── docker-compose.examples.yml  # Example services (included via .env)
├── .env                         # Environment variables for Docker Compose
├── docker-compose/              # Docker Compose configuration files
│   ├── README.md                # Docker Compose documentation
│   ├── EXAMPLES.md              # Example services documentation
│   ├── otel-collector/          # OpenTelemetry Collector configuration
│   │   └── config.yaml
│   ├── data-prepper/            # Data Prepper pipeline configuration
│   │   ├── pipelines.template.yaml
│   │   └── data-prepper-config.yaml
│   ├── prometheus/              # Prometheus configuration
│   │   └── prometheus.yml
│   ├── opensearch-dashboards/   # OpenSearch Dashboards configuration
│   │   └── opensearch_dashboards.yml
│   └── canary/                  # Canary service (optional example)
│       ├── Dockerfile
│       └── canary.py
├── helm/                        # Kubernetes Helm charts
│   └── observability-stack/                # Main Helm chart
│       ├── Chart.yaml           # Chart metadata
│       ├── values.yaml          # Configurable parameters
│       └── templates/           # Kubernetes resource templates
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           └── pvc.yaml
├── examples/                    # Instrumentation examples
│   ├── plain-agents/            # Plain agent examples
│   │   ├── weather-agent/       # Weather agent with FastAPI server
│   │   │   ├── Dockerfile
│   │   │   ├── main.py
│   │   │   ├── server.py
│   │   │   └── README.md
│   │   └── multi-agent-planner/ # Multi-agent orchestration example
│   │       ├── orchestrator/    # Travel planner (fans out to sub-agents)
│   │       └── events-agent/    # Events lookup agent
│   ├── langchain/               # LangChain examples
│   └── strands/                 # Strands examples
├── docs/                        # Additional documentation
├── .kiro/                       # Kiro AI assistant configuration
│   ├── specs/                   # Feature specifications
│   └── steering/                # Context-specific guidance
├── README.md                    # Main documentation
├── AGENTS.md                    # This file
├── CONTRIBUTING.md              # Contribution guidelines
└── MAINTAINERS.md               # Maintainer information
```

## Directory Organization

### docker-compose/

Contains all files needed for local Docker Compose deployment. Each component has its own subdirectory with configuration files.

**Key Files**:
- `docker-compose.yml`: Defines core observability services (including opensearch-dashboards-init), dependencies, ports, and volumes (in repository root)
- `docker-compose.examples.yml`: Defines example services (weather-agent, canary) included via .env (in repository root)
- `.env`: Environment variables for easy configuration customization (in repository root)
  - `INCLUDE_COMPOSE_FILES`: Controls which additional compose files to include (default: `docker-compose.examples.yml`)
- `README.md`: Comprehensive documentation for Docker Compose deployment
- `QUICK_START.md`: Step-by-step quick start guide
- `CHANGELOG.md`: History of configuration changes and updates
- `otel-collector/config.yaml`: OpenTelemetry Collector receivers, processors, and exporters
- `data-prepper/pipelines.template.yaml`: Data transformation pipeline template for logs and traces (credentials injected at container startup)
- `data-prepper/data-prepper-config.yaml`: Data Prepper server configuration
- `prometheus/prometheus.yml`: Prometheus scrape and storage configuration
- `opensearch-dashboards/opensearch_dashboards.yml`: Dashboard UI configuration
- `opensearch-dashboards/init/`: Initialization script and saved query configurations

**Note**: OpenSearch uses default configuration with settings provided via environment variables in docker-compose.yml and .env file.

**Example Services**: The multi-agent planner (travel-planner, weather-agent, events-agent) and canary services are defined in `docker-compose.examples.yml` and included by default. To disable them, comment out `INCLUDE_COMPOSE_FILES=docker-compose.examples.yml` in the `.env` file.

### Prometheus Configuration

```yaml
global:
  scrape_interval: 60s
  scrape_timeout: 10s
  evaluation_interval: 60s
  external_labels:
    cluster: 'observability-stack-dev'
    environment: 'development'

# OTLP configuration for receiving metrics
otlp:
  keep_identifying_resource_attributes: true
  promote_resource_attributes:
    - service.instance.id
    - service.name
    - service.namespace
    - service.version
    - deployment.environment.name
    # Gen-AI semantic convention attributes
    - gen_ai.agent.id
    - gen_ai.agent.name
    - gen_ai.provider.name
    - gen_ai.request.model
    - gen_ai.response.model

storage:
  tsdb:
    out_of_order_time_window: 30m

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8888']
    scrape_interval: 10s
```

**Key Changes from Previous Version**:
- Added OTLP configuration for resource attribute promotion
- Added gen-ai semantic convention attributes to promoted attributes
- Configured out-of-order time window for handling delayed metrics
- Simplified scrape configuration

### helm/observability-stack/

Contains Kubernetes Helm chart for production-like deployments.

**Key Files**:
- `Chart.yaml`: Chart metadata (name, version, description)
- `values.yaml`: All configurable parameters with defaults
- `templates/`: Kubernetes resource definitions using Go templating

### aws/cdk/

Contains the AWS CDK app (TypeScript) for a managed AWS deployment: OpenSearch, Amazon Managed Prometheus, an OSIS ingestion pipeline, the OpenSearch Application and dashboards, and an optional demo EC2 instance (`enableDemo`).

**Key Files**:
- `bin/app.ts`: App entry; instantiates `ObsInfra` and `ObservabilityStack`
- `lib/demo-workload.ts`: Optional EC2 demo; its user-data is a Docker Compose bring-up injected via CloudFormation `Fn::Sub`
- `custom-resources/`: UI-init and FGAC role-mapping resources

**Gotcha**: the demo user-data in `lib/demo-workload.ts` is a single CloudFormation `Fn::Sub` string, so a bare shell `${VAR}` (even inside a comment) is read as a template reference and fails synth or deploy with `Unresolved resource dependencies [...]`. Escape shell variables as `${!VAR}`; `$(...)` command substitution is safe. `${OsiEndpoint}` is the one intentional `Fn::Sub` variable.

### examples/

Contains working code examples for instrumenting agent applications with OpenTelemetry.

**Organization**:
- By language: `python/`, `javascript/`
- By framework: `frameworks/langchain/`, `frameworks/crewai/`

**Each example should demonstrate**:
- OTLP exporter configuration
- Agent invocation tracing
- Tool execution tracing
- Gen-AI semantic convention attributes
- Structured logging

### .kiro/steering/

Contains context-specific guidance for AI coding assistants. These files are automatically included when relevant files are in context.

**Steering Files**:
- `observability-stack-development.md`: Always included, explains Observability Stack conventions
- `docker-compose-patterns.md`: Included when editing docker-compose files
- `helm-chart-patterns.md`: Included when editing Helm charts
- `observability-patterns.md`: Always included, explains OpenTelemetry patterns

## Naming Conventions

### Files and Directories

- **kebab-case**: All files and directories use lowercase with hyphens
  - ✅ `docker-compose.yml`, `otel-collector/`, `data-prepper/`
  - ❌ `dockerCompose.yml`, `otelCollector/`, `data_prepper/`

### Configuration Files

- **Component-specific**: Configuration files are named after their component
  - `config.yaml` for OpenTelemetry Collector
  - `pipelines.template.yaml` for Data Prepper
  - `prometheus.yml` for Prometheus

### Services in docker-compose.yml

- **Descriptive names**: Service names match component names
  - `otel-collector`, `data-prepper`, `opensearch`, `prometheus`, `opensearch-dashboards`

## Configuration Patterns

### Environment Variables

The `.env` file in the docker-compose directory provides centralized configuration:

```env
# OpenSearch Configuration
OPENSEARCH_VERSION=3.4.0
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD='My_password_123!@#'
OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200

# OpenTelemetry Collector Configuration
OTEL_COLLECTOR_VERSION=0.143.0
OTEL_COLLECTOR_HOST=otel-collector
OTEL_COLLECTOR_PORT_GRPC=4317
OTEL_COLLECTOR_PORT_HTTP=4318

# Data Prepper Configuration
DATA_PREPPER_VERSION=2.13.0
DATA_PREPPER_OTLP_PORT=21890

# Prometheus Configuration
PROMETHEUS_VERSION=v3.8.1
PROMETHEUS_PORT=9090
PROMETHEUS_RETENTION=15d
```

**Key Principles**:
- Centralize configuration in .env file
- Use environment variables in docker-compose.yml
- Document all variables with comments
- Provide sensible defaults for development

### Docker Compose Services

Each service definition follows this pattern:

```yaml
service-name:
  image: vendor/image:version
  container_name: service-name
  ports:
    - "host:container"
  volumes:
    - ./config-dir:/container-config-path
    - data-volume:/container-data-path
  environment:
    - ENV_VAR=value
  depends_on:
    dependency-service:
      condition: service_healthy  # Wait for health check
  networks:
    - observability-stack-network
  restart: unless-stopped
  deploy:
    resources:
      limits:
        memory: 200M
  logging:
    driver: "json-file"
    options:
      max-size: "5m"
      max-file: "2"
```

**Key Principles**:
- Use specific image versions (not `latest`)
- Mount configuration files as volumes
- Use named volumes for data persistence
- Declare service dependencies with health checks
- Use a shared network for inter-service communication
- Set resource limits to prevent resource exhaustion
- Configure log rotation to prevent disk space issues

### OpenTelemetry Collector Configuration

Structure: Receivers → Processors → Exporters

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins:
            - "http://*"
            - "https://*"

processors:
  memory_limiter:
    check_interval: 5s
    limit_percentage: 80
    spike_limit_percentage: 25
  batch:
    timeout: 10s
    send_batch_size: 1024
  resourcedetection:
    detectors: [env, docker, system]
  transform:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          # Flatten nested dotted keys to prevent OpenSearch mapping conflicts
          - set(attributes["db_system_name"], attributes["db.system.name"]) where attributes["db.system.name"] != nil
          - delete_key(attributes, "db.system.name")

exporters:
  debug:
    verbosity: detailed
  otlp/opensearch:
    endpoint: "data-prepper:21890"
    tls:
      insecure: true
  otlphttp/prometheus:
    endpoint: "http://prometheus:9090/api/v1/otlp"
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [resourcedetection, memory_limiter, transform, batch]
      exporters: [otlp/opensearch, debug]
    metrics:
      receivers: [otlp]
      processors: [resourcedetection, memory_limiter, batch]
      exporters: [otlphttp/prometheus, debug]
    logs:
      receivers: [otlp]
      processors: [resourcedetection, memory_limiter, transform, batch]
      exporters: [otlp/opensearch, debug]
```

**Key Changes from Previous Version**:
- Added `transform` processor to handle nested dotted attribute keys
- Added `resourcedetection` processor for environment context
- Changed exporter names to `otlp/opensearch` and `otlphttp/prometheus`
- Added `debug` exporter for troubleshooting
- Improved memory limiter with spike limits

### Data Prepper Pipelines

Structure: Source → Processors → Sink

```yaml
# Main routing pipeline
otlp-pipeline:
  delay: 10
  source:
    otlp:
      port: 21890
      ssl: false
      http:
        port: 21892
  route:
    - logs: "getEventType() == \"LOG\""
    - traces: "getEventType() == \"TRACE\""
  sink:
    - pipeline:
        name: "otel-logs-pipeline"
        routes: ["logs"]
    - pipeline:
        name: "otel-traces-pipeline"
        routes: ["traces"]

# Log processing pipeline
otel-logs-pipeline:
  workers: 5
  delay: 10
  source:
    pipeline:
      name: "otlp-pipeline"
  buffer:
    bounded_blocking:
  sink:
    - opensearch:
        hosts: ["https://opensearch:9200"]
        username: OPENSEARCH_USER
        password: OPENSEARCH_PASSWORD
        insecure: true
        index_type: log-analytics-plain

# Trace processing pipeline
otel-traces-pipeline:
  delay: 100
  source:
    pipeline:
      name: "otlp-pipeline"
  sink:
    - pipeline:
        name: "traces-raw-pipeline"
    - pipeline:
        name: "service-map-pipeline"

# Raw trace storage
traces-raw-pipeline:
  source:
    pipeline:
      name: "otel-traces-pipeline"
  processor:
    - otel_trace_raw:
  sink:
    - opensearch:
        hosts: ["https://opensearch:9200"]
        username: OPENSEARCH_USER
        password: OPENSEARCH_PASSWORD
        insecure: true
        index_type: trace-analytics-plain-raw

# Service map generation
service-map-pipeline:
  delay: 100
  source:
    pipeline:
      name: "otel-traces-pipeline"
  processor:
    - service_map_stateful:
  sink:
    - opensearch:
        hosts: ["https://opensearch:9200"]
        username: OPENSEARCH_USER
        password: OPENSEARCH_PASSWORD
        insecure: true
        index_type: trace-analytics-service-map
```

**Key Changes from Previous Version**:
- Simplified to use main routing pipeline with sub-pipelines
- Changed to use OpenSearch built-in index types (log-analytics-plain, trace-analytics-plain-raw, trace-analytics-service-map)
- Added service map generation for trace visualization
- Enabled HTTPS for OpenSearch connections with authentication
- Removed custom index patterns in favor of OpenSearch managed indices

### OpenSearch Configuration

OpenSearch now uses environment variables for configuration instead of a custom opensearch.yml file:

```yaml
opensearch:
  image: opensearchproject/opensearch:3.4.0
  container_name: opensearch
  environment:
    - cluster.name=observability-stack-cluster
    - node.name=observability-stack-node
    - discovery.type=single-node
    - bootstrap.memory_lock=true
    - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
    - "OPENSEARCH_INITIAL_ADMIN_PASSWORD=admin"
  volumes:
    - opensearch-data:/usr/share/opensearch/data
  ports:
    - "9200:9200"
    - "9600:9600"
  healthcheck:
    test: curl -s -k -u admin:My_password_123!@# https://localhost:9200/_cluster/health | grep -E '"status":"(green|yellow)"'
    start_period: 30s
    interval: 5s
    timeout: 10s
    retries: 30
```

**Key Changes from Previous Version**:
- Removed custom opensearch.yml configuration file
- Using environment variables for all settings
- Enabled security with OPENSEARCH_INITIAL_ADMIN_PASSWORD
- Added health check using cluster health API with authentication
- Simplified configuration by relying on OpenSearch defaults
- No longer need ISM policy setup script - using OpenSearch built-in index management

Organize by component with consistent structure:

```yaml
component:
  enabled: true
  replicaCount: 1
  image:
    repository: vendor/image
    tag: version
    pullPolicy: IfNotPresent
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1000m"
  service:
    type: ClusterIP
    port: 8080
  persistence:
    enabled: true
    size: 10Gi
    storageClass: standard
```

## Common Development Tasks

### Starting the Stack

By default, this starts all services including example agents (travel-planner, weather-agent, events-agent, and canary):

```bash
docker compose up -d
```

To start only the core observability stack without examples, edit `.env` and comment out:
```env
# INCLUDE_COMPOSE_FILES=docker-compose.examples.yml
```

Then start the stack:
```bash
docker compose up -d
```

**Note for macOS users**: Some macOS users use Finch as an alternative to Docker. If you're using Finch, replace `docker compose` with `finch compose` in all commands:
```bash
finch compose up -d
```

### Checking Service Health

```bash
# Check all services
docker-compose ps

# Check OpenSearch health (with authentication - use password from .env)
curl -k -u admin:My_password_123!@# https://localhost:9200/_cluster/health?pretty

# Check Prometheus
curl http://localhost:9090/-/healthy

# Check OpenTelemetry Collector metrics
curl http://localhost:8888/metrics
```

### Viewing Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs otel-collector

# Follow logs
docker-compose logs -f data-prepper
```

### Stopping the Stack

```bash
# Stop but keep data
docker-compose down

# Stop and remove data
docker-compose down -v
```

### Modifying Configuration

1. **Edit configuration file** in the appropriate subdirectory
2. **Restart the affected service**:
   ```bash
   docker-compose restart <service-name>
   ```
3. **Verify changes**:
   ```bash
   docker-compose logs <service-name>
   ```

**Note**: If the service uses a custom `build` directive (like the canary service), you must rebuild the container to apply code changes:
```bash
# Rebuild the service with no cache
docker-compose build --no-cache <service-name>

# Restart the service
docker-compose restart <service-name>

# Or rebuild and restart in one command
docker compose up -d --build <service-name>
```

**Note**: If using Finch instead of Docker, replace `docker-compose` with `finch compose` in the commands above.

### Changing Environment Variables

1. **Edit `.env` file** in repository root
2. **Recreate services** to apply changes:
   ```bash
   docker-compose down
   docker compose up -d
   ```

### Managing Example Services

Example services (weather-agent and canary) are defined in `docker-compose.examples.yml` and included via `.env`:

**To disable examples:**
1. Edit `.env` and comment out:
   ```env
   # INCLUDE_COMPOSE_FILES=docker-compose.examples.yml
   ```
2. Restart: `docker compose down && docker compose up -d`

**To re-enable examples:**
1. Uncomment the line in `.env`
2. Restart the stack

**To add custom services:**
1. Create `docker-compose.custom.yml`
2. Update `.env`: `INCLUDE_COMPOSE_FILES=docker-compose.examples.yml,docker-compose.custom.yml`

### Changing OpenSearch Password

1. **Edit `.env` file**:
   ```env
   OPENSEARCH_PASSWORD=your-new-password
   ```

2. **Restart services** (remove volumes to clear stale credentials):
   ```bash
   docker compose down -v
   docker compose up -d
   ```

Data Prepper uses a template (`pipelines.template.yaml`) with credential placeholders that are injected from `.env` at container startup — no manual edits needed. OpenSearch Dashboards also reads credentials from `.env` automatically.

1. Add service definition to `docker-compose.yml`:
```yaml
new-service:
  image: vendor/new-service:version
  container_name: new-service
  ports:
    - "8080:8080"
  volumes:
    - ./new-service:/config
  depends_on:
    - existing-service
  networks:
    - observability-stack-network
```

2. Create configuration directory: `mkdir -p docker-compose/new-service`
3. Add configuration file: `docker-compose/new-service/config.yaml`
4. Update README.md with new service information
5. Add health check if applicable

### Modifying Port Mappings

1. Locate service in `docker-compose.yml`
2. Update `ports` section:
```yaml
ports:
  - "new-host-port:container-port"
```
3. Update README.md to document new port
4. Update firewall rules if needed

### Adjusting Resource Limits

**Docker Compose**: Add resource limits to service:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '1.0'
      memory: 1G
```

**Helm**: Update `values.yaml`:
```yaml
component:
  resources:
    requests:
      memory: "1Gi"
      cpu: "1000m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
```

### Adding a New Example

1. Create directory: `examples/<language>/`
2. Create example file with clear comments
3. Include:
   - OTLP exporter setup
   - Tracer/logger configuration
   - Agent operation instrumentation
   - Gen-AI semantic convention attributes
4. Add README.md in example directory explaining usage
5. Update main README.md to reference new example

**Note**: If the example is used by a Docker Compose service with a custom build (like the canary), you must rebuild the container after making changes:
```bash
docker-compose build --no-cache <service-name>
docker-compose restart <service-name>
```

### Modifying Data Retention

**OpenSearch**: Set `ISM_RETENTION_DAYS` in `.env` (default: 7 days). The init script configures ISM policies with rollover + delete. Set to `0` to disable automatic deletion.
```env
ISM_RETENTION_DAYS=7
```
**Prometheus**: Set `PROMETHEUS_RETENTION` in `.env`:
```env
PROMETHEUS_RETENTION=15d
```

### Adding Configuration Comments

All configuration files should include inline comments explaining:
- Purpose of each section
- Key configuration parameters
- Default values and why they were chosen
- Security implications
- Performance considerations

Example:
```yaml
# OpenTelemetry Collector receives telemetry data via OTLP protocol
receivers:
  otlp:
    protocols:
      # gRPC endpoint for high-performance binary protocol
      grpc:
        endpoint: 0.0.0.0:4317  # Listen on all interfaces for development
      # HTTP endpoint for easier debugging and browser compatibility
      http:
        endpoint: 0.0.0.0:4318
```

## Testing Changes

### Local Testing with Docker Compose

1. Start the stack:
```bash
docker compose up -d
```

2. Verify services are running:
```bash
docker-compose ps
```

3. Check logs for errors:
```bash
docker-compose logs <service-name>
```

4. Send test data:
```bash
python examples/python/sample_agent.py
```

5. Verify data in OpenSearch:
```bash
curl http://localhost:9200/_cat/indices?v
```

6. Stop the stack:
```bash
docker-compose down
```

**Important**: If you modified code in services with custom builds (e.g., canary service), rebuild before testing:
```bash
# Rebuild the service
docker-compose build --no-cache canary

# Restart to apply changes
docker-compose restart canary

# Or rebuild and restart in one step
docker compose up -d --build canary
```

### Testing Helm Charts

1. Validate chart syntax:
```bash
helm lint helm/observability-stack
```

2. Render templates locally:
```bash
helm template observability-stack helm/observability-stack
```

3. Deploy to test cluster:
```bash
helm install observability-stack-test helm/observability-stack
```

4. Verify pods:
```bash
kubectl get pods
kubectl logs <pod-name>
```

5. Clean up:
```bash
helm uninstall observability-stack-test
```

## Code Style Guidelines

### YAML Files

- Use 2 spaces for indentation
- Include inline comments for complex configurations
- Group related settings together
- Use consistent key ordering (image, ports, volumes, environment, depends_on)

### Documentation

- Use Markdown for all documentation
- Include code examples with syntax highlighting
- Provide both quick start and detailed explanations
- Include troubleshooting sections

### Docs Site Development Workflow

The docs site is built with [Starlight](https://starlight.astro.build/) (Astro). Source files are in `docs/starlight-docs/`.

**Required workflow for all docs changes:**

1. **Build** — validates internal links via `starlight-links-validator` plugin. The build will fail if any internal links are broken. Never skip this step.
   ```bash
   cd docs/starlight-docs && npm install && npm run build
   ```

2. **Preview** — start a local preview server and visually verify changes.
   ```bash
   bash docs/starlight-docs/test/preview.sh          # start server
   # Open http://localhost:4321/docs in browser
   bash docs/starlight-docs/test/preview.sh --stop    # stop server
   ```

3. **Rebuild after changes** — if you make further edits, rebuild before previewing:
   ```bash
   bash docs/starlight-docs/test/preview.sh --stop
   bash docs/starlight-docs/test/preview.sh --build
   bash docs/starlight-docs/test/preview.sh
   ```

**Critical rules:**
- **Never start the astro server directly** (e.g. `npx astro preview`, `nohup`, `npm run preview`). Always use `test/preview.sh` — it handles background process management correctly. Direct invocations will block the terminal.
- **Always build before previewing.** The link validator only runs during build. Previewing without building first will show stale output.
- **Never use `grep -P` (Perl regex)** — macOS does not support it. Use `sed` or `grep -E` instead.
- **Verify the server is responding** after starting preview by checking `curl -s http://localhost:4321/docs` returns 200 before telling the user it's ready.

**Sidebar configuration:**
- Sidebar labels and ordering are configured in `docs/starlight-docs/astro.config.mjs` — this is the single source of truth.
- **Do not use frontmatter `sidebar.label` or `sidebar.order` to control group/section headings.** Frontmatter only controls individual page labels, not the group name shown in the sidebar for a directory. Use explicit `items` with `label` in `astro.config.mjs` instead (see "Send Data" and "Get Started" sections as examples).
- Sections using `autogenerate` derive group labels from directory names (lowercase). Replace `autogenerate` with explicit `items` when proper casing or custom ordering is needed.

**llms.txt:**
- `docs/public/llms.txt` is a maintained artifact, served at the site root (`https://observability.opensearch.org/llms.txt`). It lists every docs page with a one-line description, for AI assistants and other automated readers.
- It is generated, not hand-written. Regenerate it whenever a page is added, removed, or renamed, or a page's `title`/`description` frontmatter changes. Do not hand-edit `docs/public/llms.txt` directly.
- The generator config lives in `docs/starlight-docs/llms-txt/`. All links in the file are fully qualified `https://observability.opensearch.org/...` URLs, not relative paths, because the file is read out of page context.

### Icons

Use OpenSearch UI (OUI) icons for documentation components. Browse the full set at https://oui.opensearch.org/1.23/#/display/icons. SVG sources are at https://github.com/opensearch-project/oui/tree/main/src/components/icon/assets. Prefer 32x32 icons over 16x16 for consistent sizing.

### Examples

- Include complete, runnable code
- Add comments explaining each step
- Show both basic and advanced usage
- Follow language-specific conventions

## Gen-AI Semantic Conventions

When creating examples or documentation, always reference the OpenTelemetry Gen-AI Semantic Conventions:

**Key Attributes**:
- `gen_ai.operation.name`: Operation type (invoke_agent, execute_tool, chat)
- `gen_ai.agent.id`: Unique agent identifier
- `gen_ai.agent.name`: Human-readable agent name
- `gen_ai.request.model`: Model requested
- `gen_ai.usage.input_tokens`: Input token count
- `gen_ai.usage.output_tokens`: Output token count
- `gen_ai.tool.name`: Tool being executed

**Span Types**:
- `invoke_agent`: Agent invocation span
- `execute_tool`: Tool execution span
- `chat`: LLM chat completion span

## Development Workflow

1. **Make Changes**: Edit configuration or code files
2. **Add Comments**: Explain key settings inline
3. **Test Locally**: Use docker-compose to verify changes
4. **Update Documentation**: Reflect changes in README.md and AGENTS.md if repository structure or conventions change
5. **Validate**: Run linters and validation tests
6. **Commit**: Use descriptive commit messages
7. **Submit PR**: Follow CONTRIBUTING.md guidelines


## Multi-Agent Development with Worktrees

When multiple agents or sessions work on this repo simultaneously, each feature branch gets its own worktree for isolation.

### Structure

```
observability-stack/
├── .worktrees/                    # gitignored — one per feature branch
│   ├── feat-self-monitoring/
│   ├── feat-helm-charts/
│   └── fix-docs/
└── ...                            # main branch
```

### Usage

```bash
# Create
mkdir -p .worktrees
git worktree add .worktrees/<branch-name> <branch-name>

# REQUIRED: Clean up after PR merge
git worktree remove .worktrees/<branch-name>
git branch -d <branch-name>
```

**You MUST remove worktrees after their PR is merged.** Stale worktrees waste disk space and cause confusion about what work is active.

**Terraform limitation:** Terraform state is local and lives in the main repo's `terraform/aws/` directory. It is NOT shared across worktrees. Only run `terraform plan/apply` from the main repo, never from a worktree.

## Common Pitfalls to Avoid

- ❌ Using `latest` image tags (use specific versions)
- ❌ Hardcoding localhost (use service names in docker-compose)
- ❌ Missing service dependencies in docker-compose
- ❌ Forgetting to expose ports
- ❌ Not including inline comments in configurations
- ❌ Inconsistent naming conventions
- ❌ Missing health checks
- ❌ Not updating documentation after changes

## Questions to Ask When Modifying Code

1. Does this change require updating documentation?
2. Does this change affect repository structure or conventions documented in AGENTS.md?
3. Are all configuration files properly commented?
4. Do service dependencies need to be updated?
5. Are port mappings documented?
6. Does this work in both docker-compose and Helm?
7. Are resource limits appropriate?
8. Is this change secure for development use?
9. Does this follow the repository's naming conventions?
10. **Does this change affect authentication or credentials?** (If yes, update all affected services)
11. **Does this change affect OpenSearch index patterns?** (If yes, verify Data Prepper pipelines)
12. **Does this change affect OTLP endpoints?** (If yes, verify collector exporters)

## Important Notes for AI Agents

### Authentication Changes

When modifying OpenSearch credentials:
1. Update `.env` file (single source of truth)
2. Restart all services with `docker compose down -v && docker compose up -d`

Data Prepper uses a template (`pipelines.template.yaml`) with placeholders processed at container startup via `command:` in docker-compose.yml. No manual credential edits needed in pipeline configs.

### Configuration File Locations

- **OpenSearch**: No custom config file - uses environment variables in docker-compose.yml
- **OpenTelemetry Collector**: `docker-compose/otel-collector/config.yaml`
- **Data Prepper**: `docker-compose/data-prepper/pipelines.template.yaml` (credentials injected at startup) and `docker-compose/data-prepper/data-prepper-config.yaml`
- **Prometheus**: `docker-compose/prometheus/prometheus.yml`
- **OpenSearch Dashboards**: `docker-compose/opensearch-dashboards/opensearch_dashboards.yml`
- **Environment Variables**: `.env` file in repository root

### Index Management

OpenSearch uses ISM (Index State Management) policies for index lifecycle, configured automatically by the init script:
- **Traces**: `otel-v1-apm-span-*` — rollover at 50GB/24h, delete after `ISM_RETENTION_DAYS`
- **Logs**: `logs-otel-v1-*` — rollover at 50GB/24h, delete after `ISM_RETENTION_DAYS`
- **Service Maps**: `otel-v2-apm-service-map-*` — rollover at 10GB/24h, delete after `ISM_RETENTION_DAYS`

Data Prepper creates rollover-only policies on startup. The init script overrides them to add a delete state. Data Prepper uses PUT-if-absent semantics and will not overwrite existing policies on restart.

### Health Checks

Services use health checks for proper startup ordering:
- OpenSearch: Cluster health API with authentication
- Other services depend on OpenSearch being healthy

When adding new services, consider adding health checks if they depend on other services.

### Security Considerations

Development configuration includes:
- OpenSearch security enabled with default admin/admin credentials
- SSL certificate verification disabled for development
- CORS enabled for all origins
- No network isolation

Always document security implications of configuration changes.

## Additional Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OpenSearch Documentation](https://opensearch.org/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Helm Documentation](https://helm.sh/docs/)
- [Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

---

This document is maintained to help AI coding assistants understand and work effectively with the Observability Stack repository. When in doubt, prioritize clarity, consistency, and comprehensive documentation.
