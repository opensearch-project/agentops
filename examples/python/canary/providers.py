"""
Provider protocols and implementations for the canary system.

This module defines the LLMProvider and ToolProvider protocols that enable
pluggable mock and real implementations using the Strategy Pattern.
"""

import time
import json
import random
from typing import Protocol, Dict, Any, Optional

from .faults import RateLimitError, TokenLimitError


class LLMProvider(Protocol):
    """Protocol defining the interface for LLM providers.
    
    This protocol enables the Strategy Pattern, allowing the ConfigurableAgent
    to work with any LLM implementation (mock or real) without knowing the
    specific implementation details.
    """
    
    @property
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'mock', 'openai').
        
        Returns:
            str: The name of the provider implementation
        """
        ...
    
    def call(
        self,
        model: str,
        messages: list[Dict[str, str]],
        tools: Optional[list[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Call the LLM with messages and optional tools.
        
        Args:
            model: The model identifier (e.g., 'gpt-4')
            messages: List of message dictionaries with 'role' and 'content' keys
            tools: Optional list of tool definitions in OpenAI format
        
        Returns:
            Response dictionary with structure:
            {
                "id": str,
                "model": str,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": str (for text responses)
                            OR
                            "tool_calls": [...] (for tool call responses)
                        },
                        "finish_reason": str
                    }
                ],
                "usage": {
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int
                }
            }
        """
        ...


class ToolProvider(Protocol):
    """Protocol defining the interface for tool providers.
    
    This protocol enables the Strategy Pattern, allowing the ConfigurableAgent
    to work with any tool implementation (mock or real) without knowing the
    specific implementation details.
    """
    
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with given arguments.
        
        Args:
            tool_name: Name of the tool to execute (e.g., 'get_weather', 'search')
            arguments: Tool arguments dictionary
        
        Returns:
            Tool execution result dictionary. The structure depends on the tool.
        
        Raises:
            ValueError: If tool_name is unknown
            Exception: If tool execution fails
        """
        ...


class MockLLMProvider:
    """Mock LLM provider that generates deterministic responses.

    This provider is used for frequent canary runs without API costs.
    It simulates LLM behavior with configurable latency and deterministic
    token calculation. Supports fault injection for testing resilience.
    """

    def __init__(
        self,
        latency_ms: int = 500,
        failure_rate: float = 0.0,
        failure_pattern: str = "random",
        rate_limit_after: Optional[int] = None,
        max_tokens: Optional[int] = None,
        completeness_ratio: float = 1.0,
    ):
        """Initialize mock LLM provider.

        Args:
            latency_ms: Simulated latency in milliseconds (default: 500ms)
            failure_rate: Probability of call failure (0.0 to 1.0, default: 0.0)
            failure_pattern: Pattern of failures - "random", "periodic", or "burst" (default: "random")
            rate_limit_after: Raise RateLimitError after this many calls (default: None, disabled)
            max_tokens: Maximum allowed tokens, raise TokenLimitError if exceeded (default: None, disabled)
            completeness_ratio: Ratio of complete response to return (0.0 to 1.0, default: 1.0)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError(
                f"failure_rate must be between 0.0 and 1.0, got {failure_rate}"
            )
        if failure_pattern not in ["random", "periodic", "burst"]:
            raise ValueError(
                f"failure_pattern must be 'random', 'periodic', or 'burst', got {failure_pattern}"
            )
        if not 0.0 <= completeness_ratio <= 1.0:
            raise ValueError(
                f"completeness_ratio must be between 0.0 and 1.0, got {completeness_ratio}"
            )
        if rate_limit_after is not None and rate_limit_after < 0:
            raise ValueError(
                f"rate_limit_after must be non-negative, got {rate_limit_after}"
            )
        if max_tokens is not None and max_tokens < 0:
            raise ValueError(f"max_tokens must be non-negative, got {max_tokens}")

        self._latency_ms = latency_ms
        self._failure_rate = failure_rate
        self._failure_pattern = failure_pattern
        self._rate_limit_after = rate_limit_after
        self._max_tokens = max_tokens
        self._completeness_ratio = completeness_ratio

        # Track call count for rate limiting and periodic failures
        self._call_count = 0

        # Track burst state for burst failure pattern
        self._burst_state = {"in_burst": False, "burst_remaining": 0}

        # Random number generator for failure simulation
        self._random = random.Random(42)  # Fixed seed for determinism

    def _should_fail(self) -> bool:
        """Determine if this call should fail based on failure pattern.

        Implements three failure patterns:
        - random: Each call has independent probability of failure
        - periodic: Fails every Nth call (N = 1/failure_rate)
        - burst: Clusters of failures followed by success periods

        Returns:
            True if the call should fail, False otherwise
        """
        if self._failure_rate == 0.0:
            return False

        if self._failure_pattern == "random":
            # Random failure with configured probability
            return self._random.random() < self._failure_rate

        elif self._failure_pattern == "periodic":
            # Fail every Nth call where N = 1/failure_rate
            # For example, failure_rate=0.2 means fail every 5th call
            if self._failure_rate >= 1.0:
                return True
            period = int(1.0 / self._failure_rate)
            return (self._call_count % period) == 0

        elif self._failure_pattern == "burst":
            # Burst pattern: clusters of failures
            # When entering burst, fail for multiple consecutive calls
            if self._burst_state["in_burst"]:
                self._burst_state["burst_remaining"] -= 1
                if self._burst_state["burst_remaining"] <= 0:
                    self._burst_state["in_burst"] = False
                return True
            else:
                # Check if we should enter a burst
                if self._random.random() < self._failure_rate:
                    # Start a burst of 3-5 failures
                    self._burst_state["in_burst"] = True
                    self._burst_state["burst_remaining"] = self._random.randint(
                        2, 4
                    )  # 2-4 more after this one
                    return True
                return False

        return False

    @property
    def provider_name(self) -> str:
        """Return the provider name.
        
        Returns:
            str: Always returns 'mock'
        """
        return "mock"

    def call(
        self,
        model: str,
        messages: list[Dict[str, str]],
        tools: Optional[list[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate deterministic mock response with token calculation.

        Simulates LLM behavior by:
        1. Checking rate limits and raising RateLimitError if exceeded
        2. Checking if call should fail based on failure pattern
        3. Calculating tokens based on input text (characters / 4)
        4. Checking token limits and raising TokenLimitError if exceeded
        5. Generating deterministic responses based on message content
        6. Applying partial response truncation if configured
        7. Simulating latency to mimic real API calls
        8. Supporting both text and tool call responses

        Args:
            model: The model identifier (e.g., 'gpt-4')
            messages: List of message dictionaries with 'role' and 'content' keys
            tools: Optional list of tool definitions in OpenAI format

        Returns:
            Response dictionary matching OpenAI API format with usage statistics

        Raises:
            RateLimitError: If rate_limit_after is set and call count exceeds it
            TokenLimitError: If max_tokens is set and total tokens exceed it
            Exception: If failure pattern determines this call should fail
        """
        # Increment call count for rate limiting and periodic failures
        self._call_count += 1

        # Check rate limit
        if (
            self._rate_limit_after is not None
            and self._call_count > self._rate_limit_after
        ):
            raise RateLimitError(
                f"Rate limit exceeded after {self._rate_limit_after} calls"
            )

        # Check if this call should fail based on failure pattern
        if self._should_fail():
            raise Exception(
                f"Mock LLM failure (pattern: {self._failure_pattern}, call: {self._call_count})"
            )

        # Simulate latency
        time.sleep(self._latency_ms / 1000.0)

        # Calculate tokens (rough approximation: 1 token ≈ 4 characters)
        # Ensure we always return at least 1 token for non-empty messages
        prompt_text = " ".join(msg["content"] for msg in messages)
        prompt_tokens = max(1, len(prompt_text) // 4)

        # Generate deterministic response based on last message
        last_message = messages[-1]["content"].lower()

        # Determine if tool call is needed
        if tools and ("weather" in last_message or "temperature" in last_message):
            # Generate tool call response
            completion_tokens = 25
            total_tokens = prompt_tokens + completion_tokens

            # Check token limit
            if self._max_tokens is not None and total_tokens > self._max_tokens:
                raise TokenLimitError(total_tokens, self._max_tokens)

            response = {
                "id": f"mock-{hash(prompt_text) % 1000000}",
                "model": model,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_mock_001",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": json.dumps({"location": "Paris"}),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
            }
        else:
            # Generate text response
            response_text = "This is a mock response for testing purposes."

            # Apply partial response truncation if configured
            if self._completeness_ratio < 1.0:
                truncate_at = int(len(response_text) * self._completeness_ratio)
                response_text = response_text[:truncate_at]

            # Ensure we always return at least 1 token for non-empty responses
            completion_tokens = max(1, len(response_text) // 4)
            total_tokens = prompt_tokens + completion_tokens

            # Check token limit
            if self._max_tokens is not None and total_tokens > self._max_tokens:
                raise TokenLimitError(total_tokens, self._max_tokens)

            response = {
                "id": f"mock-{hash(prompt_text) % 1000000}",
                "model": model,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
            }

        return response


class MockToolProvider:
    """Mock tool provider with configurable failure rate and fault injection.

    This provider is used for testing error handling and resilience.
    It simulates tool execution with configurable failure rates, latency,
    and supports fault injection for testing resilience.
    """

    def __init__(
        self,
        failure_rate: float = 0.0,
        latency_ms: int = 200,
        failure_pattern: str = "random",
        completeness_ratio: float = 1.0,
    ):
        """Initialize mock tool provider.

        Args:
            failure_rate: Probability of tool failure (0.0 to 1.0)
            latency_ms: Simulated latency in milliseconds (default: 200ms)
            failure_pattern: Pattern of failures - "random", "periodic", or "burst" (default: "random")
            completeness_ratio: Ratio of complete response to return (0.0 to 1.0, default: 1.0)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError(
                f"failure_rate must be between 0.0 and 1.0, got {failure_rate}"
            )
        if failure_pattern not in ["random", "periodic", "burst"]:
            raise ValueError(
                f"failure_pattern must be 'random', 'periodic', or 'burst', got {failure_pattern}"
            )
        if not 0.0 <= completeness_ratio <= 1.0:
            raise ValueError(
                f"completeness_ratio must be between 0.0 and 1.0, got {completeness_ratio}"
            )

        self._failure_rate = failure_rate
        self._latency_ms = latency_ms
        self._failure_pattern = failure_pattern
        self._completeness_ratio = completeness_ratio

        # Track call count for periodic failures
        self._call_count = 0

        # Track burst state for burst failure pattern
        self._burst_state = {"in_burst": False, "burst_remaining": 0}

        # Random number generator for failure simulation
        self._random = random.Random(42)  # Fixed seed for determinism

    def _should_fail(self) -> bool:
        """Determine if this call should fail based on failure pattern.

        Implements three failure patterns:
        - random: Each call has independent probability of failure
        - periodic: Fails every Nth call (N = 1/failure_rate)
        - burst: Clusters of failures followed by success periods

        Returns:
            True if the call should fail, False otherwise
        """
        if self._failure_rate == 0.0:
            return False

        if self._failure_pattern == "random":
            # Random failure with configured probability
            return self._random.random() < self._failure_rate

        elif self._failure_pattern == "periodic":
            # Fail every Nth call where N = 1/failure_rate
            # For example, failure_rate=0.2 means fail every 5th call
            if self._failure_rate >= 1.0:
                return True
            period = int(1.0 / self._failure_rate)
            return (self._call_count % period) == 0

        elif self._failure_pattern == "burst":
            # Burst pattern: clusters of failures
            # When entering burst, fail for multiple consecutive calls
            if self._burst_state["in_burst"]:
                self._burst_state["burst_remaining"] -= 1
                if self._burst_state["burst_remaining"] <= 0:
                    self._burst_state["in_burst"] = False
                return True
            else:
                # Check if we should enter a burst
                if self._random.random() < self._failure_rate:
                    # Start a burst of 3-5 failures
                    self._burst_state["in_burst"] = True
                    self._burst_state["burst_remaining"] = self._random.randint(
                        2, 4
                    )  # 2-4 more after this one
                    return True
                return False

        return False

    def _truncate_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate string fields in result based on completeness_ratio.

        Args:
            result: Tool result dictionary

        Returns:
            Result dictionary with truncated string values
        """
        if self._completeness_ratio >= 1.0:
            return result

        truncated = {}
        for key, value in result.items():
            if isinstance(value, str):
                # Truncate string values
                truncate_at = int(len(value) * self._completeness_ratio)
                truncated[key] = value[:truncate_at]
            elif isinstance(value, dict):
                # Recursively truncate nested dictionaries
                truncated[key] = self._truncate_response(value)
            elif isinstance(value, list):
                # Truncate list items if they are strings or dicts
                truncated[key] = [
                    (
                        item[: int(len(item) * self._completeness_ratio)]
                        if isinstance(item, str)
                        else (
                            self._truncate_response(item)
                            if isinstance(item, dict)
                            else item
                        )
                    )
                    for item in value
                ]
            else:
                # Keep non-string values as-is
                truncated[key] = value

        return truncated

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mock tool with optional failure and partial responses.

        Simulates tool execution by:
        1. Incrementing call count for failure pattern tracking
        2. Applying configured latency
        3. Checking if call should fail based on failure pattern
        4. Returning deterministic results for known tools
        5. Applying partial response truncation if configured

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments dictionary

        Returns:
            Tool execution result dictionary (possibly truncated)

        Raises:
            ValueError: If tool_name is unknown
            Exception: If tool execution fails (based on failure pattern)
        """
        # Increment call count for failure pattern tracking
        self._call_count += 1

        # Simulate latency
        time.sleep(self._latency_ms / 1000.0)

        # Check if this call should fail based on failure pattern
        if self._should_fail():
            raise Exception(
                f"Mock tool failure (pattern: {self._failure_pattern}, call: {self._call_count}): {tool_name}"
            )

        # Return deterministic mock results
        if tool_name == "get_weather":
            location = arguments.get("location", "Unknown")
            result = {
                "location": location,
                "temperature": "72°F",
                "condition": "sunny",
                "humidity": "45%",
                "wind_speed": "8 mph",
            }
        elif tool_name == "search":
            query = arguments.get("query", "")
            result = {
                "results": [
                    {"title": f"Result 1 for {query}", "url": "https://example.com/1"},
                    {"title": f"Result 2 for {query}", "url": "https://example.com/2"},
                ]
            }
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Apply partial response truncation if configured
        return self._truncate_response(result)


class RealToolProvider:
    """Real tool provider with actual implementations.

    This provider is used for end-to-end validation with real tool execution.
    For now, it uses realistic mock data for the get_weather tool, but the
    structure is designed to be easily extended with actual API calls.
    """

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute real tool implementation.

        This method executes actual tool implementations. Currently implements
        get_weather with realistic mock data that can be replaced with actual
        API calls in the future.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments dictionary

        Returns:
            Tool execution result dictionary

        Raises:
            ValueError: If tool_name is unknown
            Exception: If tool execution fails
        """
        try:
            if tool_name == "get_weather":
                return self._get_weather(arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        except ValueError:
            # Re-raise ValueError for unknown tools
            raise
        except Exception as e:
            # Wrap other exceptions with context
            raise Exception(
                f"Tool execution failed for {tool_name}: {str(e)}"
            ) from e

    def _get_weather(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather for a location.

        Currently returns realistic mock data. This can be replaced with
        actual weather API calls (e.g., OpenWeatherMap, WeatherAPI) in
        the future.

        Args:
            arguments: Dictionary containing 'location' key

        Returns:
            Weather data dictionary with location, temperature, condition,
            humidity, and wind_speed

        Raises:
            ValueError: If location is missing from arguments
        """
        location = arguments.get("location")

        if not location:
            raise ValueError("Missing required argument: location")

        # TODO: Replace with actual weather API call
        # Example:
        # response = requests.get(
        #     f"https://api.weatherapi.com/v1/current.json",
        #     params={"key": API_KEY, "q": location}
        # )
        # return response.json()

        # For now, return realistic mock data
        return {
            "location": location,
            "temperature": "68°F",
            "condition": "partly cloudy",
            "humidity": "60%",
            "wind_speed": "10 mph"
        }


class RealLLMProvider:
    """Real LLM provider for actual API integration.

    This provider is used for end-to-end validation with real LLM API calls.
    For now, it delegates to MockLLMProvider as a placeholder until actual
    API integration is implemented.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """Initialize real LLM provider.

        Args:
            api_key: API key for LLM service (e.g., OpenAI API key)
            model: Model identifier to use (default: 'gpt-4')
        """
        self._api_key = api_key
        self._model = model

        # TODO: Initialize actual LLM client here
        # Example for OpenAI:
        # from openai import OpenAI
        # self._client = OpenAI(api_key=api_key)

        # For now, use MockLLMProvider as placeholder
        self._mock_provider = MockLLMProvider(latency_ms=500)

    @property
    def provider_name(self) -> str:
        """Return the provider name.

        Returns:
            str: Returns 'openai' (or other provider name in the future)
        """
        # TODO: Return actual provider name when implemented
        return "openai"

    def call(
        self,
        model: str,
        messages: list[Dict[str, str]],
        tools: Optional[list[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Call the LLM with messages and optional tools.

        This method will make actual API calls to an LLM service.
        For now, it delegates to MockLLMProvider as a placeholder.

        Args:
            model: The model identifier (e.g., 'gpt-4')
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tool definitions in OpenAI format

        Returns:
            Response dictionary matching OpenAI API format with usage stats

        Raises:
            Exception: If API call fails
        """
        # TODO: Implement actual LLM API call
        # Example for OpenAI:
        # try:
        #     response = self._client.chat.completions.create(
        #         model=model,
        #         messages=messages,
        #         tools=tools
        #     )
        #     return response.model_dump()
        # except Exception as e:
        #     raise Exception(f"LLM API call failed: {str(e)}") from e

        # For now, delegate to mock provider
        return self._mock_provider.call(model, messages, tools)
