"""
Canary traffic system for ATLAS observability validation.

This package provides synthetic and real agent traffic generation
to continuously validate the observability pipeline.
"""

from .providers import (
    LLMProvider,
    ToolProvider,
    MockLLMProvider,
    MockToolProvider,
    RealToolProvider,
    RealLLMProvider,
)
from .agent import ConfigurableAgent
from .factory import AgentFactory
from .scenarios import (
    ScenarioResult,
    CanaryScenario,
    SimpleToolCallScenario,
    MultiToolChainScenario,
    ToolFailureScenario,
    HighTokenUsageScenario,
    ConversationContextScenario,
    MultiAgentScenario,
)
from .validator import TelemetryValidator
from .runner import CanaryRunner
from .faults import (
    FaultProfile,
    FaultInjectionConfig,
    RateLimitError,
    TokenLimitError,
)
from .config import (
    load_config,
    parse_fault_injection_config,
)

__all__ = [
    "LLMProvider",
    "ToolProvider",
    "MockLLMProvider",
    "MockToolProvider",
    "RealToolProvider",
    "RealLLMProvider",
    "ConfigurableAgent",
    "AgentFactory",
    "ScenarioResult",
    "CanaryScenario",
    "SimpleToolCallScenario",
    "MultiToolChainScenario",
    "ToolFailureScenario",
    "HighTokenUsageScenario",
    "ConversationContextScenario",
    "MultiAgentScenario",
    "TelemetryValidator",
    "CanaryRunner",
    "FaultProfile",
    "FaultInjectionConfig",
    "RateLimitError",
    "TokenLimitError",
    "load_config",
    "parse_fault_injection_config",
]
