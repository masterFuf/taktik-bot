"""Compatibility layer for integrating new architecture with existing workflows."""

from .modern_instagram_actions import ModernInstagramActions
from .cli_adapter import InstagramCLIAdapter, create_cli_parser

__all__ = [
    'ModernInstagramActions',
    'InstagramCLIAdapter',
    'create_cli_parser'
]
