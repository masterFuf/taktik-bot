"""Centralized IPC event emitter for Instagram workflows.

All bridge communication goes through here — single try/except,
single import, single place to maintain.
"""

from typing import Optional, Dict, Any
from loguru import logger

log = logger.bind(module="instagram-ipc-emitter")

# Lazy-loaded bridge module reference (None = not yet attempted)
_bridge_module = None
_bridge_load_attempted = False


def _get_bridge():
    """Lazy-load the bridge module. Returns None if not available (CLI mode)."""
    global _bridge_module, _bridge_load_attempted
    if _bridge_load_attempted:
        return _bridge_module
    _bridge_load_attempted = True
    try:
        import bridges.instagram.desktop_bridge as bridge
        _bridge_module = bridge
        log.debug("IPC bridge loaded successfully")
    except ImportError:
        _bridge_module = None
        log.debug("IPC bridge not available (CLI mode)")
    except Exception as e:
        _bridge_module = None
        log.debug(f"IPC bridge load error: {e}")
    return _bridge_module


class IPCEmitter:
    """Centralized IPC event emission for Instagram actions.
    
    Usage:
        IPCEmitter.emit_follow("username", profile_data={...})
        IPCEmitter.emit_like("username", count=3)
        IPCEmitter.emit_profile_visit("username")
        IPCEmitter.emit_action("story_watch", "username", {"count": 2})
    """

    @staticmethod
    def emit_follow(username: str, success: bool = True, profile_data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a follow event to the frontend WorkflowAnalyzer."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, 'send_follow_event'):
                bridge.send_follow_event(username, success=success, profile_data=profile_data)
        except Exception as e:
            log.debug(f"IPC follow event error: {e}")

    @staticmethod
    def emit_like(username: str, likes_count: int = 1, profile_data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a like event to the frontend WorkflowAnalyzer."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, 'send_like_event'):
                bridge.send_like_event(username, likes_count=likes_count, profile_data=profile_data)
        except Exception as e:
            log.debug(f"IPC like event error: {e}")

    @staticmethod
    def emit_profile_visit(username: str) -> None:
        """Emit a profile visit event to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, 'send_instagram_profile_visit'):
                bridge.send_instagram_profile_visit(username)
        except Exception as e:
            log.debug(f"IPC profile visit error: {e}")

    @staticmethod
    def emit_profile_captured(username: str, profile_data: Optional[Dict[str, Any]] = None, profile_pic_base64: Optional[str] = None) -> None:
        """Emit a profile_captured event with optional base64 profile image."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, 'send_profile_captured'):
                bridge.send_profile_captured(username, profile_data=profile_data, profile_pic_base64=profile_pic_base64)
        except Exception as e:
            log.debug(f"IPC profile_captured event error: {e}")

    @staticmethod
    def emit_action(action_type: str, username: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a generic action event to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, 'send_instagram_action'):
                bridge.send_instagram_action(action_type, username, data or {})
        except Exception as e:
            log.debug(f"IPC action event error: {e}")
