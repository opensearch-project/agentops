"""
Telemetry validation module for the canary system.

This module provides the TelemetryValidator class that queries Prometheus and
OpenSearch to verify that telemetry data (metrics and traces) is correctly
stored with proper gen-ai semantic convention attributes.
"""

import requests
from typing import List
import urllib3

# Disable SSL warnings for development (OpenSearch uses self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TelemetryValidator:
    """
    Validates telemetry data in Prometheus and OpenSearch.
    
    This validator queries the ATLAS observability stack to verify that:
    1. Metrics are correctly stored in Prometheus
    2. Traces are correctly stored in OpenSearch
    3. Required gen-ai semantic convention attributes are present
    """
    
    def __init__(
        self,
        prometheus_url: str,
        opensearch_url: str,
        opensearch_user: str,
        opensearch_password: str
    ):
        """
        Initialize telemetry validator.
        
        Args:
            prometheus_url: Prometheus base URL (e.g., http://localhost:9090)
            opensearch_url: OpenSearch base URL (e.g., https://localhost:9200)
            opensearch_user: OpenSearch username
            opensearch_password: OpenSearch password
        """
        self.prometheus_url = prometheus_url.rstrip('/')
        self.opensearch_url = opensearch_url.rstrip('/')
        self.opensearch_user = opensearch_user
        self.opensearch_password = opensearch_password
    
    def validate_metrics(self, conversation_id: str, agent_name: str = None) -> List[str]:
        """
        Query Prometheus for gen-ai metrics and validate they exist.
        
        This method queries Prometheus for the gen_ai.client.token.usage metric.
        Since conversation_id is a high-cardinality attribute not suitable for
        metric labels, we query by service_name (agent_name) instead and just
        verify that metrics exist for the agent.
        
        Args:
            conversation_id: Conversation ID (used for error messages)
            agent_name: Agent name to filter metrics by (optional)
        
        Returns:
            List of validation errors (empty list if all valid)
        """
        errors = []
        
        try:
            # Query for token usage metrics
            # Note: Prometheus metric names use underscores, not dots
            # The counter metric has _total suffix
            # We query by service_name since conversation_id is not a metric label
            if agent_name:
                query = f'gen_ai_client_token_usage_total{{service_name="{agent_name}"}}'
            else:
                query = 'gen_ai_client_token_usage_total'
            
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=10
            )
            
            if response.status_code != 200:
                errors.append(
                    f"Prometheus query failed with status {response.status_code}: {response.text}"
                )
                return errors
            
            data = response.json()
            
            # Check if query was successful
            if data.get("status") != "success":
                errors.append(
                    f"Prometheus query returned non-success status: {data.get('status')}"
                )
                return errors
            
            # Check if any results were returned
            results = data.get("data", {}).get("result", [])
            if not results:
                if agent_name:
                    errors.append(
                        f"No gen_ai_client_token_usage_total metrics found in Prometheus "
                        f"for agent: {agent_name}"
                    )
                else:
                    errors.append(
                        f"No gen_ai_client_token_usage_total metrics found in Prometheus"
                    )
        
        except requests.exceptions.RequestException as e:
            errors.append(f"Failed to connect to Prometheus: {str(e)}")
        except Exception as e:
            errors.append(f"Unexpected error querying Prometheus: {str(e)}")
        
        return errors
    
    def validate_traces(self, conversation_id: str) -> List[str]:
        """
        Query OpenSearch for traces and validate gen-ai attributes.
        
        This method queries OpenSearch for traces with the given conversation_id
        and validates that required gen-ai semantic convention attributes are
        present in the spans.
        
        Required attributes for agent invocation spans:
        - gen_ai.operation.name
        - gen_ai.agent.id
        - gen_ai.agent.name
        
        Required attributes for tool execution spans:
        - gen_ai.operation.name (should be "execute_tool")
        - gen_ai.tool.name
        
        Args:
            conversation_id: Conversation ID to filter traces by
        
        Returns:
            List of validation errors (empty list if all valid)
        """
        errors = []
        
        try:
            # Query OpenSearch for traces with the conversation_id
            # OpenSearch stores traces in otel-v1-apm-span-* indices
            # The conversation_id is nested under attributes
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"attributes.gen_ai.conversation.id.keyword": conversation_id}}
                        ]
                    }
                },
                "size": 100  # Get up to 100 spans
            }
            
            response = requests.post(
                f"{self.opensearch_url}/otel-v1-apm-span-*/_search",
                auth=(self.opensearch_user, self.opensearch_password),
                json=query,
                verify=False,  # Disable SSL verification for development
                timeout=10
            )
            
            if response.status_code != 200:
                errors.append(
                    f"OpenSearch query failed with status {response.status_code}: {response.text}"
                )
                return errors
            
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            
            if not hits:
                errors.append(
                    f"No traces found in OpenSearch for conversation_id: {conversation_id}"
                )
                return errors
            
            # Validate each span for required attributes
            for i, hit in enumerate(hits):
                source = hit.get("_source", {})
                span_id = source.get("spanId", f"span_{i}")
                attributes = source.get("attributes", {})
                operation_name = attributes.get("gen_ai.operation.name")
                
                # Check for required gen-ai attributes in all spans
                required_base_attrs = [
                    "gen_ai.operation.name",
                    "gen_ai.agent.id",
                    "gen_ai.agent.name"
                ]
                
                for attr in required_base_attrs:
                    if attr not in attributes or attributes[attr] is None:
                        errors.append(
                            f"Span {span_id}: Missing required attribute '{attr}'"
                        )
                
                # If this is a tool execution span, check for tool.name
                if operation_name == "execute_tool":
                    if "gen_ai.tool.name" not in attributes or attributes["gen_ai.tool.name"] is None:
                        errors.append(
                            f"Span {span_id}: Tool execution span missing 'gen_ai.tool.name' attribute"
                        )
        
        except requests.exceptions.RequestException as e:
            errors.append(f"Failed to connect to OpenSearch: {str(e)}")
        except Exception as e:
            errors.append(f"Unexpected error querying OpenSearch: {str(e)}")
        
        return errors
    
    def validate(self, conversation_id: str) -> List[str]:
        """
        Validate both metrics and traces for a conversation.
        
        This is a convenience method that runs both metric and trace validation
        and returns all errors combined.
        
        Args:
            conversation_id: Conversation ID to validate
        
        Returns:
            List of all validation errors (empty list if all valid)
        """
        errors = []
        errors.extend(self.validate_metrics(conversation_id))
        errors.extend(self.validate_traces(conversation_id))
        return errors
