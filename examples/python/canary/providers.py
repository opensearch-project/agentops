"""
Provider protocols and implementations for the canary system.

This module defines the LLMProvider and ToolProvider protocols that enable
pluggable mock and real implementations using the Strategy Pattern.
"""

import time
import json
import random
from typing import Protocol, Dict, Any, Optional


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
    token calculation.
    """
    
    def __init__(self, latency_ms: int = 500):
        """Initialize mock LLM provider.
        
        Args:
            latency_ms: Simulated latency in milliseconds (default: 500ms)
        """
        self._latency_ms = latency_ms
    
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
        1. Calculating tokens based on input text (characters / 4)
        2. Generating deterministic responses based on message content
        3. Simulating latency to mimic real API calls
        4. Supporting both text and tool call responses
        
        Args:
            model: The model identifier (e.g., 'gpt-4')
            messages: List of message dictionaries with 'role' and 'content' keys
            tools: Optional list of tool definitions in OpenAI format
        
        Returns:
            Response dictionary matching OpenAI API format with usage statistics
        """
        # Simulate latency
        time.sleep(self._latency_ms / 1000.0)
        
        # Calculate tokens (rough approximation: 1 token ≈ 4 characters)
        prompt_text = " ".join(msg["content"] for msg in messages)
        prompt_tokens = len(prompt_text) // 4
        
        # Generate deterministic response based on last message
        last_message = messages[-1]["content"].lower()
        
        # Determine if tool call is needed
        if tools and ("weather" in last_message or "temperature" in last_message):
            # Generate tool call response
            completion_tokens = 25
            response = {
                "id": f"mock-{hash(prompt_text) % 1000000}",
                "model": model,
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_mock_001",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": json.dumps({"location": "Paris"})
                            }
                        }]
                    },
                    "finish_reason": "tool_calls"
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            }
        else:
            # Generate text response
            response_text = "This is a mock response for testing purposes."
            completion_tokens = len(response_text) // 4
            response = {
                "id": f"mock-{hash(prompt_text) % 1000000}",
                "model": model,
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            }
        
        return response


class MockToolProvider:
    """Mock tool provider with configurable failure rate.
    
    This provider is used for testing error handling and resilience.
    It simulates tool execution with configurable failure rates and latency.
    """
    
    def __init__(self, failure_rate: float = 0.0, latency_ms: int = 200):
        """Initialize mock tool provider.
        
        Args:
            failure_rate: Probability of tool failure (0.0 to 1.0)
            latency_ms: Simulated latency in milliseconds (default: 200ms)
        
        Raises:
            ValueError: If failure_rate is outside [0.0, 1.0] range
        """
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError(f"failure_rate must be between 0.0 and 1.0, got {failure_rate}")
        
        self._failure_rate = failure_rate
        self._latency_ms = latency_ms
        self._random = random.Random(42)  # Fixed seed for determinism
    
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mock tool with optional failure.
        
        Simulates tool execution by:
        1. Applying configured latency
        2. Randomly failing based on failure_rate
        3. Returning deterministic results for known tools
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments dictionary
        
        Returns:
            Tool execution result dictionary
        
        Raises:
            ValueError: If tool_name is unknown
            Exception: If tool execution fails (based on failure_rate)
        """
        # Simulate latency
        time.sleep(self._latency_ms / 1000.0)
        
        # Randomly fail based on failure rate
        if self._random.random() < self._failure_rate:
            raise Exception(f"Mock tool failure: {tool_name}")
        
        # Return deterministic mock results
        if tool_name == "get_weather":
            location = arguments.get("location", "Unknown")
            return {
                "location": location,
                "temperature": "72°F",
                "condition": "sunny",
                "humidity": "45%",
                "wind_speed": "8 mph"
            }
        elif tool_name == "search":
            query = arguments.get("query", "")
            return {
                "results": [
                    {"title": f"Result 1 for {query}", "url": "https://example.com/1"},
                    {"title": f"Result 2 for {query}", "url": "https://example.com/2"}
                ]
            }
        else:
            raise ValueError(f"Unknown tool: {tool_name}")


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
