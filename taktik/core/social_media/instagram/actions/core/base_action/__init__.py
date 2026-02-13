"""
Instagram BaseAction facade — composes all base action mixins.

Sub-modules:
- delays.py          — Délais humanisés (gaussian, fatigue, action-type)
- scroll.py          — Scroll IG-specific avec variance naturelle
- typing.py          — Saisie texte humaine + Taktik Keyboard
- app_management.py  — Gestion app Instagram (open, check, debug, back)
"""

import time
import random
import os
import re
import math
import base64
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union
from loguru import logger

from taktik.core.shared.actions.base_action import SharedBaseAction
from ..device.facade import DeviceFacade
from ..utils import ActionUtils
from ....utils.input.keyboard import run_adb_shell, TAKTIK_KEYBOARD_IME, IME_MESSAGE_B64, IME_CLEAR_TEXT
from ..behavior import HumanBehavior

from .delays import DelaysMixin
from .scroll import ScrollMixin
from .typing import TypingMixin
from .app_management import AppManagementMixin


class BaseAction(
    DelaysMixin,
    ScrollMixin,
    TypingMixin,
    AppManagementMixin,
    SharedBaseAction
):
    """Instagram-specific base action.
    
    Inherits common element interaction methods from SharedBaseAction:
    - _find_and_click, _wait_for_element, _is_element_present
    - _get_text_from_element, _get_element_attribute
    - _get_device_serial, _clear_text_with_taktik_keyboard
    - get_method_stats, reset_stats
    - _extract_number_from_text, _clean_username, _is_valid_username
    
    Overrides/adds Instagram-specific behavior:
    - HumanBehavior singleton (fatigue, gaussian delays, break management)
    - Extended action types for _human_like_delay
    - Human-like scroll with random offsets
    - Taktik Keyboard with send_keys fallback
    - Instagram app management
    """
    
    _device_facade_class = DeviceFacade
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module=f"instagram.actions.{self.__class__.__name__.lower()}")
        self.utils = ActionUtils()
        self.human = HumanBehavior()  # Singleton partagé
        
        # Store keyboard constants for typing mixin
        self._run_adb_shell = run_adb_shell
        self._TAKTIK_KEYBOARD_IME = TAKTIK_KEYBOARD_IME
        self._IME_MESSAGE_B64 = IME_MESSAGE_B64


__all__ = ['BaseAction']
