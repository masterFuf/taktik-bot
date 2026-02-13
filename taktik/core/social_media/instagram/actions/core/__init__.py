"""
Couche core pour les actions Instagram.

Sub-packages:
- device/        — Abstraction device (facade IG-specific + manager shim)
- behavior/      — Simulation comportement humain (fatigue, pauses, gaussian delays)
- base_action/   — Infrastructure actions IG (delays, scroll, typing, app mgmt)
- base_business/ — Logique métier commune (popups, config, interactions, likers, stats)
- stats/         — Statistiques temps réel
"""

from .base_action import BaseAction
from .base_business import BaseBusinessAction
from .device import DeviceFacade, DeviceManager
from .utils import ActionUtils

__all__ = [
    'BaseAction',
    'BaseBusinessAction',
    'DeviceFacade',
    'DeviceManager',
    'ActionUtils'
]
