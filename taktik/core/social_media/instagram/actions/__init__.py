"""Compatibility module for Instagram automation actions.

This module now uses the new modular architecture with ModernInstagramActions.
"""
import warnings

from .core.base_action import BaseAction
from .compatibility.modern_instagram_actions import ModernInstagramActions


class InstagramActions:
    
    def __init__(self, device_manager, session_manager=None):
        warnings.warn(
            "InstagramActions is deprecated. Use ModernInstagramActions directly.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if hasattr(device_manager, 'device') and device_manager.device is not None:
            device = device_manager.device
        else:
            device = device_manager
        
        self._modern_actions = ModernInstagramActions(device, session_manager)
        
        self.device_manager = device_manager
        self.device = device
        
    def get_profile_info(self, username: str = None) -> dict:
        return self._modern_actions.get_profile_info(username)
        
    def navigate_to_profile(self, username: str) -> bool:
        return self._modern_actions.navigate_to_profile(username)
    
    def follow_user(self, username: str) -> bool:
        return self._modern_actions.follow_user(username)
    
    def like_post(self, *args, **kwargs):
        return self._modern_actions.like_post(*args, **kwargs)
    
    def get_followers_from_profile(self, username: str, max_followers: int = 100):
        return self._modern_actions.get_followers_from_profile(username, max_followers)
