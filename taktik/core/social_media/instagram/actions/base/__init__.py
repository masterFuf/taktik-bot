"""
Core layer of the Instagram actions.

Sub-packages:
- device/        — Abstraction device (facade IG-specific + manager shim)
- behavior/      — Simulation comportement humain (fatigue, pauses, gaussian delays)
- base_action/   — Infrastructure actions IG (delays, scroll, typing, app mgmt)
- base_business/ — Logique métier commune (popups, config, interactions, likers, stats)
- stats/         — Statistiques temps réel
"""

from taktik.core.social_media.instagram.actions.base.base_action import BaseAction
from taktik.core.social_media.instagram.actions.base.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.base.device import DeviceFacade, DeviceManager
from taktik.core.social_media.instagram.actions.base.utils import ActionUtils

__all__ = [
    'BaseAction',
    'BaseBusinessAction',
    'DeviceFacade',
    'DeviceManager',
    'ActionUtils'
]
