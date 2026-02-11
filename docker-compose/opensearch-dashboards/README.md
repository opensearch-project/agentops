# OpenSearch Dashboards Configuration

This directory contains configuration files for OpenSearch Dashboards initialization.

## Files

### `opensearch_dashboards.yml`
Main configuration file for OpenSearch Dashboards service. Mounted into the container at startup.

### `saved-queries.yaml`
Collection of saved queries that are automatically created during initialization. These queries provide quick access to common agent observability patterns.

### `init/init-opensearch-dashboards.py`
Python script that runs once during stack startup to:
- Create the Observability Stack workspace
- Create index patterns for logs, traces, and service maps
- Set up APM correlation between traces and logs
- Create Prometheus and OpenSearch datasources
- Load and create saved queries from `saved-queries.yaml`

## Customizing Saved Queries

To add or modify saved queries, edit `saved-queries.yaml`:

```yaml
queries:
  - id: my_custom_query
    title: My Custom Query
    description: Description of what this query does
    language: PPL  # or DQL for Dashboards Query Language
    query: |
      | WHERE `attributes.some.field` = 'value'
```

### Query Fields

- **id**: Unique identifier for the query (used in the API URL)
- **title**: Display name shown in the UI
- **description**: Help text explaining what the query does
- **language**: Query language (`PPL` for Piped Processing Language or `DQL` for Dashboards Query Language)
- **query**: The actual query string (use `|` for multi-line PPL queries)

### PPL Query Examples

**Filter by attribute:**
```yaml
query: |
  | WHERE `attributes.gen_ai.agent.name` = 'My Agent'
```

**Aggregate data:**
```yaml
query: |
  | stats count() by `attributes.gen_ai.tool.name`
```

**Time-based filter:**
```yaml
query: |
  | WHERE `startTime` > now() - 1h
```

**Complex conditions:**
```yaml
query: |
  | WHERE `status.code` = 2 AND `durationInNanos` > 1000000000
```

## Applying Changes

After modifying `saved-queries.yaml`, restart the init container:

```bash
# Remove the init container (it only runs once)
docker compose rm -f opensearch-dashboards-init

# Restart the stack to run init again
docker compose up -d
```

The init script is idempotent - it will skip creating queries that already exist.

## Viewing Saved Queries

Once created, saved queries appear in OpenSearch Dashboards:

1. Navigate to **Discover** or **Observability > Traces**
2. Click the **Saved queries** dropdown in the search bar
3. Select a query to apply it

## Troubleshooting

**Queries not appearing:**
```bash
# Check init container logs
docker compose logs opensearch-dashboards-init

# Look for "Created X saved queries" message
```

**YAML syntax errors:**
```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('docker-compose/opensearch-dashboards/saved-queries.yaml'))"
```

**Recreate all queries:**
```bash
# Delete existing queries via API (replace workspace_id)
curl -X DELETE -u admin:password \
  http://localhost:5601/w/{workspace_id}/api/saved_objects/query/{query_id}

# Restart init container
docker compose rm -f opensearch-dashboards-init
docker compose up -d
```

## References

- [OpenSearch PPL Documentation](https://opensearch.org/docs/latest/search-plugins/sql/ppl/index/)
- [OpenSearch Dashboards Query Language](https://opensearch.org/docs/latest/dashboards/dql/)
- [Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
