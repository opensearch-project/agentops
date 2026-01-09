"""Fault injection configuration and exception classes for canary testing."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class FaultProfile:
    """Configuration for a single fault profile."""
    name: str
    parameters: Dict[str, Any]


@dataclass
class FaultInjectionConfig:
    """Complete fault injection configuration."""
    enabled: bool
    profiles: List[FaultProfile]
    
    def get_profile(self, name: str) -> Optional[FaultProfile]:
        """
        Get profile by name.
        
        Args:
            name: Name of the profile to retrieve
            
        Returns:
            FaultProfile if found, None otherwise
        """
        for profile in self.profiles:
            if profile.name == name:
                return profile
        return None
    
    def is_profile_enabled(self, name: str) -> bool:
        """
        Check if a profile is enabled.
        
        Args:
            name: Name of the profile to check
            
        Returns:
            True if profile exists in the enabled profiles list
        """
        return any(p.name == name for p in self.profiles)
    
    def get_parameter(self, profile_name: str, param_name: str, default: Any = None) -> Any:
        """
        Get parameter value from a profile.
        
        Args:
            profile_name: Name of the profile
            param_name: Name of the parameter
            default: Default value if parameter not found
            
        Returns:
            Parameter value if found, default otherwise
        """
        profile = self.get_profile(profile_name)
        if profile:
            return profile.parameters.get(param_name, default)
        return default


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded (HTTP 429)"):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message describing the rate limit
        """
        self.status_code = 429
        super().__init__(message)


class TokenLimitError(Exception):
    """Exception raised when token limit is exceeded."""
    
    def __init__(self, tokens_used: int, max_tokens: int):
        """
        Initialize token limit error.
        
        Args:
            tokens_used: Number of tokens used
            max_tokens: Maximum allowed tokens
        """
        self.tokens_used = tokens_used
        self.max_tokens = max_tokens
        super().__init__(
            f"Token limit exceeded: {tokens_used} tokens used, "
            f"maximum is {max_tokens}"
        )
