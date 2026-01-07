"""
Canary scenario base class and data models.

This module provides the base class for canary scenarios and the result
data model for scenario execution.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ScenarioResult:
    """Result of a canary scenario execution."""

    scenario_name: str
    success: bool
    duration_seconds: float
    error_message: Optional[str] = None
    conversation_id: Optional[str] = None

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
            "conversation_id": self.conversation_id
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

    def execute(self, agent) -> ScenarioResult:
        """Execute multi-agent scenario.

        This scenario creates a parent-child agent relationship to test
        that span hierarchy is correctly preserved through the telemetry
        pipeline. The parent agent's span should contain the child agent's
        span as a nested child.

        Args:
            agent: Configurable agent to use as parent agent

        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        conversation_id = f"conv_multi_agent_{int(time.time())}"

        try:
            # Import here to avoid circular dependency
            from .factory import AgentFactory
            from .providers import MockLLMProvider, MockToolProvider

            # Parent agent is the one passed in
            parent_agent = agent

            # Create child agent (separate instance, same process)
            # Child agent initializes its own OTel exporters
            factory = AgentFactory(otlp_endpoint=parent_agent.otlp_endpoint)
            child_agent = factory.create_mock_agent(
                agent_id="child_agent_001",
                agent_name="Child Agent",
                llm_latency_ms=100,
                tool_latency_ms=50,
                tool_failure_rate=0.0
            )

            # Parent agent invokes child agent within its span context
            with parent_agent.tracer.start_as_current_span(
                "parent_agent_operation"
            ):
                # This creates a parent span
                parent_result = parent_agent.invoke(
                    "Coordinate with child agent",
                    conversation_id
                )

                # Child invocation happens within parent span context
                # This creates a child span nested under the parent
                child_result = child_agent.invoke(
                    "Execute subtask",
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
