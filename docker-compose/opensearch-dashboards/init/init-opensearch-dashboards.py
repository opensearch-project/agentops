#!/usr/bin/env python3

import os
import time
import requests
import yaml

_dashboards_host = os.getenv("OPENSEARCH_DASHBOARDS_HOST", "opensearch-dashboards")
_dashboards_port = os.getenv("OPENSEARCH_DASHBOARDS_PORT", "5601")
_dashboards_protocol = os.getenv("OPENSEARCH_DASHBOARDS_PROTOCOL", "http")
BASE_URL = f"{_dashboards_protocol}://{_dashboards_host}:{_dashboards_port}"
USERNAME = os.getenv("OPENSEARCH_USER", "admin")
PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "My_password_123!@#")
PROMETHEUS_HOST = os.getenv("PROMETHEUS_HOST", "prometheus.observability-stack-network")
PROMETHEUS_PORT = os.getenv("PROMETHEUS_PORT", "9090")
ALERTMANAGER_HOST = os.getenv("ALERTMANAGER_HOST", "alertmanager")
ALERTMANAGER_PORT = os.getenv("ALERTMANAGER_PORT", "9093")
_opensearch_protocol = os.getenv("OPENSEARCH_PROTOCOL", "https")
OPENSEARCH_ENDPOINT = f"{_opensearch_protocol}://{os.getenv('OPENSEARCH_HOST', 'opensearch')}:{os.getenv('OPENSEARCH_PORT', '9200')}"
ISM_RETENTION_DAYS = int(os.getenv("ISM_RETENTION_DAYS", "7"))


def _ism_policy(policy_id, description, index_patterns, rollover_size, retention_days):
    """Build an ISM policy with rollover and optional delete."""
    states = [
        {
            "name": "current_write_index",
            "actions": [{"retry": {"count": 3, "backoff": "exponential", "delay": "1m"},
                         "rollover": {"min_size": rollover_size, "min_index_age": "24h", "copy_alias": False}}],
            "transitions": [{"state_name": "delete", "conditions": {"min_index_age": f"{retention_days}d"}}] if retention_days > 0 else [],
        }
    ]
    if retention_days > 0:
        states.append({"name": "delete", "actions": [{"delete": {}}], "transitions": []})
    return {
        "policy": {
            "policy_id": policy_id,
            "description": description,
            "default_state": "current_write_index",
            "states": states,
            "ism_template": [{"index_patterns": index_patterns, "priority": 100}],
        }
    }


def configure_ism_policies():
    """Create or update ISM policies with retention-based deletion.

    Data Prepper creates rollover-only policies on startup. This function
    overrides them to add a delete state so old indices are cleaned up
    automatically. Set ISM_RETENTION_DAYS=0 to keep rollover-only behavior.
    """
    if ISM_RETENTION_DAYS == 0:
        print("⏭️  ISM_RETENTION_DAYS=0, skipping retention policy setup (rollover-only)")
        return

    print(f"🗂️  Configuring ISM retention policies ({ISM_RETENTION_DAYS}d)...")

    policies = [
        _ism_policy("raw-span-policy", "Trace span index lifecycle",
                     ["otel-v1-apm-span-*"], "50gb", ISM_RETENTION_DAYS),
        _ism_policy("logs-policy", "Log index lifecycle",
                     ["logs-otel-v1-*"], "50gb", ISM_RETENTION_DAYS),
        _ism_policy("otel-v2-apm-service-map-policy", "Service map index lifecycle",
                     ["otel-v2-apm-service-map-*"], "10gb", ISM_RETENTION_DAYS),
    ]

    for policy_body in policies:
        pid = policy_body["policy"]["policy_id"]
        url = f"{OPENSEARCH_ENDPOINT}/_plugins/_ism/policies/{pid}"
        try:
            # Get current policy to obtain seq_no/primary_term for update
            resp = requests.get(url, auth=(USERNAME, PASSWORD), verify=False, timeout=10)
            if resp.status_code == 200:
                existing = resp.json()
                seq_no = existing.get("_seq_no")
                primary_term = existing.get("_primary_term")
                resp = requests.put(
                    f"{url}?if_seq_no={seq_no}&if_primary_term={primary_term}",
                    auth=(USERNAME, PASSWORD), json=policy_body, verify=False, timeout=10,
                )
                if resp.status_code == 200:
                    print(f"  ✅ Updated {pid}")
                else:
                    print(f"  ⚠️  Update {pid}: {resp.status_code} {resp.text[:120]}")
            elif resp.status_code == 404:
                resp = requests.put(url, auth=(USERNAME, PASSWORD), json=policy_body,
                                    verify=False, timeout=10)
                if resp.status_code in (200, 201):
                    print(f"  ✅ Created {pid}")
                else:
                    print(f"  ⚠️  Create {pid}: {resp.status_code} {resp.text[:120]}")
            else:
                print(f"  ⚠️  Get {pid}: {resp.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Error configuring {pid}: {e}")

def wait_for_dashboards():
    """Wait for OpenSearch Dashboards to be ready"""
    print("🔄 Initializing OpenSearch workspace...")

    while True:
        try:
            response = requests.get(
                f"{BASE_URL}/api/status", auth=(USERNAME, PASSWORD), timeout=5, verify=False
            )
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass

        print("⏳ Waiting for OpenSearch Dashboards...")
        time.sleep(5)

def get_existing_workspace():
    """Check if Observability Stack workspace already exists"""
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
                    if workspace.get("name") == "Observability Stack":
                        return workspace.get("id")
        elif response.status_code == 404:
            print("⚠️  Workspace API not available - workspaces may not be supported in this version")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking workspaces: {e}")
    return None

def create_workspace():
    """Create new Observability Stack workspace"""
    print("🏗️  Creating Observability Stack workspace...")

    payload = {
        "attributes": {
            "name": "Observability Stack",
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
    workspace_id, title, time_field=None, signal_type=None, schema_mappings=None,
    display_name=None
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

    if time_field:
        payload["attributes"]["timeFieldName"] = time_field
    if signal_type:
        payload["attributes"]["signalType"] = signal_type
    if schema_mappings:
        payload["attributes"]["schemaMappings"] = schema_mappings
    if display_name:
        payload["attributes"]["displayName"] = display_name

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


def get_prometheus_datasource_properties(datasource_name):
    """Fetch the full properties map for a Prometheus dataconnection.

    The /api/saved_objects/_find?type=data-connection endpoint only exposes
    connectionId + type; the authoritative read for `properties` is the SQL
    plugin's /api/dataconnections endpoint.
    """
    try:
        response = requests.get(
            f"{BASE_URL}/api/dataconnections",
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )
        if response.status_code != 200:
            print(f"⚠️  GET /api/dataconnections returned {response.status_code}: {response.text[:200]}")
            return None
        for entry in response.json() or []:
            if entry.get("name") == datasource_name:
                return entry.get("properties") or {}
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error reading dataconnections: {e}")
        return None


def create_prometheus_datasource(workspace_id):
    """Create Prometheus datasource using direct query API"""
    datasource_name = "ObservabilityStack_Prometheus"

    # Cortex exposes the Prometheus-compatible query API under /prometheus
    # (e.g. /prometheus/api/v1/query_range) while the Ruler admin API lives
    # at the unprefixed root (/api/v1/rules/{namespace}). The SQL plugin's
    # PrometheusClient exposes `prometheus.uri` and `prometheus.ruler.uri`
    # exactly for this split — both must be set for query + rule management
    # to work against Cortex.
    prometheus_endpoint = f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}/prometheus"
    ruler_endpoint = f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}"
    alertmanager_endpoint = f"http://{ALERTMANAGER_HOST}:{ALERTMANAGER_PORT}"

    desired_properties = {
        "prometheus.uri": prometheus_endpoint,
        "prometheus.ruler.uri": ruler_endpoint,
        "alertmanager.uri": alertmanager_endpoint,
    }

    # Check if datasource already exists
    existing_id = get_existing_prometheus_datasource(datasource_name)
    if existing_id:
        print(f"✅ Prometheus datasource already exists: {existing_id}")
        reconciled = reconcile_prometheus_datasource_properties(
            datasource_name, desired_properties
        )
        # Reconciliation goes through DELETE + POST, so the saved-object
        # id may have changed — re-read before associating.
        datasource_id = existing_id
        if reconciled:
            datasource_id = get_existing_prometheus_datasource(datasource_name) or existing_id
        # Associate with workspace if provided
        if workspace_id and workspace_id != "default":
            associate_prometheus_with_workspace(workspace_id, datasource_id)
        return datasource_id

    print("🔧 Creating Prometheus datasource...")

    payload = {
        "name": datasource_name,
        "allowedRoles": [],
        "connector": "prometheus",
        "properties": desired_properties,
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
                reconcile_prometheus_datasource_properties(
                    datasource_name, desired_properties
                )
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


def _delete_stale_data_connection_saved_object(saved_object_id):
    """Delete the orphaned data-connection saved-object left behind by the
    SQL plugin's DELETE /api/dataconnections/{name} path.

    The SQL plugin removes its own dataconnection record but not the wrapper
    OSD saved-object, so without this call an in-place upgrade ends up with
    two data-connection saved-objects sharing the same connectionId — one
    orphaned (no SQL backing), one live. The orphan pollutes workspace
    listings and re-breaks every time the migration runs.
    """
    url = f"{BASE_URL}/api/saved_objects/data-connection/{saved_object_id}?force=true"
    try:
        resp = requests.delete(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )
        if resp.status_code in (200, 204, 404):
            print(
                f"🧹 Deleted stale data-connection saved-object {saved_object_id}"
            )
            return True
        print(
            f"⚠️  Failed to delete stale data-connection saved-object "
            f"({resp.status_code}): {resp.text[:200]}"
        )
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error deleting stale data-connection saved-object: {e}")
    return False


def _delete_correlations_referencing_data_connection(data_connection_id):
    """Remove any correlation saved-objects whose references point at
    `data_connection_id`. They'll be re-created idempotently later in the
    init flow with the new id, so the net effect is "migrate reference,
    not break it". Without this, the APM-config correlation from the pre-PR
    install dangles: it still exists, but its references[2].dataConnection.id
    points at a saved-object whose SQL-plugin backing is gone.
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/api/saved_objects/_find?type=correlations&per_page=1000",
            auth=(USERNAME, PASSWORD),
            headers={"osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )
        if resp.status_code != 200:
            print(
                f"⚠️  Could not list correlations for dangling-reference scan "
                f"({resp.status_code})"
            )
            return

        for obj in resp.json().get("saved_objects", []):
            refs = obj.get("references") or []
            if not any(
                r.get("type") == "data-connection" and r.get("id") == data_connection_id
                for r in refs
            ):
                continue
            obj_id = obj.get("id")
            workspaces = obj.get("workspaces") or []
            if workspaces and workspaces[0] != "default":
                url = f"{BASE_URL}/w/{workspaces[0]}/api/saved_objects/correlations/{obj_id}"
            else:
                url = f"{BASE_URL}/api/saved_objects/correlations/{obj_id}"
            del_resp = requests.delete(
                url + "?force=true",
                auth=(USERNAME, PASSWORD),
                headers={"osd-xsrf": "true"},
                verify=False,
                timeout=10,
            )
            if del_resp.status_code in (200, 204, 404):
                print(
                    f"🧹 Deleted stale correlation {obj_id} "
                    f"(referenced pre-migration dataconnection)"
                )
            else:
                print(
                    f"⚠️  Failed to delete stale correlation {obj_id} "
                    f"({del_resp.status_code}): {del_resp.text[:200]}"
                )
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error scanning correlations for stale references: {e}")


def reconcile_prometheus_datasource_properties(datasource_name, desired_properties):
    """Ensure an existing Prometheus datasource carries all desired properties.

    Returns True when the datasource was rewritten (so callers can re-fetch
    the saved-object id, which changes across DELETE+POST), False when it
    was already in the desired state or when reconciliation could not run.

    Why: in-place upgrades keep the pre-PR datasource (prometheus.uri only)
    so the OSD Alert Manager UI silently shows zero alerts because the
    alertmanager.uri / prometheus.ruler.uri it needs were never added. This
    reads the authoritative properties via /api/dataconnections, diffs them
    against the desired set, and rewrites only on a mismatch to keep re-runs
    idempotent.

    Update strategy: DELETE + POST. The SQL plugin does not expose a PUT/PATCH
    update endpoint for Prometheus dataconnections — POST rejects with 400
    "already exists" and PUT/PATCH return 404. DELETE on
    /api/dataconnections/{name} succeeds, after which a fresh POST recreates
    the dataconnection with the full property set.

    The SQL plugin's DELETE does not remove the wrapping OSD saved-object or
    update any correlation that references it, so this function also cleans
    up the stale saved-object and any dangling correlation references before
    re-POSTing. The correlations are re-created idempotently later in the
    init flow against the new id.
    """
    current = get_prometheus_datasource_properties(datasource_name)
    if current is None:
        print(
            "⚠️  Could not read Prometheus datasource properties "
            f"for '{datasource_name}' — skipping reconciliation"
        )
        return False

    missing = [k for k in desired_properties if k not in current]
    mismatched = [
        k for k in desired_properties
        if k in current and current.get(k) != desired_properties[k]
    ]
    if not missing and not mismatched:
        print("✅ Prometheus datasource properties already up to date")
        return False

    if missing:
        print(f"🔧 Prometheus datasource missing properties: {missing}")
    if mismatched:
        print(f"🔧 Prometheus datasource properties changed: {mismatched}")

    # Capture the pre-existing saved-object id BEFORE the SQL-plugin DELETE
    # so we can clean up the orphaned saved-object and any correlations that
    # still point at it.
    stale_saved_object_id = get_existing_prometheus_datasource(datasource_name)

    delete_url = f"{BASE_URL}/api/dataconnections/{datasource_name}"
    try:
        delete_resp = requests.delete(
            delete_url,
            auth=(USERNAME, PASSWORD),
            headers={"osd-xsrf": "true"},
            verify=False,
            timeout=10,
        )
        if delete_resp.status_code not in (200, 204, 404):
            print(
                f"⚠️  Prometheus datasource DELETE failed "
                f"({delete_resp.status_code}): {delete_resp.text[:200]}"
            )
            return False
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error deleting Prometheus datasource: {e}")
        return False

    # Remove the now-orphaned saved-object wrapper + any correlations that
    # reference it. Best-effort — failures here are logged but don't abort
    # the migration, since the subsequent POST still restores a working
    # datasource even if cleanup is incomplete.
    if stale_saved_object_id:
        _delete_correlations_referencing_data_connection(stale_saved_object_id)
        _delete_stale_data_connection_saved_object(stale_saved_object_id)

    payload = {
        "name": datasource_name,
        "allowedRoles": [],
        "connector": "prometheus",
        "properties": desired_properties,
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
        if response.status_code == 200:
            print("✅ Recreated Prometheus datasource with updated properties")
            return True
        print(
            f"⚠️  Prometheus datasource recreate after delete failed "
            f"({response.status_code}): {response.text[:200]}"
        )
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error recreating Prometheus datasource: {e}")
    return False


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

    # OSD_DATASOURCE_ENDPOINT lets operators override the endpoint written
    # onto the saved object — useful when OSD runs outside the compose
    # network and cannot resolve the `opensearch` service name. Falls back
    # to the intra-network hostname when unset.
    opensearch_endpoint = os.getenv("OSD_DATASOURCE_ENDPOINT", OPENSEARCH_ENDPOINT)

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


def get_existing_correlation(workspace_id, correlation_type_prefix):
    """Check if a correlation with the given type prefix already exists"""
    try:
        if workspace_id and workspace_id != "default":
            url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/_find?type=correlations"
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
                ct = attributes.get("correlationType", "")
                if ct.startswith(correlation_type_prefix):
                    return obj.get("id")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking existing correlation: {e}")
        return None


def create_correlation(workspace_id, correlation_type, title, entities, references):
    """Create a correlation saved object (idempotent)"""
    # Determine prefix for existence check (APM-Config- or trace-to-logs-)
    prefix = correlation_type.split("-")[0] + "-" + correlation_type.split("-")[1] if "-" in correlation_type else correlation_type
    existing_id = get_existing_correlation(workspace_id, prefix)
    if existing_id:
        print(f"✅ Correlation already exists ({prefix}*): {existing_id}")
        return existing_id

    print(f"🔗 Creating correlation: {title}...")

    payload = {
        "attributes": {
            "correlationType": correlation_type,
            "title": title,
            "version": "1.0.0",
            "entities": entities,
        },
        "references": references,
    }

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

        if response.status_code == 200:
            result = response.json()
            correlation_id = result.get("id")
            print(f"✅ Created correlation: {title} ({correlation_id})")
            return correlation_id
        else:
            print(f"⚠️  Correlation creation failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating correlation: {e}")
        return None


def create_trace_to_logs_correlation(workspace_id, traces_pattern_id, logs_pattern_id):
    """Create trace-to-logs correlation for cross-signal navigation"""
    return create_correlation(
        workspace_id,
        correlation_type=f"trace-to-logs-otel-v1-apm-span*",
        title="trace-to-logs_otel-v1-apm-span*",
        entities=[
            {"tracesDataset": {"id": "references[0].id"}},
            {"logsDataset": {"id": "references[1].id"}},
        ],
        references=[
            {"name": "entities[0].index", "type": "index-pattern", "id": traces_pattern_id},
            {"name": "entities[1].index", "type": "index-pattern", "id": logs_pattern_id},
        ],
    )


def create_apm_config_correlation(workspace_id, traces_pattern_id, service_map_pattern_id, prometheus_datasource_id):
    """Create APM config correlation that ties traces, service map, and Prometheus together"""
    if not prometheus_datasource_id:
        print("⚠️  Skipping APM config - no Prometheus datasource ID")
        return None

    return create_correlation(
        workspace_id,
        correlation_type=f"APM-Config-{workspace_id}",
        title="apm-config",
        entities=[
            {"tracesDataset": {"id": "references[0].id"}},
            {"serviceMapDataset": {"id": "references[1].id"}},
            {"prometheusDataSource": {"id": "references[2].id"}},
        ],
        references=[
            {"name": "entities[0].index", "type": "index-pattern", "id": traces_pattern_id},
            {"name": "entities[1].index", "type": "index-pattern", "id": service_map_pattern_id},
            {"name": "entities[2].dataConnection", "type": "data-connection", "id": prometheus_datasource_id},
        ],
    )


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


def create_promql_dashboard_from_yaml(workspace_id, config_path, prometheus_datasource_title="ObservabilityStack_Prometheus"):
    """Create a dashboard with PromQL explore panels from a YAML config file"""
    import json

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"⚠️  Skipping dashboard from {config_path}: {e}")
        return None

    dashboard_config = config.get("dashboard", {})
    panel_defs = config.get("panels", [])
    dashboard_id = dashboard_config.get("id", "promql-dashboard")

    print(f"📊 Creating {dashboard_config.get('title', 'PromQL Dashboard')} dashboard ({len(panel_defs)} panels)...")

    viz_template = json.dumps({
        "title": "", "chartType": "line",
        "params": {
            "addLegend": True, "addTimeMarker": False, "legendPosition": "bottom",
            "legendTitle": "", "lineMode": "straight", "lineStyle": "line", "lineWidth": 2,
            "showFullTimeRange": False, "standardAxes": [],
            "thresholdOptions": {"baseColor": "#00BD6B", "thresholds": [], "thresholdStyle": "off"},
            "titleOptions": {"show": False, "titleName": ""},
            "tooltipOptions": {"mode": "all"}
        },
        "axesMapping": {"color": "Series", "x": "Time", "y": "Value"}
    })

    dataset = {
        "id": prometheus_datasource_title, "title": prometheus_datasource_title,
        "type": "PROMETHEUS", "language": "PROMQL", "timeFieldName": "Time",
        "dataSource": {}, "signalType": "metrics"
    }

    created_ids = []
    for panel_def in panel_defs:
        panel_id = panel_def["id"]
        search_source = json.dumps({
            "query": {"query": panel_def["query"], "language": "PROMQL", "dataset": dataset},
            "filter": [], "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
        })
        payload = {
            "attributes": {
                "title": panel_def["title"], "description": "", "hits": 0,
                "columns": ["_source"], "sort": [], "version": 1, "type": "metrics",
                "visualization": viz_template,
                "uiState": json.dumps({"activeTab": "explore_visualization_tab"}),
                "kibanaSavedObjectMeta": {"searchSourceJSON": search_source}
            },
            "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": prometheus_datasource_title}]
        }
        if workspace_id and workspace_id != "default":
            payload["workspaces"] = [workspace_id]
            url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/explore/{panel_id}"
        else:
            url = f"{BASE_URL}/api/saved_objects/explore/{panel_id}"
        try:
            response = requests.post(url, auth=(USERNAME, PASSWORD), headers={"Content-Type": "application/json", "osd-xsrf": "true"}, json=payload, verify=False, timeout=10)
            if response.status_code == 200:
                created_ids.append(panel_id)
                print(f"  ✅ {panel_def['title']}")
            elif response.status_code == 409:
                requests.put(url, auth=(USERNAME, PASSWORD), headers={"Content-Type": "application/json", "osd-xsrf": "true"}, json={"attributes": payload["attributes"], "references": payload["references"]}, verify=False, timeout=10)
                created_ids.append(panel_id)
                print(f"  🔄 {panel_def['title']} (updated)")
            else:
                print(f"  ⚠️  {panel_def['title']}: {response.status_code} {response.text[:100]}")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  {panel_def['title']}: {e}")

    if not created_ids:
        print("⚠️  No panels created, skipping dashboard")
        return None

    panels = []
    references = []
    for i, pid in enumerate(created_ids):
        panels.append({"version": "3.6.0", "panelIndex": pid, "gridData": {"i": pid, "x": (i % 2) * 24, "y": (i // 2) * 15, "w": 24, "h": 15}, "panelRefName": f"panel_{i}"})
        references.append({"name": f"panel_{i}", "type": "explore", "id": pid})

    dashboard_payload = {
        "attributes": {
            "title": dashboard_config.get("title", "PromQL Dashboard"),
            "description": dashboard_config.get("description", ""),
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "timeRestore": False,
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({})}
        },
        "references": references
    }
    if workspace_id and workspace_id != "default":
        dashboard_payload["workspaces"] = [workspace_id]
        url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/dashboard/{dashboard_id}"
    else:
        url = f"{BASE_URL}/api/saved_objects/dashboard/{dashboard_id}"
    try:
        # Always delete and recreate the dashboard so panel order matches YAML
        requests.delete(url, auth=(USERNAME, PASSWORD), headers={"osd-xsrf": "true"}, verify=False, timeout=10)
        response = requests.post(url, auth=(USERNAME, PASSWORD), headers={"Content-Type": "application/json", "osd-xsrf": "true"}, json=dashboard_payload, verify=False, timeout=10)
        if response.status_code == 200:
            print(f"✅ Created {dashboard_config['title']} dashboard ({len(created_ids)} panels)")
            return dashboard_id
        else:
            print(f"⚠️  Dashboard creation failed: {response.text[:200]}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating dashboard: {e}")
        return None


def create_overview_dashboard(workspace_id):
    """Create an overview landing dashboard with markdown links to all observability features"""
    import json
    import base64

    markdown_vis_id = "overview-markdown"
    dashboard_id = "observability-overview-dashboard"

    # Check if dashboard already exists
    if get_existing_dashboard(workspace_id, dashboard_id):
        print("✅ Overview dashboard already exists")
        set_default_dashboard(workspace_id, dashboard_id)
        return dashboard_id

    print("📊 Creating Observability Stack overview dashboard...")

    # Load architecture image as base64 data URI
    arch_img_tag = ""
    try:
        with open("/config/architecture.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
            arch_img_tag = f"![Architecture](data:image/png;base64,{img_b64})"
    except FileNotFoundError:
        print("⚠️  Architecture image not found, using text fallback")
        arch_img_tag = "*Agents / Apps → OTel Collector → Data Prepper → OpenSearch + Prometheus*"

    # Build workspace-aware links
    if workspace_id and workspace_id != "default":
        w = f"/w/{workspace_id}"
    else:
        w = ""

    markdown_text = f"""## Welcome to OpenSearch Observability Stack!
Your entire stack, fully visible. APM traces, logs, Prometheus metrics, service maps, and AI agent tracing — unified in one open-source platform built for modern infrastructure. Total observability, zero lock-in.

[Observability Stack Website](https://observability.opensearch.org) | [GitHub](https://github.com/opensearch-project/observability-stack)

### Architecture
{arch_img_tag}

---

### Getting started
For full setup instructions and guides, see the [Documentation](https://observability.opensearch.org/docs/).

1. **Send telemetry** to the OTel Collector via gRPC (`:4317`) or HTTP (`:4318`)
2. **Explore logs** to see application log events
3. **Explore traces** to follow requests across services
4. **Check APM services** for latency, error rates, and throughput
5. **View the service map** for a visual topology of your system

---

### Explore telemetry
**Logs** — [Explore logs]({w}/app/explore/logs)
Search, filter, and analyze application and infrastructure log events.

**Traces** — [Explore traces]({w}/app/explore/traces)
Follow requests end-to-end across services to pinpoint latency and errors.

**Metrics** — [Explore metrics]({w}/app/explore/metrics)
Query Prometheus metrics for throughput, latency percentiles, and error rates.

### APM & services
**APM services** — [Service list]({w}/app/observability-apm-services#/services)
View latency, error rate, and throughput (RED metrics) for every instrumented service.

**Service map** — [View service map]({w}/app/observability-apm-application-map)
Visualize service-to-service dependencies and traffic flow across your system.

### Agent observability
**Agent traces** — [Explore agent traces]({w}/app/agentTraces)
Inspect individual AI agent invocations, tool calls, and LLM interactions.

**Agent dashboard** — [Agent observability dashboard]({w}/app/dashboards#/view/agent-observability-dashboard)
Monitor agent activity, token usage, and tool execution at a glance.
"""

    # Create the markdown visualization
    vis_state = {
        "title": "",
        "type": "markdown",
        "params": {
            "fontSize": 12,
            "openLinksInNewTab": False,
            "markdown": markdown_text,
        },
        "aggs": [],
    }

    vis_payload = {
        "attributes": {
            "title": "",
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({})
            },
        },
    }

    if workspace_id and workspace_id != "default":
        vis_payload["workspaces"] = [workspace_id]
        vis_url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/visualization/{markdown_vis_id}"
    else:
        vis_url = f"{BASE_URL}/api/saved_objects/visualization/{markdown_vis_id}"

    try:
        response = requests.post(
            vis_url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=vis_payload,
            verify=False,
            timeout=10,
        )

        if response.status_code not in (200, 409):
            print(f"⚠️  Overview markdown creation failed: {response.text}")
            return None
        print(f"✅ Created overview markdown visualization")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating overview markdown: {e}")
        return None

    # Create the dashboard with a single full-width markdown panel
    panels = [
        {
            "version": "3.5.0",
            "gridData": {"x": 0, "y": 0, "w": 48, "h": 35, "i": "0"},
            "panelIndex": "0",
            "embeddableConfig": {},
            "panelRefName": "panel_0",
        }
    ]

    dashboard_payload = {
        "attributes": {
            "title": "Observability Stack Overview",
            "description": "Landing page with links to all observability features",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": True}),
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(
                    {"query": {"query": "", "language": "kuery"}, "filter": []}
                )
            },
        },
        "references": [
            {"name": "panel_0", "type": "visualization", "id": markdown_vis_id}
        ],
    }

    if workspace_id and workspace_id != "default":
        dashboard_payload["workspaces"] = [workspace_id]
        dash_url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/dashboard/{dashboard_id}"
    else:
        dash_url = f"{BASE_URL}/api/saved_objects/dashboard/{dashboard_id}"

    try:
        response = requests.post(
            dash_url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=dashboard_payload,
            verify=False,
            timeout=10,
        )

        if response.status_code in (200, 409):
            print(f"✅ Created Observability Stack overview dashboard")
            set_default_dashboard(workspace_id, dashboard_id)
            return dashboard_id
        else:
            print(f"⚠️  Overview dashboard creation failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error creating overview dashboard: {e}")
        return None


def _has_virtual_reference(obj):
    """Check if a saved object references a virtual index pattern (e.g. Prometheus datasource).

    Virtual index patterns are created at runtime by datasource plugins and don't
    exist as persisted saved objects — the _import API rejects them as missing refs.
    """
    VIRTUAL_INDEX_PATTERNS = {"ObservabilityStack_Prometheus"}
    for ref in obj.get("references", []):
        if ref.get("type") == "index-pattern" and ref.get("id") in VIRTUAL_INDEX_PATTERNS:
            return True
    return False


def _create_saved_object_directly(workspace_id, obj):
    """Create a single saved object via the individual saved-objects API.

    Unlike _import, this API does not validate references, so objects that
    reference virtual index patterns (e.g. Prometheus) can be created.
    """
    obj_type = obj.get("type")
    obj_id = obj.get("id")
    title = obj.get("attributes", {}).get("title", obj_id)

    payload = {"attributes": obj.get("attributes", {}), "references": obj.get("references", [])}
    if workspace_id and workspace_id != "default":
        payload["workspaces"] = [workspace_id]
        url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/{obj_type}/{obj_id}"
    else:
        url = f"{BASE_URL}/api/saved_objects/{obj_type}/{obj_id}"

    try:
        response = requests.post(
            url, auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json=payload, verify=False, timeout=10,
        )
        if response.status_code == 200:
            print(f"  ✅ {title} (created directly)")
            return True
        elif response.status_code == 409:
            # Already exists — update
            update_payload = {"attributes": obj.get("attributes", {}), "references": obj.get("references", [])}
            requests.put(
                url, auth=(USERNAME, PASSWORD),
                headers={"Content-Type": "application/json", "osd-xsrf": "true"},
                json=update_payload, verify=False, timeout=10,
            )
            print(f"  🔄 {title} (updated directly)")
            return True
        else:
            print(f"  ⚠️  {title}: {response.status_code} {response.text[:100]}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  {title}: {e}")
        return False


def import_ndjson_dashboard(workspace_id, ndjson_path, id_mappings=None):
    """Import a dashboard and its dependencies from an ndjson export file.

    Objects that reference virtual index patterns (e.g. Prometheus datasource)
    are separated out and created individually via the saved-objects API, which
    does not validate references. The remaining objects are bulk-imported via the
    _import API.

    id_mappings: optional dict of {old_id: new_id} to rewrite references at
    import time. Used to point exported objects at the live index-pattern IDs
    instead of the hardcoded ones from the export environment.
    """
    import json
    import io

    print(f"📦 Importing dashboard from {os.path.basename(ndjson_path)}...")

    try:
        with open(ndjson_path, "r") as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        print(f"⚠️  File not found: {ndjson_path}")
        return None

    importable = []
    direct_create = []

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Skip the export summary line (has exportedCount but no type)
        if "exportedCount" in obj and "type" not in obj:
            continue
        # Skip index-pattern objects — they are created earlier by the init
        # script with the correct workspace/datasource associations. Importing
        # them again from the ndjson would create duplicates with different IDs.
        if obj.get("type") == "index-pattern":
            continue
        # Remove workspace associations so objects land in the target workspace
        obj.pop("workspaces", None)
        # Remove version field that can cause conflicts on import
        obj.pop("version", None)

        # Rewrite references to point at the live index-pattern IDs
        if id_mappings:
            for ref in obj.get("references", []):
                if ref.get("id") in id_mappings:
                    ref["id"] = id_mappings[ref["id"]]

        if _has_virtual_reference(obj):
            direct_create.append(obj)
        else:
            importable.append(json.dumps(obj, separators=(",", ":")))

    if not importable and not direct_create:
        print("⚠️  No valid saved objects found in ndjson file")
        return None

    total_success = 0

    # Bulk-import objects without virtual references
    if importable:
        ndjson_body = "\n".join(importable) + "\n"

        if workspace_id and workspace_id != "default":
            url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/_import?overwrite=true"
        else:
            url = f"{BASE_URL}/api/saved_objects/_import?overwrite=true"

        try:
            response = requests.post(
                url, auth=(USERNAME, PASSWORD), headers={"osd-xsrf": "true"},
                files={"file": ("dashboard.ndjson", io.BytesIO(ndjson_body.encode("utf-8")), "application/ndjson")},
                verify=False, timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                total_success += result.get("successCount", 0)
                for err in result.get("errors", []):
                    print(f"  ⚠️  {err.get('type', '?')}/{err.get('id', '?')}: {err.get('error', {}).get('message', 'unknown error')}")
            else:
                print(f"⚠️  Bulk import failed ({response.status_code}): {response.text[:200]}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error during bulk import: {e}")

    # Create objects with virtual references individually
    for obj in direct_create:
        if _create_saved_object_directly(workspace_id, obj):
            total_success += 1

    print(f"✅ Imported {total_success} saved objects from {os.path.basename(ndjson_path)}")
    return total_success


def main():
    """Initialize OpenSearch Dashboards with workspace and datasources"""
    wait_for_dashboards()

    # Configure ISM retention policies (overrides Data Prepper rollover-only defaults)
    configure_ism_policies()

    # Check for existing workspace
    workspace_id = get_existing_workspace()

    if workspace_id:
        print("✅ Observability Stack workspace already exists")
    else:
        workspace_id = create_workspace()

    # Create index patterns (idempotent - will skip if already exist)
    # Titles must match exactly what the APM plugin expects
    logs_schema_mappings = '{"otelLogs":{"timestamp":"time","traceId":"traceId","spanId":"spanId","serviceName":"resource.attributes.service.name"}}'
    logs_pattern_id = create_index_pattern(
        workspace_id, "logs-otel-v1*", "time", "logs", logs_schema_mappings,
        display_name="Log Dataset - Local Cluster"
    )
    traces_pattern_id = create_index_pattern(
        workspace_id, "otel-v1-apm-span*", "endTime", "traces",
        display_name="Trace Dataset - Local Cluster"
    )
    service_map_pattern_id = create_index_pattern(
        workspace_id, "otel-v2-apm-service-map*", "timestamp"
    )

    print("📊 Created index patterns for spans, logs, and service map")

    # Warm the field list immediately after creation. Patterns created via the
    # raw saved-objects API land with an empty `fields` attribute (OSD only
    # fetches fields lazily on first Discover/Explore visit, and the on-read
    # auto-fetch safety net was removed upstream). Without this, pre-generated
    # datasets show "Fields (0)" and charts error with "Could not locate that
    # index-pattern-field" until a manual refresh. This mirrors what the
    # dataset-creation wizard does (pre-fetch _fields_for_wildcard at create
    # time). delayed_field_refresh() below remains the backstop for indices
    # that are still empty at init time.
    for pid, title in (
        (logs_pattern_id, "logs-otel-v1*"),
        (traces_pattern_id, "otel-v1-apm-span*"),
        (service_map_pattern_id, "otel-v2-apm-service-map*"),
    ):
        refresh_index_pattern_fields(workspace_id, pid, title)

    # Set logs as the default index pattern
    if logs_pattern_id:
        set_default_index_pattern(workspace_id, logs_pattern_id)

    # Create trace-to-logs correlation for cross-signal navigation
    if traces_pattern_id and logs_pattern_id:
        create_trace_to_logs_correlation(workspace_id, traces_pattern_id, logs_pattern_id)

    # Create Agent Observability dashboard
    if traces_pattern_id:
        create_agent_observability_dashboard(workspace_id, traces_pattern_id)

    # Create overview landing dashboard (becomes the new default)
    create_overview_dashboard(workspace_id)

    # Create self-monitoring dashboards (PromQL explore panels)
    create_promql_dashboard_from_yaml(workspace_id, "/config/dashboard-pipeline-health.yaml")
    create_promql_dashboard_from_yaml(workspace_id, "/config/dashboard-opensearch-health.yaml")

    # Create datasources (must happen before ndjson import so Prometheus references resolve)
    prometheus_datasource_id = create_prometheus_datasource(workspace_id)
    create_opensearch_datasource(workspace_id)

    # Import Astronomy Shop dashboard (ndjson export with all dependencies).
    # Map the hardcoded index-pattern IDs from the export to the live IDs
    # created above, so dashboard panels reference the correct datasets.
    ndjson_id_mappings = {}
    if logs_pattern_id:
        ndjson_id_mappings["545c7990-2938-11f1-84ad-e734b5ac5a91"] = logs_pattern_id
    if traces_pattern_id:
        ndjson_id_mappings["54f4c1f0-2938-11f1-84ad-e734b5ac5a91"] = traces_pattern_id
    if service_map_pattern_id:
        ndjson_id_mappings["55f4c1f0-2938-11f1-84ad-e734b5ac5a91"] = service_map_pattern_id
    import_ndjson_dashboard(workspace_id, "/config/dashboard-astronomy-shop.ndjson", ndjson_id_mappings)
    # Astronomy shop - service telemetry: 12-panel dashboard with service-name and
    # SDK-language variables; reuses the logs/span/service-map index patterns and
    # the ObservabilityStack_Prometheus datasource created above.
    import_ndjson_dashboard(workspace_id, "/config/dashboard-astronomy-service-telemetry.ndjson", ndjson_id_mappings)

    # Create saved queries for common agent observability patterns
    create_default_saved_queries(workspace_id)

    # Create APM config correlation (ties traces + service map + Prometheus)
    if traces_pattern_id and service_map_pattern_id:
        # Resolve Prometheus data-connection saved object ID
        prom_so_id = get_existing_prometheus_datasource("ObservabilityStack_Prometheus")
        create_apm_config_correlation(
            workspace_id, traces_pattern_id, service_map_pattern_id, prom_so_id
        )

    # Output summary
    print()
    print("🎉 Observability Stack Ready!")
    print(f"👤 Username: {USERNAME}")
    print(f"🔑 Password: {PASSWORD}")

    # Generate appropriate dashboard URL
    if workspace_id and workspace_id != "default":
        dashboard_url = f"http://localhost:5601/w/{workspace_id}/app/dashboards#/view/observability-overview-dashboard"
    else:
        dashboard_url = "http://localhost:5601/app/home"

    print(f"\033[1m📊 OpenSearch Dashboards: {dashboard_url}\033[0m")
    print(f"📈 Prometheus: http://localhost:{PROMETHEUS_PORT}")
    print()

def refresh_index_pattern_fields(workspace_id, pattern_id, title):
    """Refresh the fields list for an index pattern by querying OpenSearch mappings.

    OSD populates fields lazily on first Discover/Explore visit. This function
    triggers the same refresh via the API so field lists are available immediately.
    """
    if not pattern_id:
        return False

    if workspace_id and workspace_id != "default":
        url = f"{BASE_URL}/w/{workspace_id}/api/index_patterns/_fields_for_wildcard"
    else:
        url = f"{BASE_URL}/api/index_patterns/_fields_for_wildcard"

    # Only `pattern` is passed. Do NOT send `meta_fields` — this OSD version's
    # route validation rejects the repeated meta_fields query params with a 400
    # ("[request query.params]: definition for this key is missing"). requests
    # URL-encodes the pattern's wildcard/special chars via the params dict.
    try:
        resp = requests.get(
            url, auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            params={"pattern": title},
            verify=False, timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ⚠️  Failed to fetch fields for {title}: {resp.status_code}")
            return False

        fields = resp.json().get("fields", [])
        if not fields:
            print(f"  ⏭️  No fields found for {title} (index may be empty)")
            return False

        import json
        fields_json = json.dumps(fields)

        if workspace_id and workspace_id != "default":
            put_url = f"{BASE_URL}/w/{workspace_id}/api/saved_objects/index-pattern/{pattern_id}"
        else:
            put_url = f"{BASE_URL}/api/saved_objects/index-pattern/{pattern_id}"

        put_resp = requests.put(
            put_url, auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/json", "osd-xsrf": "true"},
            json={"attributes": {"fields": fields_json}},
            verify=False, timeout=10,
        )
        if put_resp.status_code == 200:
            print(f"  ✅ Refreshed fields for {title} ({len(fields)} fields)")
            return True
        else:
            print(f"  ⚠️  Failed to update fields for {title}: {put_resp.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  Error refreshing fields for {title}: {e}")
        return False


def delayed_field_refresh(workspace_id, titles, max_attempts=12, interval_minutes=5):
    """Periodically refresh field lists until every pattern is populated.

    main() warms the field lists immediately, but indices that are still empty
    at init time (otel-demo and agent examples take a while to send their first
    documents) return no fields on that first pass. Rather than a single blind
    wait, poll on an interval and retry only the patterns that haven't been
    populated yet, stopping early once they all succeed. With the defaults this
    covers a one-hour window (12 attempts × 5 minutes).

    Patterns are resolved by title on every attempt rather than once up front,
    so this self-heals regardless of start order: if the backstop starts before
    main() has created the index patterns, the early attempts simply find
    nothing and retry until the patterns exist. This is what lets the compose
    service / k8s Job run without a hard `depends_on` the init step — a
    dependency that otherwise breaks `docker compose up --wait` (a
    `service_completed_successfully` target exiting mid-startup makes --wait
    abort with a non-zero code).
    """
    pending = list(titles)

    print(
        f"\n⏳ Will refresh field lists as indices populate "
        f"(up to {max_attempts} attempts every {interval_minutes} min)..."
    )
    for attempt in range(1, max_attempts + 1):
        print(f"🔄 Field refresh attempt {attempt}/{max_attempts} ({len(pending)} pending)...")
        still_pending = []
        for title in pending:
            pattern_id = get_existing_index_pattern(workspace_id, title)
            if not pattern_id:
                # Pattern not created yet (backstop outran init) — retry later.
                still_pending.append(title)
                continue
            if not refresh_index_pattern_fields(workspace_id, pattern_id, title):
                still_pending.append(title)
        pending = still_pending
        if not pending:
            print("✅ Field refresh complete — all patterns populated")
            return
        # Sleep between attempts (not before the first / after the last), so a
        # stack whose indices are already populated exits promptly.
        if attempt < max_attempts:
            time.sleep(interval_minutes * 60)

    print(
        f"⚠️  Field refresh finished with {len(pending)} pattern(s) still empty: "
        f"{', '.join(pending)}"
    )


def run_field_refresh_backstop():
    """Run the delayed field-refresh loop as a standalone process.

    Split out from main() so it can run as a separate, long-running process
    (its own compose service / Kubernetes Job). main() is the fast, blocking
    setup that a Helm post-install/upgrade hook waits on; this backstop can run
    for up to an hour and must never block install/upgrade completion.

    Intentionally has no hard ordering dependency on the init step: it waits for
    dashboards, then delayed_field_refresh() resolves pattern IDs by title on
    each attempt, so it works whether it starts before or after init.
    """
    wait_for_dashboards()
    workspace_id = get_existing_workspace()
    titles = ["logs-otel-v1*", "otel-v1-apm-span*", "otel-v2-apm-service-map*"]
    delayed_field_refresh(workspace_id, titles)


if __name__ == "__main__":
    import sys

    # Two modes, run as separate processes so the long-running field-refresh
    # backstop never blocks init completion (or a Helm hook):
    #   (default)      → main(): fast one-shot setup + immediate field warm
    #   refresh-loop   → periodic field refresh until indices populate
    mode = sys.argv[1] if len(sys.argv) > 1 else "init"
    if mode == "refresh-loop":
        run_field_refresh_backstop()
    else:
        main()
