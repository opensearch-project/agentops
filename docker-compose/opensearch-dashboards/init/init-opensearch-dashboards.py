#!/usr/bin/env python3

import os
import time
import requests
import yaml

BASE_URL = "http://opensearch-dashboards:5601"
USERNAME = os.getenv("OPENSEARCH_USER", "admin")
PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "admin")
PROMETHEUS_HOST = os.getenv("PROMETHEUS_HOST", "prometheus")
PROMETHEUS_PORT = os.getenv("PROMETHEUS_PORT", "9090")

def wait_for_dashboards():
    """Wait for OpenSearch Dashboards to be ready"""
    print("🔄 Initializing OpenSearch workspace...")

    while True:
        try:
            response = requests.get(
                f"{BASE_URL}/api/status", auth=(USERNAME, PASSWORD), timeout=5
            )
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass

        print("⏳ Waiting for OpenSearch Dashboards...")
        time.sleep(5)

def get_existing_workspace():
    """Check if AgentOps workspace already exists"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/workspaces/_list",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json={},
            verify=False,
            timeout=10,
        )
        print(f"Workspace list response: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                workspaces = result.get("result", {}).get("workspaces", [])
                for workspace in workspaces:
                    if workspace.get("name") == "AgentOps Observability":
                        return workspace.get("id")
        elif response.status_code == 404:
            print("⚠️  Workspace API not available - workspaces may not be supported in this version")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking workspaces: {e}")
    return None

def create_workspace():
    """Create new AgentOps workspace"""
    print("🏗️  Creating AgentOps workspace...")

    payload = {
        "attributes": {
            "name": "AgentOps Observability",
            "description": "AI Agent observability workspace with logs, traces, and metrics",
            "features": ["use-case-observability"]
        }
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/workspaces",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        print(f"Create workspace response: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                workspace_id = result.get("result", {}).get("id")
                if workspace_id:
                    print(f"✅ Created workspace: {workspace_id}")
                    return workspace_id
        elif response.status_code == 404:
            print("⚠️  Workspace API not available - using default dashboard")
            return "default"
        else:
            print(f"⚠️  Workspace creation failed: {response.text}")
            return "default"
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating workspace: {e}")
        return "default"


def get_existing_index_pattern(workspace_id, title):
    """Check if an index pattern with the given title already exists"""
    try:
        # Use workspace-specific URL if workspace exists
        if workspace_id and workspace_id != "default":
            url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/_find?type=index-pattern&search_fields=title&search={title}"
        else:
            url = f"{BASE_URL}/api/saved_objects/_find?type=index-pattern&search_fields=title&search={title}"

        response = requests.get(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            saved_objects = result.get("saved_objects", [])
            for obj in saved_objects:
                attributes = obj.get("attributes", {})
                # Exact match on title
                if attributes.get("title") == title:
                    return obj.get("id")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking existing index pattern {title}: {e}")
        return None


def create_index_pattern(
    workspace_id, title, time_field=None, signal_type=None, schema_mappings=None
):
    """Create index pattern in workspace and return its ID"""
    # Check if index pattern already exists
    existing_id = get_existing_index_pattern(workspace_id, title)
    if existing_id:
        print(f"✅ Index pattern already exists: {title}")
        return existing_id

    payload = {
        "attributes": {
            "title": title
        }
    }

    # Only add timeFieldName if time_field is provided
    if time_field:
        payload["attributes"]["timeFieldName"] = time_field

    # Only add signalType if signal_type is provided
    if signal_type:
        payload["attributes"]["signalType"] = signal_type

    # Only add schemaMappings if schema_mappings is provided (as a JSON string)
    if schema_mappings:
        payload["attributes"]["schemaMappings"] = schema_mappings

    # Use workspace-specific URL if workspace exists, otherwise use default
    if workspace_id and workspace_id != "default":
        url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/index-pattern"
    else:
        url = f"{BASE_URL}/api/saved_objects/index-pattern"

    try:
        response = requests.post(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )
        print(f"Index pattern {title} creation: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            pattern_id = result.get("id")
            if pattern_id:
                print(f"✅ Created index pattern: {title}")
                return pattern_id
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating index pattern {title}: {e}")
        return None


def get_existing_prometheus_datasource(datasource_name):
    """Check if a Prometheus datasource with the given name already exists"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/saved_objects/_find?per_page=10000&type=data-connection",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            saved_objects = result.get("saved_objects", [])
            for obj in saved_objects:
                attributes = obj.get("attributes", {})
                if attributes.get("connectionId") == datasource_name:
                    return obj.get("id")
        elif response.status_code == 404:
            # List endpoint not available
            return None
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking existing Prometheus datasources: {e}")
        return None


def create_prometheus_datasource(workspace_id):
    """Create Prometheus datasource using direct query API"""
    datasource_name = "AgentOps_Prometheus"

    # Check if datasource already exists
    existing_id = get_existing_prometheus_datasource(datasource_name)
    if existing_id:
        print(f"✅ Prometheus datasource already exists: {existing_id}")
        # Associate with workspace if provided
        if workspace_id and workspace_id != "default":
            associate_prometheus_with_workspace(workspace_id, existing_id)
        return existing_id

    print("🔧 Creating Prometheus datasource...")

    prometheus_endpoint = f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}"

    payload = {
        "name": datasource_name,
        "allowedRoles": [],
        "connector": "prometheus",
        "properties": {
            "prometheus.uri": prometheus_endpoint,
            "prometheus.auth.type": "basicauth",
            "prometheus.auth.username": "",
            "prometheus.auth.password": "",
        },
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/directquery/dataconnections",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        print(f"Prometheus datasource creation: {response.status_code}")

        if response.status_code == 200:
            print(f"✅ Created Prometheus datasource: {datasource_name}")

            # Fetch the datasource ID from saved objects
            datasource_id = get_existing_prometheus_datasource(datasource_name)
            if datasource_id and workspace_id and workspace_id != "default":
                associate_prometheus_with_workspace(workspace_id, datasource_id)

            return datasource_name
        elif response.status_code == 400:
            # Check if error is due to duplicate
            error_text = response.text
            if "already exists with name" in error_text:
                print(f"✅ Prometheus datasource already exists: {datasource_name}")
                # Fetch the datasource ID and associate
                datasource_id = get_existing_prometheus_datasource(datasource_name)
                if datasource_id and workspace_id and workspace_id != "default":
                    associate_prometheus_with_workspace(workspace_id, datasource_id)
                return datasource_name
            else:
                print(f"⚠️  Prometheus datasource creation failed: {error_text}")
                return None
        else:
            print(f"⚠️  Prometheus datasource creation failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating Prometheus datasource: {e}")
        return None


def associate_prometheus_with_workspace(workspace_id, datasource_id):
    """Associate Prometheus datasource with workspace"""
    print(f"🔗 Associating Prometheus datasource with workspace {workspace_id}...")

    payload = {
        "workspaceId": workspace_id,
        "savedObjects": [{"type": "data-connection", "id": datasource_id}],
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/workspaces/_associate",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        print(f"Prometheus datasource association: {response.status_code}")

        if response.status_code == 200:
            print("✅ Prometheus datasource associated with workspace")
        else:
            print(f"⚠️  Association failed: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error associating Prometheus datasource: {e}")


def associate_datasource_with_workspace(workspace_id, datasource_id):
    """Associate datasource with workspace"""
    print(f"🔗 Associating datasource {datasource_id} with workspace {workspace_id}...")

    payload = {
        "workspaceId": workspace_id,
        "savedObjects": [{"type": "data-source", "id": datasource_id}],
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/workspaces/_associate",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        print(f"Datasource association: {response.status_code}")

        if response.status_code == 200:
            print("✅ Datasource associated with workspace")
        else:
            print(f"⚠️  Association failed: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error associating datasource: {e}")


def get_existing_opensearch_datasource(datasource_title):
    """Check if OpenSearch datasource already exists"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/saved_objects/_find?per_page=10000&type=data-source",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            saved_objects = result.get("saved_objects", [])
            for obj in saved_objects:
                attributes = obj.get("attributes", {})
                if attributes.get("title") == datasource_title:
                    return obj.get("id")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking existing OpenSearch datasources: {e}")
        return None


def create_opensearch_datasource(workspace_id):
    """Create OpenSearch datasource from local cluster"""
    datasource_title = "local_cluster"

    # Check if datasource already exists
    existing_id = get_existing_opensearch_datasource(datasource_title)
    if existing_id:
        print(f"✅ OpenSearch datasource already exists: {existing_id}")
        # Associate with workspace if provided
        if workspace_id and workspace_id != "default":
            associate_datasource_with_workspace(workspace_id, existing_id)
        return existing_id

    print("🔧 Creating OpenSearch datasource...")

    opensearch_endpoint = "https://opensearch:9200"

    payload = {
        "attributes": {
            "title": datasource_title,
            "description": "Local OpenSearch cluster",
            "endpoint": opensearch_endpoint,
            "auth": {
                "type": "username_password",
                "credentials": {"username": USERNAME, "password": PASSWORD},
            },
            "dataSourceVersion": "3.5.0",
            "dataSourceEngineType": "OpenSearch",
        }
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/saved_objects/data-source",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        print(f"OpenSearch datasource creation: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            datasource_id = result.get("id")
            if datasource_id:
                print(f"✅ Created OpenSearch datasource: {datasource_id}")

                # Associate with workspace if provided
                if workspace_id and workspace_id != "default":
                    associate_datasource_with_workspace(workspace_id, datasource_id)
                return datasource_id
        else:
            print(f"⚠️  OpenSearch datasource creation failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating OpenSearch datasource: {e}")
        return None


def set_default_index_pattern(workspace_id, pattern_id):
    """Set the default index pattern"""
    print(f"⭐ Setting default index pattern: {pattern_id}")

    # Use workspace-specific URL if workspace exists, otherwise use default
    if workspace_id and workspace_id != "default":
        url = f"{BASE_URL}/w/{workspace_id}/api/opensearch-dashboards/settings/defaultIndex"
    else:
        url = f"{BASE_URL}/api/opensearch-dashboards/settings/defaultIndex"

    payload = {"value": pattern_id}

    try:
        response = requests.post(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        print(f"Set default index pattern: {response.status_code}")

        if response.status_code == 200:
            print("✅ Default index pattern set to logs-otel-v1-*")
        else:
            print(f"⚠️  Setting default failed: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error setting default index pattern: {e}")


def get_existing_correlation(workspace_id):
    """Check if APM correlation already exists"""
    try:
        if workspace_id and workspace_id != "default":
            url = (
                f"{BASE_URL}/w/{workspace_id}/api/saved_objects/_find?type=correlations"
            )
        else:
            url = f"{BASE_URL}/api/saved_objects/_find?type=correlations"

        response = requests.get(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            saved_objects = result.get("saved_objects", [])
            for obj in saved_objects:
                attributes = obj.get("attributes", {})
                if attributes.get("correlationType") == "APM-Correlation":
                    return obj.get("id")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking existing correlation: {e}")
        return None


def create_apm_correlation(workspace_id, traces_pattern_id, logs_pattern_id):
    """Create APM correlation between traces and logs"""
    # Check if correlation already exists
    existing_id = get_existing_correlation(workspace_id)
    if existing_id:
        print(f"✅ APM correlation already exists: {existing_id}")
        return existing_id

    print("🔗 Creating APM correlation between traces and logs...")

    payload = {
        "attributes": {
            "correlationType": "APM-Correlation",
            "version": "1.0.0",
            "entities": [
                {"tracesDataset": {"id": "references[0].id"}},
                {"logsDataset": {"id": "references[1].id"}},
            ],
        },
        "references": [
            {
                "name": "entities[0].index",
                "type": "index-pattern",
                "id": traces_pattern_id,
            },
            {
                "name": "entities[1].index",
                "type": "index-pattern",
                "id": logs_pattern_id,
            },
        ],
    }

    # Add workspaces field if workspace exists
    if workspace_id and workspace_id != "default":
        payload["workspaces"] = [workspace_id]
        url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/correlations"
    else:
        url = f"{BASE_URL}/api/saved_objects/correlations"

    try:
        response = requests.post(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        print(f"APM correlation creation: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            correlation_id = result.get("id")
            if correlation_id:
                print(f"✅ Created APM correlation: {correlation_id}")
                return correlation_id
        else:
            print(f"⚠️  APM correlation creation failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating APM correlation: {e}")
        return None


def create_or_update_saved_query(
    workspace_id, query_id, title, description, query_string, language="PPL"
):
    """Create or update a saved query in the workspace"""
    print(f"💾 Creating/updating saved query: {title}...")

    # Base attributes for both create and update
    base_attributes = {
        "title": title,
        "description": description,
        "query": {"query": query_string, "language": language},
    }

    # Set URL based on workspace
    if workspace_id and workspace_id != "default":
        url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/query/{query_id}"
    else:
        url = f"{BASE_URL}/api/saved_objects/query/{query_id}"

    try:
        # Try POST first (create) - includes workspaces field
        create_payload = {"attributes": base_attributes}
        if workspace_id and workspace_id != "default":
            create_payload["workspaces"] = [workspace_id]

        response = requests.post(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=create_payload,
            verify=False,
            timeout=10,
        )

        if response.status_code == 200:
            print(f"✅ Created saved query: {title}")
            return query_id
        elif response.status_code == 409:
            # Query exists, update it with PUT - only attributes, no workspaces field
            print(f"🔄 Query exists, updating: {title}")
            update_payload = {"attributes": base_attributes}

            response = requests.put(
                url,
                auth=(USERNAME, PASSWORD),
                headers={"Content-Type": "application/json", "osd-xsrf": "true"},
                json=update_payload,
                verify=False,
                timeout=10,
            )

            if response.status_code == 200:
                print(f"✅ Updated saved query: {title}")
                return query_id
            else:
                print(f"⚠️  Saved query update failed: {response.text}")
                return None
        else:
            print(f"⚠️  Saved query creation failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating/updating saved query: {e}")
        return None


def create_default_saved_queries(workspace_id):
    """Create a collection of useful saved queries for agent observability"""
    print("📝 Creating saved queries...")

    import glob

    # Load all saved-queries-*.yaml files
    queries_files = glob.glob("/config/saved-queries-*.yaml")

    if not queries_files:
        print("⚠️  No saved-queries-*.yaml files found")
        return 0

    total_created = 0
    for queries_file in sorted(queries_files):
        print(f"📄 Loading {os.path.basename(queries_file)}...")
        try:
            with open(queries_file, "r") as f:
                config = yaml.safe_load(f)
                queries = config.get("queries", [])
        except yaml.YAMLError as e:
            print(f"⚠️  Error parsing {queries_file}: {e}")
            continue

        if not queries:
            print(f"⚠️  No queries found in {queries_file}")
            continue

        for query_def in queries:
            result = create_or_update_saved_query(
                workspace_id,
                query_def.get("id"),
                query_def.get("title"),
                query_def.get("description"),
                query_def.get("query"),
                query_def.get("language", "PPL"),
            )
            if result:
                total_created += 1

    print(f"✅ Processed {total_created} saved queries from {len(queries_files)} file(s)")
    return total_created


def get_existing_dashboard(workspace_id, dashboard_id):
    """Check if dashboard already exists"""
    try:
        if workspace_id and workspace_id != "default":
            url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/dashboard/{dashboard_id}"
        else:
            url = f"{BASE_URL}/api/saved_objects/dashboard/{dashboard_id}"

        response = requests.get(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def set_default_dashboard(workspace_id, dashboard_id):
    """Set the default dashboard for the observability overview page"""
    print(f"⭐ Setting default dashboard: {dashboard_id}")

    if workspace_id and workspace_id != "default":
        url = f"{BASE_URL}/w/{workspace_id}/api/opensearch-dashboards/settings"
    else:
        url = f"{BASE_URL}/api/opensearch-dashboards/settings"

    payload = {"changes": {"observability:defaultDashboard": dashboard_id}}

    try:
        response = requests.post(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        if response.status_code == 200:
            print("✅ Default dashboard set")
        else:
            print(f"⚠️  Setting default dashboard failed: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error setting default dashboard: {e}")


def create_agent_observability_dashboard(workspace_id, traces_pattern_id):
    """Create or update Agent Observability dashboard with visualizations"""
    import json

    dashboard_id = "agent-observability-dashboard"
    dashboard_exists = get_existing_dashboard(workspace_id, dashboard_id)

    if dashboard_exists:
        print("📊 Updating Agent Observability dashboard...")
    else:
        print("📊 Creating Agent Observability dashboard...")

    # Visualizations based on last 5 queries from saved-queries-traces.yaml
    visualizations = [
        {
            "id": "llm-requests-by-model",
            "title": "LLM Requests by Model",
            "type": "pie",
            "field": "attributes.gen_ai.request.model"
        },
        {
            "id": "tool-usage-stats",
            "title": "Tool Usage Statistics",
            "type": "pie",
            "field": "attributes.gen_ai.tool.name"
        },
        {
            "id": "token-usage-by-agent",
            "title": "Token Usage by Agent",
            "type": "horizontal_bar",
            "field": "attributes.gen_ai.agent.name",
            "metric_field": "attributes.gen_ai.usage.input_tokens"
        },
        {
            "id": "token-usage-by-model",
            "title": "Token Usage by Model",
            "type": "horizontal_bar",
            "field": "attributes.gen_ai.request.model",
            "metric_field": "attributes.gen_ai.usage.input_tokens"
        },
        {
            "id": "agent-operations-by-service",
            "title": "Agent Operations by Service",
            "type": "horizontal_bar",
            "field": "serviceName",
            "split_field": "attributes.gen_ai.operation.name"
        }
    ]

    created_vis_ids = []
    for vis in visualizations:
        vis_id = create_chart_visualization(
            workspace_id, vis["id"], vis["title"], vis["type"],
            vis["field"], traces_pattern_id,
            metric_field=vis.get("metric_field"),
            split_field=vis.get("split_field")
        )
        if vis_id:
            created_vis_ids.append(vis_id)
            print(f"  ✅ Created visualization: {vis['title']}")

    if not created_vis_ids:
        print("⚠️  No visualizations created, skipping dashboard")
        return None

    # Create dashboard with panels
    panels = []
    references = []
    for i, vis_id in enumerate(created_vis_ids):
        panels.append({
            "version": "3.5.0",
            "gridData": {"x": (i % 2) * 24, "y": (i // 2) * 15, "w": 24, "h": 15, "i": str(i)},
            "panelIndex": str(i),
            "embeddableConfig": {},
            "panelRefName": f"panel_{i}"
        })
        references.append({"name": f"panel_{i}", "type": "visualization", "id": vis_id})

    if workspace_id and workspace_id != "default":
        url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/dashboard/{dashboard_id}"
    else:
        url = f"{BASE_URL}/api/saved_objects/dashboard/{dashboard_id}"

    payload = {
        "attributes": {
            "title": "Agent Observability",
            "description": "Overview of AI agent performance, token usage, and tool execution",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
            }
        },
        "references": references
    }

    if workspace_id and workspace_id != "default":
        payload["workspaces"] = [workspace_id]

    try:
        response = requests.post(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        if response.status_code == 200:
            print(f"✅ Created Agent Observability dashboard")
            set_default_dashboard(workspace_id, dashboard_id)
            return dashboard_id
        elif response.status_code == 409:
            # Dashboard exists, update it with PUT
            print("🔄 Dashboard exists, updating...")
            update_payload = {"attributes": payload["attributes"], "references": references}
            response = requests.put(
                url,
                auth=(USERNAME, PASSWORD),
                headers={"Content-Type": "application/json", "osd-xsrf": "true"},
                json=update_payload,
                verify=False,
                timeout=10,
            )
            if response.status_code == 200:
                print(f"✅ Updated Agent Observability dashboard")
                set_default_dashboard(workspace_id, dashboard_id)
                return dashboard_id
            else:
                print(f"⚠️  Dashboard update failed: {response.text}")
                return None
        else:
            print(f"⚠️  Dashboard creation failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating dashboard: {e}")
        return None


def create_chart_visualization(workspace_id, vis_id, title, vis_type, field, index_pattern_id,
                                metric_field=None, split_field=None):
    """Create a chart visualization (pie, bar, etc.)"""
    import json

    if workspace_id and workspace_id != "default":
        url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/visualization/{vis_id}"
    else:
        url = f"{BASE_URL}/api/saved_objects/visualization/{vis_id}"

    # Build aggregations
    aggs = []
    if metric_field:
        aggs.append({"id": "1", "type": "sum", "schema": "metric", "params": {"field": metric_field}})
    else:
        aggs.append({"id": "1", "type": "count", "schema": "metric"})

    aggs.append({"id": "2", "type": "terms", "schema": "segment", "params": {"field": field, "size": 10}})

    if split_field:
        aggs.append({"id": "3", "type": "terms", "schema": "group", "params": {"field": split_field, "size": 5}})

    vis_state = {
        "title": title,
        "type": vis_type,
        "params": {"type": vis_type, "addTooltip": True, "addLegend": True},
        "aggs": aggs
    }

    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern",
                "id": index_pattern_id
            }
        ]
    }

    if workspace_id and workspace_id != "default":
        payload["workspaces"] = [workspace_id]

    try:
        response = requests.post(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload,
            verify=False,
            timeout=10,
        )

        if response.status_code in (200, 409):
            return vis_id
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating visualization {title}: {e}")
        return None


def main():
    """Initialize OpenSearch Dashboards with workspace and datasources"""
    wait_for_dashboards()

    # Check for existing workspace
    workspace_id = get_existing_workspace()

    if workspace_id:
        print("✅ AgentOps workspace already exists")
    else:
        workspace_id = create_workspace()

    # Create index patterns (idempotent - will skip if already exist)
    logs_schema_mappings = '{"otelLogs":{"timestamp":"time","traceId":"traceId","spanId":"spanId","serviceName":"resource.attributes.service.name"}}'
    logs_pattern_id = create_index_pattern(
        workspace_id, "logs-otel-v1-*", "time", "logs", logs_schema_mappings
    )
    traces_pattern_id = create_index_pattern(
        workspace_id, "otel-v1-apm-span-*", "startTime", "traces"
    )
    create_index_pattern(workspace_id, "otel-v1-apm-service-map")

    print("📊 Created index patterns for spans, logs, and service map")

    # Set logs as the default index pattern
    if logs_pattern_id:
        set_default_index_pattern(workspace_id, logs_pattern_id)

    # Create APM correlation between traces and logs
    if traces_pattern_id and logs_pattern_id:
        create_apm_correlation(workspace_id, traces_pattern_id, logs_pattern_id)

    # Create Agent Observability dashboard
    if traces_pattern_id:
        create_agent_observability_dashboard(workspace_id, traces_pattern_id)

    # Create saved queries for common agent observability patterns
    create_default_saved_queries(workspace_id)

    # Create datasources
    create_prometheus_datasource(workspace_id)
    create_opensearch_datasource(workspace_id)

    # Output summary
    print()
    print("🎉 AgentOps Stack Ready!")
    print(f"👤 Username: {USERNAME}")
    print(f"🔑 Password: {PASSWORD}")

    # Generate appropriate dashboard URL
    if workspace_id and workspace_id != "default":
        dashboard_url = f"http://localhost:5601/w/{workspace_id}/app/explore/logs"
    else:
        dashboard_url = "http://localhost:5601/app/home"

    print(f"\033[1m📊 OpenSearch Dashboards: {dashboard_url}\033[0m")
    print(f"📈 Prometheus: http://localhost:{PROMETHEUS_PORT}")
    print()

if __name__ == "__main__":
    main()
