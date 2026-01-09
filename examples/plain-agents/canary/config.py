"""Configuration management for the canary system.

This module provides functionality to load and parse YAML configuration files
with environment variable substitution and validation.
"""

import os
import re
import yaml
from typing import Dict, Any, List, Optional
from canary.faults import FaultInjectionConfig, FaultProfile


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and parse YAML configuration file with environment variable substitution.
    
    This function:
    1. Reads the YAML configuration file
    2. Substitutes environment variables (${VAR_NAME} syntax)
    3. Validates required configuration fields
    4. Returns the parsed configuration dictionary
    
    Args:
        config_path: Path to the YAML configuration file
    
    Returns:
        Configuration dictionary with all values resolved
    
    Raises:
        FileNotFoundError: If configuration file doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
        ValueError: If required fields are missing or environment variables are undefined
    
    Example:
        >>> config = load_config("config_mock.yaml")
        >>> print(config["mode"])
        mock
    """
    # Check if file exists
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Load YAML file
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML syntax in {config_path}: {e}")
    
    # Substitute environment variables
    config = _substitute_env_vars(config)
    
    # Validate required fields
    _validate_config(config)
    
    return config


def _substitute_env_vars(config: Any) -> Any:
    """
    Recursively substitute environment variables in configuration.
    
    Replaces ${VAR_NAME} with the value of environment variable VAR_NAME.
    
    Args:
        config: Configuration value (can be dict, list, str, or other types)
    
    Returns:
        Configuration with environment variables substituted
    
    Raises:
        ValueError: If referenced environment variable is not defined
    """
    if isinstance(config, dict):
        return {key: _substitute_env_vars(value) for key, value in config.items()}
    elif isinstance(config, list):
        return [_substitute_env_vars(item) for item in config]
    elif isinstance(config, str):
        # Find all ${VAR_NAME} patterns
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, config)
        
        # Substitute each environment variable
        result = config
        for var_name in matches:
            if var_name not in os.environ:
                raise ValueError(
                    f"Environment variable '{var_name}' referenced in configuration "
                    f"but not defined. Please set {var_name} in your environment."
                )
            result = result.replace(f"${{{var_name}}}", os.environ[var_name])
        
        return result
    else:
        # Return other types unchanged (int, float, bool, None, etc.)
        return config


def _validate_config(config: Dict[str, Any]) -> None:
    """
    Validate that required configuration fields are present.
    
    Args:
        config: Configuration dictionary to validate
    
    Raises:
        ValueError: If required fields are missing or invalid
    """
    missing_fields: List[str] = []

    # Check top-level required fields
    if "mode" not in config:
        missing_fields.append("mode")
    elif config["mode"] not in ["mock", "real"]:
        raise ValueError(f"Invalid mode: {config['mode']}. Must be 'mock' or 'real'")

    if "agent" not in config:
        missing_fields.append("agent")
    else:
        # Validate agent section
        agent_config = config["agent"]
        if not isinstance(agent_config, dict):
            raise ValueError("'agent' must be a dictionary")

        # agent_id and agent_name are optional, will use defaults if not provided

    if "otlp" not in config:
        missing_fields.append("otlp")
    else:
        # Validate otlp section
        otlp_config = config["otlp"]
        if not isinstance(otlp_config, dict):
            raise ValueError("'otlp' must be a dictionary")

        if "endpoint" not in otlp_config:
            missing_fields.append("otlp.endpoint")

    if "scenarios" not in config:
        missing_fields.append("scenarios")
    else:
        # Validate scenarios is a list
        if not isinstance(config["scenarios"], list):
            raise ValueError("'scenarios' must be a list")

        if len(config["scenarios"]) == 0:
            raise ValueError("'scenarios' list cannot be empty")

    # validation section is optional
    if "validation" in config:
        validation_config = config["validation"]
        if not isinstance(validation_config, dict):
            raise ValueError("'validation' must be a dictionary")

    # Report all missing fields at once
    if missing_fields:
        raise ValueError(
            f"Missing required configuration fields: {', '.join(missing_fields)}"
        )

    # Validate mode-specific settings
    mode = config["mode"]

    if mode == "mock" and "mock_settings" in config:
        mock_settings = config["mock_settings"]
        if not isinstance(mock_settings, dict):
            raise ValueError("'mock_settings' must be a dictionary")

        # Validate failure rate if present
        if "tool_failure_rate" in mock_settings:
            failure_rate = mock_settings["tool_failure_rate"]
            if not isinstance(failure_rate, (int, float)):
                raise ValueError("'tool_failure_rate' must be a number")
            if not 0.0 <= failure_rate <= 1.0:
                raise ValueError(
                    f"'tool_failure_rate' must be between 0.0 and 1.0, got {failure_rate}"
                )

    if mode == "real" and "real_settings" in config:
        real_settings = config["real_settings"]
        if not isinstance(real_settings, dict):
            raise ValueError("'real_settings' must be a dictionary")


def parse_fault_injection_config(
    config: Dict[str, Any],
) -> Optional[FaultInjectionConfig]:
    """
    Parse fault injection configuration from YAML config.

    This function extracts the fault_injection section from the configuration
    and creates a FaultInjectionConfig object with all enabled profiles and
    their parameters.

    Args:
        config: Full configuration dictionary

    Returns:
        FaultInjectionConfig object if fault injection is configured, None otherwise

    Raises:
        ValueError: If fault injection configuration is invalid

    Example:
        >>> config = load_config("config_fault.yaml")
        >>> fault_config = parse_fault_injection_config(config)
        >>> if fault_config and fault_config.enabled:
        ...     print(f"Fault injection enabled with {len(fault_config.profiles)} profiles")
    """
    # Check if fault_injection section exists
    if "fault_injection" not in config:
        return None

    fault_config = config["fault_injection"]

    # Validate fault_injection is a dictionary
    if not isinstance(fault_config, dict):
        raise ValueError("'fault_injection' must be a dictionary")

    # Get enabled flag (default to False if not specified)
    enabled = fault_config.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("'fault_injection.enabled' must be a boolean")

    # If not enabled, return disabled config
    if not enabled:
        return FaultInjectionConfig(enabled=False, profiles=[])

    # Get profiles list
    profile_names = fault_config.get("profiles", [])
    if not isinstance(profile_names, list):
        raise ValueError("'fault_injection.profiles' must be a list")

    # Parse each profile
    profiles: List[FaultProfile] = []

    for profile_name in profile_names:
        if not isinstance(profile_name, str):
            raise ValueError(f"Profile name must be a string, got {type(profile_name)}")

        # Get profile configuration
        if profile_name not in fault_config:
            raise ValueError(
                f"Profile '{profile_name}' listed in profiles but not defined in configuration"
            )

        profile_params = fault_config[profile_name]
        if not isinstance(profile_params, dict):
            raise ValueError(f"Profile '{profile_name}' must be a dictionary")

        # Validate profile-specific parameters
        _validate_profile_parameters(profile_name, profile_params)

        profiles.append(FaultProfile(name=profile_name, parameters=profile_params))

    return FaultInjectionConfig(enabled=True, profiles=profiles)


def _validate_profile_parameters(profile_name: str, parameters: Dict[str, Any]) -> None:
    """
    Validate parameters for a specific fault profile.

    Args:
        profile_name: Name of the profile being validated
        parameters: Profile parameters dictionary

    Raises:
        ValueError: If parameters are invalid for the profile type
    """
    if profile_name == "high_latency":
        # Validate latency parameters
        if "llm_latency_ms" in parameters:
            latency = parameters["llm_latency_ms"]
            if not isinstance(latency, (int, float)) or latency < 0:
                raise ValueError(
                    f"'high_latency.llm_latency_ms' must be a non-negative number, got {latency}"
                )

        if "tool_latency_ms" in parameters:
            latency = parameters["tool_latency_ms"]
            if not isinstance(latency, (int, float)) or latency < 0:
                raise ValueError(
                    f"'high_latency.tool_latency_ms' must be a non-negative number, got {latency}"
                )

    elif profile_name == "intermittent_failures":
        # Validate failure rate parameters
        if "llm_failure_rate" in parameters:
            rate = parameters["llm_failure_rate"]
            if not isinstance(rate, (int, float)) or not 0.0 <= rate <= 1.0:
                raise ValueError(
                    f"'intermittent_failures.llm_failure_rate' must be between 0.0 and 1.0, got {rate}"
                )

        if "tool_failure_rate" in parameters:
            rate = parameters["tool_failure_rate"]
            if not isinstance(rate, (int, float)) or not 0.0 <= rate <= 1.0:
                raise ValueError(
                    f"'intermittent_failures.tool_failure_rate' must be between 0.0 and 1.0, got {rate}"
                )

        if "failure_pattern" in parameters:
            pattern = parameters["failure_pattern"]
            valid_patterns = ["random", "periodic", "burst"]
            if pattern not in valid_patterns:
                raise ValueError(
                    f"'intermittent_failures.failure_pattern' must be one of {valid_patterns}, got '{pattern}'"
                )

    elif profile_name == "rate_limits":
        # Validate rate limit parameters
        if "trigger_after_calls" in parameters:
            trigger = parameters["trigger_after_calls"]
            if not isinstance(trigger, int) or trigger < 1:
                raise ValueError(
                    f"'rate_limits.trigger_after_calls' must be a positive integer, got {trigger}"
                )

    elif profile_name == "token_limits":
        # Validate token limit parameters
        if "max_tokens" in parameters:
            max_tokens = parameters["max_tokens"]
            if not isinstance(max_tokens, int) or max_tokens < 1:
                raise ValueError(
                    f"'token_limits.max_tokens' must be a positive integer, got {max_tokens}"
                )

        if "exceed_by" in parameters:
            exceed_by = parameters["exceed_by"]
            if not isinstance(exceed_by, int) or exceed_by < 0:
                raise ValueError(
                    f"'token_limits.exceed_by' must be a non-negative integer, got {exceed_by}"
                )

    elif profile_name == "partial_responses":
        # Validate completeness ratio
        if "completeness_ratio" in parameters:
            ratio = parameters["completeness_ratio"]
            if not isinstance(ratio, (int, float)) or not 0.0 <= ratio <= 1.0:
                raise ValueError(
                    f"'partial_responses.completeness_ratio' must be between 0.0 and 1.0, got {ratio}"
                )

    # Unknown profile names are allowed - they might be custom profiles
    # Just validate that parameters is a dictionary (already done above)
