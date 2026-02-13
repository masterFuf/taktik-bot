"""Atomic actions for TikTok - Low level UI interactions.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

Aggregate classes (backward-compatible):
    ClickActions      — VideoActions + PopupActions + profile/nav clicks
    NavigationActions  — SearchActions + bottom-nav/header/go_back
    DetectionActions   — VideoDetector + PopupDetector + page/error/app state

Granular classes (for targeted imports):
    VideoActions, PopupActions, SearchActions,
    VideoDetector, PopupDetector
"""

from .click_actions import ClickActions
from .navigation_actions import NavigationActions
from .scroll_actions import ScrollActions
from .detection_actions import DetectionActions
from .dm_actions import DMActions

from .video_actions import VideoActions
from .popup_actions import PopupActions
from .search_actions import SearchActions
from .video_detector import VideoDetector
from .popup_detector import PopupDetector

__all__ = [
    # Aggregate (backward-compat)
    'ClickActions',
    'NavigationActions',
    'ScrollActions',
    'DetectionActions',
    'DMActions',
    # Granular
    'VideoActions',
    'PopupActions',
    'SearchActions',
    'VideoDetector',
    'PopupDetector',
]
