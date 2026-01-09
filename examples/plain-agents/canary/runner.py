"""
Canary Runner for orchestrating scenario execution.

This module provides the CanaryRunner class that loads configuration,
creates agents, executes scenarios, and generates summary reports.
"""

import time
from typing import Dict, Any, List

from .config import load_config, parse_fault_injection_config
from .factory import AgentFactory
from .scenarios import (
    ScenarioResult,
    SimpleToolCallScenario,
    MultiToolChainScenario,
    ToolFailureScenario,
    HighTokenUsageScenario,
    ConversationContextScenario,
    MultiAgentScenario,
)
from .validator import TelemetryValidator


class CanaryRunner:
    """
    Orchestrates canary scenario execution.
    
    The CanaryRunner is a script-based orchestrator that:
    1. Loads configuration from YAML file
    2. Creates agent using AgentFactory based on config mode
    3. Executes scenarios sequentially in configured order
    4. Collects ScenarioResult for each scenario
    5. Optionally validates telemetry
    6. Generates summary report
    7. Exits with appropriate status code
    
    The runner does NOT initialize OpenTelemetry - agents do that themselves.
    This is a one-shot execution script, not a long-running service.
    """

    def __init__(self, config_path: str):
        """
        Initialize canary runner.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.results: List[ScenarioResult] = []
        self.fault_config = None  # Fault injection configuration

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Configuration dictionary
        
        Raises:
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If YAML syntax is invalid
            ValueError: If required fields are missing
        """
        self.config = load_config(self.config_path)

        # Parse fault injection configuration
        self.fault_config = parse_fault_injection_config(self.config)

        return self.config

    def _create_agent_hierarchy(
        self, factory: AgentFactory, agent_config: Dict[str, Any], mode: str
    ):
        """
        Recursively create agent hierarchy with fault injection.

        This method builds the entire agent tree, applying fault injection
        configuration to all agents in the hierarchy.

        Args:
            factory: AgentFactory instance
            agent_config: Agent configuration dictionary (may contain children)
            mode: Mode (mock or real)

        Returns:
            ConfigurableAgent with child_agents populated
        """
        from opentelemetry import trace

        # Build config for this agent
        config = {
            "mode": mode,
            "agent_id": agent_config.get("agent_id", "canary_001"),
            "agent_name": agent_config.get("agent_name", "Canary Agent"),
        }

        # Add mode-specific settings
        if mode == "mock" and "mock_settings" in self.config:
            config.update(self.config["mock_settings"])
        elif mode == "real" and "real_settings" in self.config:
            config.update(self.config["real_settings"])

        # Recursively create child agents
        child_agents = {}
        if "children" in agent_config:
            for child_config in agent_config["children"]:
                child_agent = self._create_agent_hierarchy(factory, child_config, mode)
                # Use agent_name as key for child_agents dict
                child_name = child_config.get("agent_name", "Child Agent")
                child_agents[child_name] = child_agent

        # Create this agent with fault injection
        agent = factory.create_from_config(config, self.fault_config)

        # Set span_kind if specified in config
        if "span_kind" in agent_config:
            span_kind_str = agent_config["span_kind"]
            if span_kind_str == "INTERNAL":
                agent.span_kind = trace.SpanKind.INTERNAL
            elif span_kind_str == "CLIENT":
                agent.span_kind = trace.SpanKind.CLIENT
            elif span_kind_str == "SERVER":
                agent.span_kind = trace.SpanKind.SERVER
            elif span_kind_str == "PRODUCER":
                agent.span_kind = trace.SpanKind.PRODUCER
            elif span_kind_str == "CONSUMER":
                agent.span_kind = trace.SpanKind.CONSUMER

        # Attach child agents
        agent.child_agents = child_agents

        return agent

    def _count_agents(self, agent) -> int:
        """
        Count total agents in hierarchy.

        Args:
            agent: Root agent

        Returns:
            Total number of agents (including root)
        """
        count = 1  # Count this agent
        for child in agent.child_agents.values():
            count += self._count_agents(child)
        return count

    def run(self) -> int:
        """
        Run the canary system.

        This method orchestrates the entire canary execution:
        1. Load configuration
        2. Create agent hierarchy using AgentFactory
        3. Execute scenarios sequentially
        4. Optionally validate telemetry
        5. Generate summary report
        6. Return exit code

        Returns:
            Exit code (0 if all scenarios pass, 1 if any fail)
        """
        # Load configuration
        print(f"Loading configuration from {self.config_path}...")
        try:
            self.load_config()
            print(f"✓ Configuration loaded successfully")
            print(f"  Mode: {self.config['mode']}")
            print(f"  Agent: {self.config['agent'].get('agent_name', 'Unknown')}")
            print(f"  Scenarios: {len(self.config['scenarios'])}")
        except Exception as e:
            print(f"✗ Failed to load configuration: {e}")
            return 1

        # Create agent hierarchy using AgentFactory
        print("\nCreating agent hierarchy...")
        try:
            factory = AgentFactory(
                otlp_endpoint=self.config['otlp']['endpoint']
            )

            # Build agent hierarchy recursively
            agent = self._create_agent_hierarchy(
                factory, self.config["agent"], self.config["mode"]
            )

            print(f"✓ Agent hierarchy created successfully")
            print(f"  Root Agent ID: {agent.agent_id}")
            print(f"  Root Agent Name: {agent.agent_name}")
            print(f"  OTLP Endpoint: {agent.otlp_endpoint}")

            # Count total agents in hierarchy
            total_agents = self._count_agents(agent)
            print(f"  Total Agents: {total_agents}")

            # Print fault injection status if enabled
            if self.fault_config and self.fault_config.enabled:
                print(f"  Fault Injection: ENABLED")
                print(
                    f"  Active Profiles: {', '.join([p.name for p in self.fault_config.profiles])}"
                )
            else:
                print(f"  Fault Injection: DISABLED")
        except Exception as e:
            print(f"✗ Failed to create agent hierarchy: {e}")
            return 1

        # Execute scenarios
        print("\nExecuting scenarios...")
        self.results = self._execute_scenarios(agent)

        # Generate summary report
        print("\n" + "=" * 60)
        exit_code = self._generate_summary()
        print("=" * 60)

        # Optionally validate telemetry
        if "validation" in self.config and self.results:
            print("\nValidating telemetry...")
            self._validate_telemetry()

        return exit_code

    def _execute_scenarios(self, agent) -> List[ScenarioResult]:
        """
        Execute scenarios sequentially in configured order.
        
        Args:
            agent: Configurable agent to use for scenarios
        
        Returns:
            List of ScenarioResult for each executed scenario
        """
        results = []

        # Map scenario names to scenario classes
        scenario_map = {
            "simple_tool_call": SimpleToolCallScenario,
            "multi_tool_chain": MultiToolChainScenario,
            "tool_failure": ToolFailureScenario,
            "high_token_usage": HighTokenUsageScenario,
            "conversation_context": ConversationContextScenario,
            "multi_agent": MultiAgentScenario,
        }

        # Execute each configured scenario
        for scenario_name in self.config["scenarios"]:
            if scenario_name not in scenario_map:
                print(f"  ⚠ Unknown scenario: {scenario_name} (skipping)")
                continue

            # Create scenario instance
            scenario_class = scenario_map[scenario_name]
            scenario = scenario_class()

            # Execute scenario
            print(f"\n  Running: {scenario.name}")
            print(f"  Description: {scenario.description}")

            try:
                result = scenario.execute(agent)

                # Add fault injection information to result
                if self.fault_config and self.fault_config.enabled:
                    result.fault_injection_enabled = True
                    result.active_fault_profiles = [
                        p.name for p in self.fault_config.profiles
                    ]

                results.append(result)

                # Print result
                if result.success:
                    print(f"  ✓ PASS ({result.duration_seconds:.2f}s)")
                else:
                    print(f"  ✗ FAIL ({result.duration_seconds:.2f}s)")
                    if result.error_message:
                        print(f"    Error: {result.error_message}")
            except Exception as e:
                # Catch any unexpected errors during scenario execution
                print(f"  ✗ FAIL (unexpected error)")
                print(f"    Error: {e}")

                # Create failed result
                result = ScenarioResult(
                    scenario_name=scenario.name,
                    success=False,
                    duration_seconds=0.0,
                    error_message=str(e),
                    fault_injection_enabled=(
                        self.fault_config.enabled if self.fault_config else False
                    ),
                    active_fault_profiles=(
                        [p.name for p in self.fault_config.profiles]
                        if self.fault_config and self.fault_config.enabled
                        else None
                    ),
                )
                results.append(result)

        return results

    def _generate_summary(self) -> int:
        """
        Generate summary report with success count, failure count, and duration.
        
        Returns:
            Exit code (0 if all scenarios pass, 1 if any fail)
        """
        print("\nCANARY SUMMARY REPORT")
        print("-" * 60)

        # Count successes and failures
        success_count = sum(1 for r in self.results if r.success)
        failure_count = sum(1 for r in self.results if not r.success)
        total_count = len(self.results)

        # Calculate total duration
        total_duration = sum(r.duration_seconds for r in self.results)

        # Print summary
        print(f"Total Scenarios:  {total_count}")
        print(f"Passed:           {success_count}")
        print(f"Failed:           {failure_count}")
        print(f"Total Duration:   {total_duration:.2f}s")

        # Print fault injection status
        if self.fault_config and self.fault_config.enabled:
            print(f"\nFault Injection:  ENABLED")
            print(
                f"Active Profiles:  {', '.join([p.name for p in self.fault_config.profiles])}"
            )

            # Show which scenarios ran with fault injection
            scenarios_with_faults = [
                r.scenario_name for r in self.results if r.fault_injection_enabled
            ]
            if scenarios_with_faults:
                print(
                    f"Scenarios with Faults: {len(scenarios_with_faults)}/{total_count}"
                )
        else:
            print(f"\nFault Injection:  DISABLED")

        # Print failed scenarios
        if failure_count > 0:
            print("\nFailed Scenarios:")
            for result in self.results:
                if not result.success:
                    print(f"  - {result.scenario_name}")
                    if result.error_message:
                        print(f"    {result.error_message}")
                    # Indicate if failure occurred with fault injection
                    if result.fault_injection_enabled:
                        print(
                            f"    (Fault injection was active: {', '.join(result.active_fault_profiles or [])})"
                        )

        # Determine exit code
        exit_code = 0 if failure_count == 0 else 1

        # Print final status
        print()
        if exit_code == 0:
            print("✓ All scenarios passed")
        else:
            print("✗ Some scenarios failed")

        return exit_code

    def _validate_telemetry(self) -> None:
        """
        Validate telemetry data in Prometheus and OpenSearch.
        
        This is an optional step that queries the observability stack
        to verify that telemetry data was correctly stored.
        
        Note: Adds a small delay to allow telemetry to be ingested.
        """
        validation_config = self.config.get("validation", {})

        if not validation_config or not validation_config.get("enabled", True):
            return

        # Wait a bit for telemetry to be ingested
        import time
        print("\n  Waiting for telemetry ingestion...")
        time.sleep(15)

        try:
            validator = TelemetryValidator(
                prometheus_url=validation_config.get("prometheus_url", ""),
                opensearch_url=validation_config.get("opensearch_url", ""),
                opensearch_user=validation_config.get("opensearch_user", "admin"),
                opensearch_password=validation_config.get("opensearch_password", "")
            )

            # Get agent name from config
            agent_name = self.config.get("agent", {}).get("agent_name", "")

            # Validate telemetry for each successful scenario
            for result in self.results:
                if result.success and result.conversation_id:
                    print(f"\n  Validating: {result.scenario_name}")

                    # Validate metrics
                    metric_errors = validator.validate_metrics(result.conversation_id, agent_name)
                    if metric_errors:
                        print(f"    ⚠ Metric validation errors:")
                        for error in metric_errors:
                            print(f"      - {error}")
                    else:
                        print(f"    ✓ Metrics validated")

                    # Validate traces
                    trace_errors = validator.validate_traces(result.conversation_id)
                    if trace_errors:
                        print(f"    ⚠ Trace validation errors:")
                        for error in trace_errors:
                            print(f"      - {error}")
                    else:
                        print(f"    ✓ Traces validated")

        except Exception as e:
            print(f"  ⚠ Telemetry validation failed: {e}")
