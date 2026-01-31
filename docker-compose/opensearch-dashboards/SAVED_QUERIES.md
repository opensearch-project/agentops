# Saved Queries Feature

## Overview

The OpenSearch Dashboards initialization now supports automatically creating saved queries from a YAML configuration file. This makes it easy for developers to add, modify, or share common queries without editing Python code.

## What Changed

### New Files

1. **`saved-queries.yaml`** - Configuration file containing all saved queries
2. **`README.md`** - Documentation for the OpenSearch Dashboards configuration
3. **`SAVED_QUERIES.md`** - This file

### Modified Files

1. **`init/init-opensearch-dashboards.py`**
   - Added `import yaml`
   - Modified `create_default_saved_queries()` to read from YAML file
   - Added error handling for missing/invalid YAML

2. **`docker-compose.yml`**
   - Added `pyyaml` to pip install command
   - Mounted `saved-queries.yaml` to `/config/saved-queries.yaml`

## Default Queries

The system now includes 10 pre-configured queries:

1. **Weather agent traces** - Filter for Weather Assistant agent
2. **All agent invocations** - Find all `invoke_agent` operations
3. **Tool executions** - Find all `execute_tool` operations
4. **High token usage** - Find spans using >1000 tokens
5. **Error spans** - Find spans with error status
6. **Slow operations** - Find operations taking >5 seconds
7. **Group agents by model** - Statistics on model usage
8. **Tool usage statistics** - Count tool executions by name
9. **Recent errors** - Errors from the last hour
10. **Token usage by agent** - Sum tokens grouped by agent

## Developer Benefits

✅ **Easy to customize** - Edit YAML instead of Python code
✅ **Version control friendly** - YAML diffs are readable
✅ **Self-documenting** - Each query has title and description
✅ **Shareable** - Teams can share query collections
✅ **No rebuild required** - Just restart the init container

## Usage

### Adding a New Query

Edit `saved-queries.yaml`:

```yaml
queries:
  - id: my_new_query
    title: My New Query
    description: What this query does
    language: PPL
    query: |
      | WHERE `some.field` = 'value'
```

Then restart:

```bash
docker compose rm -f opensearch-dashboards-init
docker compose up -d
```

### Modifying Existing Queries

1. Edit the query in `saved-queries.yaml`
2. Delete the old query via API or UI
3. Restart the init container

### Sharing Queries

Teams can:
- Commit `saved-queries.yaml` to version control
- Share custom query files
- Maintain different query sets for different environments

## Technical Details

- Queries are created via OpenSearch Dashboards Saved Objects API
- Each query is associated with the AgentOps workspace
- The init script is idempotent (won't create duplicates)
- Supports both PPL and DQL query languages
- Multi-line queries are supported using YAML's `|` syntax

## Testing

To test the changes:

```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('docker-compose/opensearch-dashboards/saved-queries.yaml'))"

# Check Python syntax
python3 -m py_compile docker-compose/opensearch-dashboards/init/init-opensearch-dashboards.py

# View init logs
docker compose logs opensearch-dashboards-init
```

Expected output:
```
📝 Creating saved queries...
💾 Creating saved query: Weather agent traces...
✅ Created saved query: Weather agent traces
...
✅ Created 10 saved queries
```
