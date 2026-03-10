"""Centralized state management for INFINIBAY projects.

Provides the canonical task state machine, dependency validation,
progress metrics, and project completion detection.
"""

from backend.state.completion import CompletionDetector, CompletionState
from backend.state.dependency_validator import DependencyValidator
from backend.state.machine import TaskStateMachine
from backend.state.progress import ProgressService

__all__ = [
    "TaskStateMachine",
    "DependencyValidator",
    "ProgressService",
    "CompletionDetector",
    "CompletionState",
]
