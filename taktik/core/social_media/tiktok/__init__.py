"""TikTok automation module.

This module provides a complete automation framework for TikTok,
with a structure similar to the Instagram module for consistency.

Main components:
- TikTokManager: Main manager class
- Actions: Atomic and business actions
- Workflows: Automation workflows
- UI: Selectors and detectors
- Models: Data models
- Utils: Utility functions
"""

from .manager import TikTokManager

__all__ = [
    'TikTokManager',
]

__version__ = '1.0.0'