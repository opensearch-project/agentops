# ATLAS Docker Compose Deployment

This directory contains the Docker Compose configuration for running the ATLAS observability stack locally.

## Directory Structure

```
docker-compose/
├── docker-compose.yml              # Main orchestration file - defines all services
├── .env                            # Environment variables (versions, ports, credentials)
├── otel-collector/                 # OpenTelemetry Collector configuration
│   └── config.yaml
├── data-prepper/                   # Data Prepper configuration
│   ├── pipelines.yaml
│   └── data-prepper-config.yaml
├── prometheus/                     # Prometheus configuration
│   └── prometheus.yml
├── opensearch-dashboards/          # OpenSearch Dashboards configuration
│   └── opensearch_dashboards.yml
└── canary/                         # Canary service (optional example)
    ├── Dockerfile
    └── canary.py
```

The main `docker-compose.yml` file is located in the repository root and references configuration files from this directory's subdirectories. Each service has its own subdirectory containing its specific configuration files. OpenSearch uses default configuration with environment variables set in docker-compose.yml.

## Quick Start

**Note**: The `.env` file in the repository root contains all configurable parameters including component versions, ports, credentials, and resource limits. You can customize these values before starting the stack.

**macOS users**: If you're using Finch instead of Docker, replace `docker compose` with `finch compose` in all commands below.

1. **Start the core stack:**
   ```bash
   docker compose up -d
   ```

   **Or start with example services:**
   ```bash
   docker compose --profile examples up -d
   ```

2. **Verify services are running:**
   ```bash
   docker-compose ps
   ```

3. **Access the UIs:**
   - OpenSearch Dashboards: http://localhost:5601
   - Prometheus: http://localhost:9090
   - OpenSearch API: http://localhost:9200
   - Weather Agent API (if examples enabled): http://localhost:8000

4. **View telemetry data:**
   
   **If using example services:**
   - View canary logs: `docker-compose logs -f canary`
   - See metrics in Prometheus: http://localhost:9090 (query: `gen_ai_client_token_usage_total`)
   - See traces in OpenSearch Dashboards: http://localhost:5601 (Observability → Trace Analytics)
   
   **Send your own test data:**
   Configure your agent application to send OTLP data to:
   - gRPC: `http://localhost:4317`
   - HTTP: `http://localhost:4318`

5. **Stop the stack:**
   ```bash
   docker-compose down
   ```

6. **Stop and remove data:**
   ```bash
   docker-compose down -v
   ```

## Services

### Core Services (Always Running)

- **otel-collector**: Receives OTLP telemetry data (ports 4317, 4318, 8888)
- **data-prepper**: Processes logs and traces before OpenSearch ingestion (ports 21890, 21892)
- **opensearch**: Stores logs and traces with security enabled (port 9200, 9600)
  - Default credentials: admin/My_password_123!@# (configured in .env file)
- **prometheus**: Stores metrics with OTLP receiver enabled (port 9090)
- **opensearch-dashboards**: Visualization UI (port 5601)

### Optional Example Services (Profile: examples)

These services demonstrate how to instrument an agent application and generate test telemetry:

- **weather-agent**: Example FastAPI server with OpenTelemetry instrumentation (port 8000)
  - Demonstrates Gen-AI semantic conventions
  - Provides REST API for agent invocation
  - Sends traces, metrics, and logs to ATLAS stack
- **canary**: Periodic test client that invokes weather-agent (no exposed ports)
  - Generates synthetic agent traffic every 30 seconds (configurable)
  - Validates the observability pipeline end-to-end
  - Useful for testing and demonstrations

**To enable example services:**
```bash
# Start core services + examples
docker compose --profile examples up -d

# Stop example services only
docker compose stop weather-agent canary

# Remove example services
docker compose --profile examples down
```

## Configuration Files

All configuration files are organized by service in subdirectories:

- **.env**: Environment variables for versions, ports, credentials, and resource limits (in repository root)
- **docker-compose.yml**: Main service definitions and orchestration (in repository root)
- **otel-collector/config.yaml**: OpenTelemetry Collector receivers, processors, and exporters
- **data-prepper/pipelines.yaml**: Data transformation pipelines for logs and traces
- **data-prepper/data-prepper-config.yaml**: Data Prepper server settings
- **prometheus/prometheus.yml**: Prometheus scrape targets and storage configuration
- **opensearch-dashboards/opensearch_dashboards.yml**: Dashboard UI settings

OpenSearch uses default configuration with settings provided via environment variables in docker-compose.yml.

### Customizing Configuration

**To change versions, ports, or credentials**: Edit the `.env` file in the repository root and restart services:
```bash
docker-compose down
docker compose up -d
```

**To modify service behavior**: Edit the configuration file in its respective subdirectory and restart the service:
```bash
docker-compose restart <service-name>
```

**To customize example services**: Edit the `.env` file:
- `WEATHER_AGENT_PORT`: Port for weather-agent API (default: 8000)
- `CANARY_INTERVAL`: Seconds between canary invocations (default: 30)
- `WEATHER_AGENT_MEMORY_LIMIT`: Memory limit for weather-agent (default: 200M)
- `CANARY_MEMORY_LIMIT`: Memory limit for canary (default: 100M)

**To modify weather-agent or canary code**: After editing code in `examples/plain-agents/weather-agent/` or `docker-compose/canary.py`:
```bash
# Rebuild the service with no cache
docker-compose build --no-cache weather-agent
# Or for canary
docker-compose build --no-cache canary

# Restart the service
docker-compose restart weather-agent
# Or restart both
docker compose --profile examples up -d --build
```

The docker-compose.yml file mounts these configurations into the containers.

## Data Retention

- **Logs and Traces**: Managed by OpenSearch index lifecycle policies (default: unlimited in development)
- **Metrics**: 15 days (configured in Prometheus)

Adjust retention periods by modifying the respective configuration files or OpenSearch index settings.

## Resource Requirements

**Minimum:**
- 4GB RAM
- 10GB disk space

**Recommended:**
- 8GB RAM
- 20GB disk space

## Troubleshooting

**Services won't start:**
```bash
docker-compose logs <service-name>
```

**Check OpenSearch health:**
```bash
curl http://localhost:9200/_cluster/health?pretty
```

**Check if data is being ingested:**
```bash
curl http://localhost:9200/_cat/indices?v
```

**Reset everything:**
```bash
docker-compose down -v
docker compose up -d
```

## Security Warning

⚠️ **This configuration is for development only!**

Security considerations:
- OpenSearch has security enabled with default credentials (admin/admin)
- SSL certificate verification is disabled for development ease
- Permissive CORS settings
- No network isolation between services

For production use:
- Change default passwords
- Enable proper SSL/TLS with valid certificates
- Configure proper authentication and authorization
- Implement network policies
- Review and harden all security settings

Never use this configuration in production without proper hardening.

## Next Steps

- See the main README.md for instrumentation examples
- Check the examples/ directory for code samples
- Visit OpenSearch Dashboards to create visualizations
- Configure your agent applications to send OTLP data
