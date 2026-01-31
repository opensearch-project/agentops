# Adding Prometheus Exporter to OpenSearch

The **Prometheus Exporter Plugin for OpenSearch** exposes OpenSearch cluster metrics in Prometheus format for monitoring.

## What it exports

- **Cluster status** - overall health
- **Node stats** - JVM, memory, CPU, file system, circuit breakers
- **Index stats** - per-index metrics (optional, can be disabled)
- **Cluster settings** - disk watermarks, etc.

## Installation

Install the plugin on each OpenSearch node you want to monitor:

```bash
./bin/opensearch-plugin install https://github.com/opensearch-project/opensearch-prometheus-exporter/releases/download/3.4.0.0/prometheus-exporter-3.4.0.0.zip
```

## Prometheus Configuration

Configure Prometheus to scrape the metrics:

```yaml
- job_name: opensearch
  scrape_interval: 10s
  metrics_path: "/_prometheus/metrics"
  static_configs:
  - targets:
    - node1:9200
    - node2:9200
    - node3:9200
```

Metrics are available at `http://<opensearch-host>:9200/_prometheus/metrics`

## Key Configuration Options

In `opensearch.yml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `prometheus.indices` | `true` | Disable per-index metrics (set to `false` if you have many indices) |
| `prometheus.nodes.filter` | `"_local"` | Set to `"_all"` to get stats from all nodes |
| `prometheus.cluster.settings` | `true` | Disable cluster settings metrics |

## Notes

- Plugin version must match your OpenSearch version - check the compatibility matrix
- Per-index metrics can cause high cardinality in Prometheus if you have many indices
