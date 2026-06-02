"""Shared behavior policy contracts.

This package only parses optional policy payloads. Runtime application belongs to
later lots and must stay opt-in so the Bot remains standalone-safe.
"""

from .policy import BehaviorPolicy, PausePolicy, ResumePolicy, parse_behavior_policy

__all__ = [
    "BehaviorPolicy",
    "PausePolicy",
    "ResumePolicy",
    "parse_behavior_policy",
]
