"""
Canary Runner for orchestrating scenario execution.

This module provides the CanaryRunner class that loads configuration,
creates agents, executes scenarios, and generates summary reports.
"""

import time
from typing import Dict, Any, List

from .config import load_config
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
        return self.config
    
    def run(self) -> int:
        """
        Run the canary system.
        
        This method orchestrates the entire canary execution:
        1. Load configuration
        2. Create agent using AgentFactory
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
        
        # Create agent using AgentFactory
        print("\nCreating agent...")
        try:
            factory = AgentFactory(
                otlp_endpoint=self.config['otlp']['endpoint']
            )
            
            # Merge agent config with mode-specific settings
            agent_config = {
                "mode": self.config["mode"],
                "agent_id": self.config["agent"].get("agent_id", "canary_001"),
                "agent_name": self.config["agent"].get("agent_name", "Canary Agent"),
            }
            
            # Add mode-specific settings
            if self.config["mode"] == "mock" and "mock_settings" in self.config:
                agent_config.update(self.config["mock_settings"])
            elif self.config["mode"] == "real" and "real_settings" in self.config:
                agent_config.update(self.config["real_settings"])
            
            agent = factory.create_from_config(agent_config)
            print(f"✓ Agent created successfully")
            print(f"  Agent ID: {agent.agent_id}")
            print(f"  Agent Name: {agent.agent_name}")
            print(f"  OTLP Endpoint: {agent.otlp_endpoint}")
        except Exception as e:
            print(f"✗ Failed to create agent: {e}")
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
                    error_message=str(e)
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
        
        # Print failed scenarios
        if failure_count > 0:
            print("\nFailed Scenarios:")
            for result in self.results:
                if not result.success:
                    print(f"  - {result.scenario_name}")
                    if result.error_message:
                        print(f"    {result.error_message}")
        
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
        
        if not validation_config:
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
