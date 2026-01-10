"""Atomic actions for TikTok - Low level UI interactions.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from .click_actions import ClickActions
from .navigation_actions import NavigationActions
from .scroll_actions import ScrollActions
from .detection_actions import DetectionActions
from .dm_actions import DMActions

__all__ = [
    'ClickActions',
    'NavigationActions',
    'ScrollActions',
    'DetectionActions',
    'DMActions',
]
