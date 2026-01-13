# ATLAS - Agent Traces Logging Analytics Stack

> ⚠️ **Production Readiness Warning**: ATLAS is designed for development and testing environments. It requires additional hardening, security configuration, and operational procedures before use in production. See [Production Readiness](#production-readiness) for details.

ATLAS (Agent Tracing Logging Analytics Stack) is an open-source quickstart observability stack specifically designed for AI agent observability. It provides a complete, pre-configured infrastructure that enables developers to quickly deploy and monitor their agent applications using industry-standard observability tools.

## Overview

ATLAS combines OpenSearch, OpenTelemetry, Prometheus, and OpenSearch Dashboards into a unified stack that ingests, processes, stores, and visualizes telemetry data from AI agents. The stack follows the [OpenTelemetry Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) to provide standardized observability for agent operations, tool executions, and evaluations. 

![](./docs/atlas-arch.excalidraw.png)

### Components

- **OpenTelemetry Collector**: Receives OTLP data and routes it to appropriate backends
- **Data Prepper**: Transforms and enriches logs and traces before storage
- **OpenSearch**: Stores and indexes logs and traces for search and analysis
- **Prometheus**: Stores time-series metrics data
- **OpenSearch Dashboards**: Provides web-based visualization and exploration

## Quick Start

### Prerequisites

- Docker Engine 20.10+ or Finch 1.0+ (macOS alternative to Docker)
- Docker Compose 2.0+ (or finch compose)
- Minimum 4GB RAM available for containers
- Minimum 10GB disk space for data volumes

### Docker Compose Deployment

**Note**: If you're using Finch instead of Docker, replace `docker compose` with `finch compose` in all commands below.

1. Clone the repository:
```bash
git clone https://github.com/opensearch-project/atlas.git
cd atlas
```

2. (Optional) Customize configuration:
```bash
cd docker-compose
# Edit .env file to change versions, ports, credentials, or resource limits
nano .env
```

3. Start the stack:
```bash
cd docker-compose
docker compose up -d
```

   **Optional**: Start with example services (weather-agent + canary):
```bash
docker compose --profile examples up -d
```
   See [docker-compose/EXAMPLES.md](docker-compose/EXAMPLES.md) for details on the example services.

4. Verify all services are running:
```bash
docker compose ps
```

5. Access the interfaces:
- OpenSearch Dashboards: http://localhost:5601
- Prometheus UI: http://localhost:9090
- Weather Agent API (if examples enabled): http://localhost:8000

6. Send sample telemetry data:
```bash
# If using example services, telemetry is generated automatically by the canary
docker compose logs -f canary

# Or run the standalone example
cd examples/plain-agents/weather-agent
python main.py
```

7. View your data in OpenSearch Dashboards at http://localhost:5601


## Instrumenting Your Agent

ATLAS accepts telemetry data via the OpenTelemetry Protocol (OTLP) and follows the [OpenTelemetry Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) for standardized attribute naming and structure for AI agents. 

Here's a quick example in Python:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure OTLP exporter
tracer_provider = TracerProvider()
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)

# Create tracer
tracer = trace.get_tracer("my-agent")

# Instrument agent invocation
with tracer.start_as_current_span("invoke_agent") as span:
    span.set_attribute("gen_ai.operation.name", "invoke_agent")
    span.set_attribute("gen_ai.agent.name", "Weather Assistant")
    span.set_attribute("gen_ai.request.model", "gpt-4")
    
    # Your agent logic here
    result = agent.run("What's the weather in Paris?")
    
    span.set_attribute("gen_ai.usage.input_tokens", 150)
    span.set_attribute("gen_ai.usage.output_tokens", 75)
```

For complete examples, see the [examples/](examples/) directory.

## Configuration

### Environment Variables

The `docker-compose/.env` file contains all configurable parameters:
- **Component versions**: OpenSearch, Prometheus, Data Prepper, etc.
- **Port mappings**: Customize exposed ports for all services
- **Credentials**: Default admin/Admin123!@# (change for production)
- **Resource limits**: Memory and CPU limits for each service

Edit this file before starting the stack to customize your deployment.

### Default Ports

- **4317**: OTLP gRPC endpoint
- **4318**: OTLP HTTP endpoint
- **5601**: OpenSearch Dashboards UI
- **9090**: Prometheus UI
- **9200**: OpenSearch REST API

### Data Retention

- **OpenSearch**: 1 day (configurable via ISM policy)
- **Prometheus**: 15 days (configurable in prometheus.yml)

### Resource Requirements

**Minimum (Development)**:
- 4GB RAM
- 10GB disk space
- 2 CPU cores

**Recommended (Development)**:
- 8GB RAM
- 50GB disk space
- 4 CPU cores

## Production Readiness

⚠️ **ATLAS is NOT production-ready out of the box.** The default configuration prioritizes ease of use for development and testing. Before deploying to production, you must address the following:

### Security Hardening Required

- **Authentication**: Enable OpenSearch security plugin and configure user authentication
- **Authorization**: Implement role-based access control (RBAC)
- **Encryption**: Enable TLS/SSL for all HTTP endpoints and encrypt data at rest
- **Network Security**: Implement network policies, firewalls, and limit exposed ports
- **Secrets Management**: Use secure secret storage instead of default passwords

### Operational Requirements

- **High Availability**: Configure multi-node OpenSearch cluster and redundant services
- **Backup and Recovery**: Implement automated backup procedures and test recovery
- **Monitoring**: Set up monitoring and alerting for the observability stack itself
- **Resource Limits**: Configure appropriate CPU, memory, and disk quotas
- **Data Lifecycle**: Implement production-appropriate retention and archival policies

### Security Considerations

The default configuration includes these development-friendly settings that are **NOT secure**:

- OpenSearch security plugin is disabled (no authentication required)
- No TLS/SSL encryption
- Default passwords where required
- Permissive CORS settings
- All services exposed without network isolation

**Never deploy the default configuration to production or expose it to untrusted networks.**

## Troubleshooting

### Services Won't Start

Check Docker resource allocation:
```bash
docker stats
```

View service logs:
```bash
docker-compose logs <service-name>
```

### Data Not Appearing

Verify OpenTelemetry Collector is receiving data:
```bash
docker-compose logs otel-collector
```

Check Data Prepper pipeline status:
```bash
docker-compose logs data-prepper
```

Verify OpenSearch indices:
```bash
curl http://localhost:9200/_cat/indices?v
```

### Performance Issues

Check resource usage:
```bash
docker-compose stats
```

Adjust resource limits in docker-compose.yml or values.yaml for Helm.

For more troubleshooting guidance, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Documentation

- [AGENTS.md](AGENTS.md) - AI-optimized repository documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development workflow and contribution guidelines
- [examples/](examples/) - Language-specific instrumentation examples
- [docs/](docs/) - Additional documentation and guides

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Development workflow
- Testing requirements
- Code style conventions
- Pull request process

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/opensearch-project/atlas/issues)
- **Discussions**: Ask questions in [GitHub Discussions](https://github.com/opensearch-project/atlas/discussions)
- **Documentation**: See the [docs/](docs/) directory

## Acknowledgments

ATLAS is built on top of excellent open-source projects:

- [OpenTelemetry](https://opentelemetry.io/)
- [OpenSearch](https://opensearch.org/)
- [Prometheus](https://prometheus.io/)
- [Data Prepper](https://opensearch.org/docs/latest/data-prepper/)

---

**Remember**: ATLAS is for development and testing. Harden security and operations before production use.
