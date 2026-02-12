"""TikTok automation module.

This module provides a complete automation framework for TikTok,
with a structure similar to the Instagram module for consistency.

Main components:
- TikTokManager: Main manager class
- Actions: Atomic and business actions
- Workflows: Automation workflows (ForYouWorkflow, etc.)
- UI: Selectors and detectors
- Models: Data models
- Utils: Utility functions

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from .core.manager import TikTokManager
from .actions import (
    ClickActions,
    NavigationActions,
    ScrollActions,
    DetectionActions,
    ForYouWorkflow,
    ForYouConfig,
    ForYouStats,
)
from .ui import (
    TIKTOK_PACKAGE,
    VIDEO_SELECTORS,
    NAVIGATION_SELECTORS,
    PROFILE_SELECTORS,
    INBOX_SELECTORS,
)

__all__ = [
    'TikTokManager',
    # Actions
    'ClickActions',
    'NavigationActions',
    'ScrollActions',
    'DetectionActions',
    # Workflows
    'ForYouWorkflow',
    'ForYouConfig',
    'ForYouStats',
    # Selectors
    'TIKTOK_PACKAGE',
    'VIDEO_SELECTORS',
    'NAVIGATION_SELECTORS',
    'PROFILE_SELECTORS',
    'INBOX_SELECTORS',
]

__version__ = '1.0.0'