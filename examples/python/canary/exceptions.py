"""
Custom exceptions for the canary system.

This module defines exceptions used throughout the agent-to-agent tracing
functionality.
"""

from typing import List


class ChildAgentNotFoundError(Exception):
    """Raised when a requested child agent is not found."""
    
    def __init__(self, child_name: str, available_children: List[str]):
        """
        Initialize the exception.
        
        Args:
            child_name: Name of the child agent that was requested
            available_children: List of available child agent names
        """
        self.child_name = child_name
        self.available_children = available_children
        super().__init__(
            f"Child agent '{child_name}' not found. "
            f"Available: {', '.join(available_children) if available_children else 'none'}"
        )


class CircularAgentReferenceError(Exception):
    """Raised when agent configuration contains circular references."""
    
    def __init__(self, cycle_path: List[str]):
        """
        Initialize the exception.
        
        Args:
            cycle_path: List of agent IDs forming the circular reference
        """
        self.cycle_path = cycle_path
        super().__init__(
            f"Circular agent reference detected: {' -> '.join(cycle_path)}"
        )
