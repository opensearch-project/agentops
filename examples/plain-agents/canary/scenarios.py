"""
Canary scenario base class and data models.

This module provides the base class for canary scenarios and the result
data model for scenario execution.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class SpanRelationship:
    """Represents a parent-child span relationship."""

    parent_span_id: str
    parent_agent_id: str
    parent_agent_name: str
    child_span_id: str
    child_agent_id: str
    child_agent_name: str
    trace_id: str
    conversation_id: str


@dataclass
class TraceHierarchyValidation:
    """Result of trace hierarchy validation."""

    is_valid: bool
    trace_id: str
    relationships: List[SpanRelationship] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Result of a canary scenario execution."""

    scenario_name: str
    success: bool
    duration_seconds: float
    error_message: Optional[str] = None
    conversation_id: Optional[str] = None
    fault_injection_enabled: bool = False
    active_fault_profiles: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the scenario result
        """
        return {
            "scenario_name": self.scenario_name,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "conversation_id": self.conversation_id,
            "fault_injection_enabled": self.fault_injection_enabled,
            "active_fault_profiles": self.active_fault_profiles,
        }


class CanaryScenario(ABC):
    """Base class for canary scenarios."""

    def __init__(self, name: str, description: str):
        """
        Initialize canary scenario.

        Args:
            name: Scenario name
            description: Scenario description
        """
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, agent) -> ScenarioResult:
        """
        Execute the scenario with the given agent.

        Args:
            agent: Configurable agent to use for scenario

        Returns:
            ScenarioResult with execution details
        """


class SimpleToolCallScenario(CanaryScenario):
    """Single agent invocation with one tool call.

    This scenario validates basic agent-tool interaction and telemetry
    generation by invoking the agent with a simple weather query.
    """

    def __init__(self):
        super().__init__(
            name="simple_tool_call",
            description="Single agent invocation with one tool call"
        )

    def execute(self, agent) -> ScenarioResult:
        """Execute simple tool call scenario.

        Args:
            agent: Configurable agent to use for scenario

        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        conversation_id = f"conv_simple_{int(time.time())}"

        try:
            response = agent.invoke(
                "What's the weather in Paris?",
                conversation_id
            )
            duration = time.time() - start_time

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_seconds=duration,
                conversation_id=conversation_id
            )
        except Exception as e:
            duration = time.time() - start_time
            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_seconds=duration,
                error_message=str(e),
                conversation_id=conversation_id
            )


class MultiToolChainScenario(CanaryScenario):
    """Multiple tool calls in sequence.

    This scenario tests the agent's ability to chain operations and
    maintain context across multiple tool invocations.
    """

    def __init__(self):
        super().__init__(
            name="multi_tool_chain",
            description="Agent invocation with multiple sequential tool calls"
        )

    def execute(self, agent) -> ScenarioResult:
        """Execute multi-tool chain scenario.

        Args:
            agent: Configurable agent to use for scenario

        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        conversation_id = f"conv_multi_{int(time.time())}"

        try:
            # First tool call
            response1 = agent.invoke(
                "What's the weather in Paris?",
                conversation_id
            )

            # Second tool call in same conversation
            response2 = agent.invoke(
                "What's the weather in London?",
                conversation_id
            )

            # Third tool call in same conversation
            response3 = agent.invoke(
                "What's the weather in Tokyo?",
                conversation_id
            )

            duration = time.time() - start_time

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_seconds=duration,
                conversation_id=conversation_id
            )
        except Exception as e:
            duration = time.time() - start_time
            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_seconds=duration,
                error_message=str(e),
                conversation_id=conversation_id
            )


class ToolFailureScenario(CanaryScenario):
    """Tool execution with high failure rate.

    This scenario tests error handling and recovery by using an agent
    configured with a high tool failure rate.
    """

    def __init__(self):
        super().__init__(
            name="tool_failure",
            description="Agent with high tool failure rate to test error handling"
        )

    def execute(self, agent) -> ScenarioResult:
        """Execute tool failure scenario.

        This scenario expects the agent to handle tool failures gracefully.
        The scenario succeeds if the agent properly handles the error
        (catches exception and reports it).

        Args:
            agent: Configurable agent with high failure rate tool provider

        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        conversation_id = f"conv_failure_{int(time.time())}"

        try:
            # This should trigger a tool failure
            response = agent.invoke(
                "What's the weather in Paris?",
                conversation_id
            )

            # If we get here, either the tool didn't fail or the agent
            # handled the failure gracefully
            duration = time.time() - start_time

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_seconds=duration,
                conversation_id=conversation_id
            )
        except Exception as e:
            # Tool failure is expected, so we consider this a success
            # if the error is properly propagated
            duration = time.time() - start_time

            # Check if this is a tool failure (expected)
            if "Mock tool failure" in str(e) or "Tool execution failed" in str(e):
                return ScenarioResult(
                    scenario_name=self.name,
                    success=True,  # Expected failure
                    duration_seconds=duration,
                    error_message=f"Expected tool failure: {str(e)}",
                    conversation_id=conversation_id
                )
            else:
                # Unexpected error
                return ScenarioResult(
                    scenario_name=self.name,
                    success=False,
                    duration_seconds=duration,
                    error_message=str(e),
                    conversation_id=conversation_id
                )


class HighTokenUsageScenario(CanaryScenario):
    """Large input text to test token calculation.

    This scenario generates large inputs (>1000 characters) to verify
    that token calculation and metrics work correctly with high counts.
    """

    def __init__(self):
        super().__init__(
            name="high_token_usage",
            description="Large input text to test token calculation and metrics"
        )

    def execute(self, agent) -> ScenarioResult:
        """Execute high token usage scenario.

        Args:
            agent: Configurable agent to use for scenario

        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        conversation_id = f"conv_high_token_{int(time.time())}"

        try:
            # Generate large input text (>1000 characters)
            large_text = (
                "I need detailed weather information for the following cities: "
                + ", ".join([f"City{i}" for i in range(200)])
                + ". Please provide comprehensive weather data including "
                "temperature, humidity, wind speed, precipitation, "
                "atmospheric pressure, visibility, UV index, and any "
                "weather warnings or advisories for each location. "
                "Additionally, I would like to know the forecast for "
                "the next 7 days for each city, including hourly "
                "breakdowns of temperature changes, precipitation "
                "probability, and wind patterns. This information is "
                "critical for planning purposes and needs to be as "
                "detailed and accurate as possible."
            )

            response = agent.invoke(large_text, conversation_id)
            duration = time.time() - start_time

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_seconds=duration,
                conversation_id=conversation_id
            )
        except Exception as e:
            duration = time.time() - start_time
            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_seconds=duration,
                error_message=str(e),
                conversation_id=conversation_id
            )


class ConversationContextScenario(CanaryScenario):
    """Multi-turn conversation with context maintenance.

    This scenario executes multiple turns in a conversation using the
    same conversation_id to verify context is maintained across turns.
    """

    def __init__(self):
        super().__init__(
            name="conversation_context",
            description="Multi-turn conversation to test context maintenance"
        )

    def execute(self, agent) -> ScenarioResult:
        """Execute conversation context scenario.

        Args:
            agent: Configurable agent to use for scenario

        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        conversation_id = f"conv_context_{int(time.time())}"

        try:
            # Turn 1: Initial query
            response1 = agent.invoke(
                "What's the weather in Paris?",
                conversation_id
            )

            # Turn 2: Follow-up query (same conversation)
            response2 = agent.invoke(
                "What about London?",
                conversation_id
            )

            # Turn 3: Another follow-up (same conversation)
            response3 = agent.invoke(
                "And how about Tokyo?",
                conversation_id
            )

            duration = time.time() - start_time

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_seconds=duration,
                conversation_id=conversation_id
            )
        except Exception as e:
            duration = time.time() - start_time
            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_seconds=duration,
                error_message=str(e),
                conversation_id=conversation_id
            )


class MultiAgentScenario(CanaryScenario):
    """Parent agent invoking child agents.

    This scenario creates a parent agent that invokes child agents,
    testing span hierarchy and parent-child relationships in traces.
    All agents run in the same Python process.
    """

    def __init__(self):
        super().__init__(
            name="multi_agent",
            description="Parent agent invoking child agents to test span hierarchy"
        )

    def validate_trace_hierarchy(
        self,
        trace_id: str,
        expected_relationships: List[SpanRelationship],
        opensearch_url: str,
        opensearch_user: str,
        opensearch_password: str,
    ) -> TraceHierarchyValidation:
        """
        Validate trace hierarchy in OpenSearch.

        This method queries OpenSearch for all spans with the given trace_id
        and validates that:
        1. Each expected parent-child relationship exists in the trace data
        2. All agents have unique agent_id and agent_name values
        3. All agents share the same conversation_id

        Args:
            trace_id: Trace ID to validate
            expected_relationships: List of expected parent-child relationships
            opensearch_url: OpenSearch base URL
            opensearch_user: OpenSearch username
            opensearch_password: OpenSearch password

        Returns:
            TraceHierarchyValidation with validation results and errors
        """
        import requests
        import urllib3

        # Disable SSL warnings for development
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        errors = []
        found_relationships = []

        try:
            # Query OpenSearch for all spans with the given trace_id
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"traceId": trace_id}},
                            {
                                "term": {
                                    "attributes.gen_ai.operation.name": "invoke_agent"
                                }
                            },
                        ]
                    }
                },
                "sort": [{"startTime": "asc"}],
                "size": 100,  # Get up to 100 spans
            }

            response = requests.post(
                f"{opensearch_url.rstrip('/')}/otel-v1-apm-span-*/_search",
                auth=(opensearch_user, opensearch_password),
                json=query,
                verify=False,
                timeout=10,
            )

            if response.status_code != 200:
                errors.append(
                    f"OpenSearch query failed with status {response.status_code}: {response.text}"
                )
                return TraceHierarchyValidation(
                    is_valid=False, trace_id=trace_id, relationships=[], errors=errors
                )

            data = response.json()
            hits = data.get("hits", {}).get("hits", [])

            if not hits:
                errors.append(
                    f"No invoke_agent spans found in OpenSearch for trace_id: {trace_id}"
                )
                return TraceHierarchyValidation(
                    is_valid=False, trace_id=trace_id, relationships=[], errors=errors
                )

            # Build span map: span_id -> span data
            span_map = {}
            agent_ids = set()
            agent_names = set()
            conversation_ids = set()

            for hit in hits:
                source = hit.get("_source", {})
                span_id = source.get("spanId")
                parent_span_id = source.get("parentSpanId")
                attributes = source.get("attributes", {})

                agent_id = attributes.get("gen_ai.agent.id")
                agent_name = attributes.get("gen_ai.agent.name")
                conversation_id = attributes.get("gen_ai.conversation.id")

                if span_id:
                    span_map[span_id] = {
                        "span_id": span_id,
                        "parent_span_id": parent_span_id,
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "conversation_id": conversation_id,
                        "trace_id": source.get("traceId"),
                    }

                    # Collect unique values for validation
                    if agent_id:
                        agent_ids.add(agent_id)
                    if agent_name:
                        agent_names.add(agent_name)
                    if conversation_id:
                        conversation_ids.add(conversation_id)

            # Verify each expected relationship exists
            for expected in expected_relationships:
                # Find parent span
                parent_span = span_map.get(expected.parent_span_id)
                if not parent_span:
                    errors.append(
                        f"Expected parent span {expected.parent_span_id} "
                        f"(agent: {expected.parent_agent_id}) not found in trace"
                    )
                    continue

                # Find child span
                child_span = span_map.get(expected.child_span_id)
                if not child_span:
                    errors.append(
                        f"Expected child span {expected.child_span_id} "
                        f"(agent: {expected.child_agent_id}) not found in trace"
                    )
                    continue

                # Verify parent-child relationship
                if child_span["parent_span_id"] != expected.parent_span_id:
                    errors.append(
                        f"Span {expected.child_span_id} has parent_span_id "
                        f"{child_span['parent_span_id']}, expected {expected.parent_span_id}"
                    )
                    continue

                # Verify agent IDs match
                if parent_span["agent_id"] != expected.parent_agent_id:
                    errors.append(
                        f"Parent span {expected.parent_span_id} has agent_id "
                        f"{parent_span['agent_id']}, expected {expected.parent_agent_id}"
                    )

                if child_span["agent_id"] != expected.child_agent_id:
                    errors.append(
                        f"Child span {expected.child_span_id} has agent_id "
                        f"{child_span['agent_id']}, expected {expected.child_agent_id}"
                    )

                # If all checks passed, add to found relationships
                if not any(
                    expected.child_span_id in err or expected.parent_span_id in err
                    for err in errors
                ):
                    found_relationships.append(expected)

            # Check for unique agent_id values
            if len(agent_ids) != len(span_map):
                errors.append(
                    f"Duplicate agent_id values detected. "
                    f"Found {len(agent_ids)} unique agent_ids for {len(span_map)} spans"
                )

            # Check for unique agent_name values
            if len(agent_names) != len(span_map):
                errors.append(
                    f"Duplicate agent_name values detected. "
                    f"Found {len(agent_names)} unique agent_names for {len(span_map)} spans"
                )

            # Check that all agents share the same conversation_id
            if len(conversation_ids) > 1:
                errors.append(
                    f"Multiple conversation_id values detected: {conversation_ids}. "
                    f"All agents should share the same conversation_id"
                )

            is_valid = len(errors) == 0

            return TraceHierarchyValidation(
                is_valid=is_valid,
                trace_id=trace_id,
                relationships=found_relationships,
                errors=errors,
            )

        except requests.exceptions.RequestException as e:
            errors.append(f"Failed to connect to OpenSearch: {str(e)}")
            return TraceHierarchyValidation(
                is_valid=False, trace_id=trace_id, relationships=[], errors=errors
            )
        except Exception as e:
            errors.append(f"Unexpected error validating trace hierarchy: {str(e)}")
            return TraceHierarchyValidation(
                is_valid=False, trace_id=trace_id, relationships=[], errors=errors
            )

    def execute(self, agent) -> ScenarioResult:
        """Execute multi-agent scenario.

        This scenario uses the pre-built agent hierarchy from the runner.
        The parent agent invokes its child agents, which were created with
        the same fault injection configuration as the parent.

        The agent hierarchy is built by the runner based on the config file,
        so all agents (parent and children) have fault injection applied.

        Args:
            agent: Root agent with child_agents already populated

        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        conversation_id = f"conv_multi_agent_{int(time.time())}"

        try:
            # Check if agent has children
            if not agent.child_agents:
                raise ValueError(
                    "Multi-agent scenario requires agent hierarchy with children. "
                    "Ensure config file has 'children' defined under 'agent'."
                )

            # Parent agent invokes itself first
            parent_result = agent.invoke(
                "Coordinate with child agents for weather information", conversation_id
            )

            # Parent invokes each child agent
            child_results = []
            for child_name, child_agent in agent.child_agents.items():
                # Invoke child agent with same conversation_id
                child_result = child_agent.invoke(
                    f"Get weather data (delegated from parent)", conversation_id
                )
                child_results.append(child_result)

            duration = time.time() - start_time

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_seconds=duration,
                conversation_id=conversation_id
            )
        except Exception as e:
            duration = time.time() - start_time
            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_seconds=duration,
                error_message=str(e),
                conversation_id=conversation_id
            )
