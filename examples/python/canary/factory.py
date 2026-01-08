"""
Agent Factory for creating agents with appropriate providers.

This module provides the AgentFactory class that simplifies agent creation
by encapsulating provider selection logic. The factory enables configuration-
driven agent creation without requiring the canary runner to know about
specific provider implementations.
"""

from typing import Dict, Any, Optional

from .agent import ConfigurableAgent
from .providers import (
    MockLLMProvider,
    MockToolProvider,
    RealLLMProvider,
    RealToolProvider,
)
from .faults import FaultInjectionConfig


class AgentFactory:
    """Factory for creating agents with appropriate providers.

    The AgentFactory simplifies agent creation by encapsulating provider
    selection logic. Instead of the canary runner needing to know about
    MockLLMProvider, RealLLMProvider, etc., it just asks the factory for
    an agent based on configuration.

    Purpose:
    1. Simplifies canary runner code - runner doesn't need to know about
       provider classes
    2. Centralizes provider logic - one place to manage mock vs real
       provider creation
    3. Configuration-driven - easily switch modes via config file without
       code changes

    The factory passes the otlp_endpoint to agents, and agents initialize
    their own OpenTelemetry exporters.
    """

    def __init__(self, otlp_endpoint: str = "http://localhost:4317"):
        """Initialize agent factory.

        Args:
            otlp_endpoint: OTLP collector endpoint for agents to use.
                          This endpoint is passed to all created agents,
                          which then initialize their own OTel exporters.
        """
        self.otlp_endpoint = otlp_endpoint

    def create_mock_agent(
        self,
        agent_id: str = "canary_mock_001",
        agent_name: str = "Mock Canary Agent",
        llm_latency_ms: int = 500,
        tool_latency_ms: int = 200,
        tool_failure_rate: float = 0.0
    ) -> ConfigurableAgent:
        """Create agent with mock providers.

        This is useful for:
        - Frequent canary runs (no API costs)
        - Testing specific scenarios (configurable failure rates)
        - CI/CD validation (fast, deterministic)

        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            llm_latency_ms: Simulated LLM latency in milliseconds
            tool_latency_ms: Simulated tool latency in milliseconds
            tool_failure_rate: Probability of tool failure (0.0 to 1.0)

        Returns:
            ConfigurableAgent instance with mock providers
        """
        llm_provider = MockLLMProvider(latency_ms=llm_latency_ms)
        tool_provider = MockToolProvider(
            failure_rate=tool_failure_rate,
            latency_ms=tool_latency_ms
        )
        return ConfigurableAgent(
            llm_provider=llm_provider,
            tool_provider=tool_provider,
            agent_id=agent_id,
            agent_name=agent_name,
            otlp_endpoint=self.otlp_endpoint
        )

    def create_real_agent(
        self,
        agent_id: str = "canary_real_001",
        agent_name: str = "Real Canary Agent",
        api_key: str = None
    ) -> ConfigurableAgent:
        """Create agent with real providers.

        This is useful for:
        - End-to-end validation (actual API calls)
        - Periodic validation (hourly/daily)
        - Production-like testing

        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            api_key: API key for LLM service (e.g., OpenAI API key)

        Returns:
            ConfigurableAgent instance with real providers
        """
        llm_provider = RealLLMProvider(api_key=api_key)
        tool_provider = RealToolProvider()
        return ConfigurableAgent(
            llm_provider=llm_provider,
            tool_provider=tool_provider,
            agent_id=agent_id,
            agent_name=agent_name,
            otlp_endpoint=self.otlp_endpoint
        )

    def create_from_config(
        self,
        config: Dict[str, Any],
        fault_config: Optional[FaultInjectionConfig] = None,
    ) -> ConfigurableAgent:
        """Create agent from configuration with optional fault injection.

        This is the main method used by the canary runner.
        It reads the mode from config and delegates to the appropriate
        method. When fault_config is provided, it merges fault injection
        settings with base provider settings to enable composable fault
        testing.

        Example config:
        {
            "mode": "mock",
            "agent_id": "canary_001",
            "agent_name": "Test Agent",
            "llm_latency_ms": 500,
            "tool_latency_ms": 200,
            "tool_failure_rate": 0.1
        }

        Args:
            config: Configuration dictionary containing mode and agent
                settings
            fault_config: Optional fault injection configuration to apply

        Returns:
            ConfigurableAgent instance configured according to the config
            with fault injection applied if enabled

        Raises:
            ValueError: If mode is unknown or required fields are missing
        """
        mode = config.get("mode", "mock")

        if mode == "mock":
            # Start with base settings from config
            llm_latency = config.get("llm_latency_ms", 500)
            tool_latency = config.get("tool_latency_ms", 200)
            tool_failure_rate = config.get("tool_failure_rate", 0.0)

            # Initialize fault injection parameters with defaults
            llm_failure_rate = 0.0
            failure_pattern = "random"
            rate_limit_after = None
            max_tokens = None
            completeness_ratio = 1.0

            # Apply fault injection profiles if enabled
            if fault_config and fault_config.enabled:
                # High latency profile: adds latency to LLM and tool
                # providers
                if fault_config.is_profile_enabled("high_latency"):
                    llm_latency = fault_config.get_parameter(
                        "high_latency", "llm_latency_ms", llm_latency
                    )
                    tool_latency = fault_config.get_parameter(
                        "high_latency", "tool_latency_ms", tool_latency
                    )

                # Intermittent failures profile: adds failure rates and
                # patterns
                if fault_config.is_profile_enabled("intermittent_failures"):
                    llm_failure_rate = fault_config.get_parameter(
                        "intermittent_failures", "llm_failure_rate", 0.0
                    )
                    tool_failure_rate = fault_config.get_parameter(
                        "intermittent_failures",
                        "tool_failure_rate",
                        tool_failure_rate,
                    )
                    failure_pattern = fault_config.get_parameter(
                        "intermittent_failures", "failure_pattern", "random"
                    )

                # Rate limits profile: triggers rate limiting after N calls
                if fault_config.is_profile_enabled("rate_limits"):
                    rate_limit_after = fault_config.get_parameter(
                        "rate_limits", "trigger_after_calls", None
                    )

                # Token limits profile: enforces maximum token limits
                if fault_config.is_profile_enabled("token_limits"):
                    max_tokens = fault_config.get_parameter(
                        "token_limits", "max_tokens", None
                    )

                # Partial responses profile: returns incomplete responses
                if fault_config.is_profile_enabled("partial_responses"):
                    completeness_ratio = fault_config.get_parameter(
                        "partial_responses", "completeness_ratio", 1.0
                    )

            # Create providers with merged configuration
            llm_provider = MockLLMProvider(
                latency_ms=llm_latency,
                failure_rate=llm_failure_rate,
                failure_pattern=failure_pattern,
                rate_limit_after=rate_limit_after,
                max_tokens=max_tokens,
                completeness_ratio=completeness_ratio,
            )

            tool_provider = MockToolProvider(
                latency_ms=tool_latency,
                failure_rate=tool_failure_rate,
                failure_pattern=failure_pattern,
                completeness_ratio=completeness_ratio,
            )

            return ConfigurableAgent(
                llm_provider=llm_provider,
                tool_provider=tool_provider,
                agent_id=config.get("agent_id", "canary_mock_001"),
                agent_name=config.get("agent_name", "Mock Canary Agent"),
                otlp_endpoint=self.otlp_endpoint,
            )
        elif mode == "real":
            return self.create_real_agent(
                agent_id=config.get("agent_id", "canary_real_001"),
                agent_name=config.get("agent_name", "Real Canary Agent"),
                api_key=config.get("api_key")
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")
