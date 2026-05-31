"""Centralized IPC event emitter for Instagram workflows.

The launching bridge injects the adapter that owns stdout JSON emission.
Standalone/CLI runs simply keep this emitter as a no-op.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

log = logger.bind(module="instagram-ipc-emitter")

_bridge_adapter = None


def _get_bridge():
    """Return the injected bridge adapter, if one is available."""
    return _bridge_adapter


class IPCEmitter:
    """Centralized IPC event emission for Instagram actions."""

    @staticmethod
    def configure_bridge_adapter(adapter: Any) -> None:
        """Inject the bridge/base module used to emit stdout JSON events."""
        global _bridge_adapter
        _bridge_adapter = adapter

    @staticmethod
    def clear_bridge_adapter() -> None:
        """Clear the bridge adapter for tests or standalone runs."""
        global _bridge_adapter
        _bridge_adapter = None

    @staticmethod
    def emit_follow(username: str, success: bool = True, profile_data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a follow event to the frontend WorkflowAnalyzer."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_follow_event"):
                bridge.send_follow_event(username, success=success, profile_data=profile_data)
        except Exception as exc:
            log.debug(f"IPC follow event error: {exc}")

    @staticmethod
    def emit_like(username: str, likes_count: int = 1, profile_data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a like event to the frontend WorkflowAnalyzer."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_like_event"):
                bridge.send_like_event(username, likes_count=likes_count, profile_data=profile_data)
        except Exception as exc:
            log.debug(f"IPC like event error: {exc}")

    @staticmethod
    def emit_profile_visit(username: str) -> None:
        """Emit a profile visit event to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_instagram_profile_visit"):
                bridge.send_instagram_profile_visit(username)
        except Exception as exc:
            log.debug(f"IPC profile visit error: {exc}")

    @staticmethod
    def emit_profile_captured(
        username: str,
        profile_data: Optional[Dict[str, Any]] = None,
        profile_pic_base64: Optional[str] = None,
    ) -> None:
        """Emit a profile_captured event with optional base64 profile image."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_profile_captured"):
                bridge.send_profile_captured(
                    username,
                    profile_data=profile_data,
                    profile_pic_base64=profile_pic_base64,
                )
        except Exception as exc:
            log.debug(f"IPC profile_captured event error: {exc}")

    @staticmethod
    def emit_profile_skipped(username: str, reason: str = "already in DB") -> None:
        """Emit a profile_skipped event to the Taktik Agent panel."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_profile_skipped"):
                bridge.send_profile_skipped(username, reason=reason)
        except Exception as exc:
            log.debug(f"IPC profile_skipped event error: {exc}")

    @staticmethod
    def emit_action(action_type: str, username: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a generic action event to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_instagram_action"):
                bridge.send_instagram_action(action_type, username, data or {})
        except Exception as exc:
            log.debug(f"IPC action event error: {exc}")

    @staticmethod
    def emit_unfollow(username: str, success: bool = True) -> None:
        """Emit an unfollow event to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_unfollow_event"):
                bridge.send_unfollow_event(username, success=success)
        except Exception as exc:
            log.debug(f"IPC unfollow event error: {exc}")

    @staticmethod
    def emit_stats(
        likes: int = 0,
        follows: int = 0,
        comments: int = 0,
        profiles: int = 0,
        unfollows: int = 0,
    ) -> None:
        """Emit a legacy stats update to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_stats"):
                bridge.send_stats(
                    likes=likes,
                    follows=follows,
                    comments=comments,
                    profiles=profiles,
                    unfollows=unfollows,
                )
        except Exception as exc:
            log.debug(f"IPC stats event error: {exc}")

    @staticmethod
    def emit_current_post(
        author: str,
        likes_count: Optional[int] = None,
        comments_count: Optional[int] = None,
        caption: Optional[str] = None,
        hashtag: Optional[str] = None,
    ) -> None:
        """Emit current post metadata to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_current_post"):
                bridge.send_current_post(
                    author=author,
                    likes_count=likes_count,
                    comments_count=comments_count,
                    caption=caption,
                    hashtag=hashtag,
                )
        except Exception as exc:
            log.debug(f"IPC current_post event error: {exc}")

    @staticmethod
    def emit_post_skipped(author: str, reason: str = "already_processed", hashtag: Optional[str] = None) -> None:
        """Emit post skipped metadata to the frontend."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_post_skipped"):
                bridge.send_post_skipped(author=author, reason=reason, hashtag=hashtag)
        except Exception as exc:
            log.debug(f"IPC post_skipped event error: {exc}")

    @staticmethod
    def emit_scraping_profile_visit(username: str, profile_data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a profile-visit event during scraping."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_scraping_profile_visit"):
                bridge.send_scraping_profile_visit(username, profile_data=profile_data)
        except Exception as exc:
            log.debug(f"IPC scraping_profile_visit error: {exc}")

    @staticmethod
    def emit_scraping_dq_progress(username: str, count: int, max_count: int) -> None:
        """Emit live following-collection progress during deep qualify."""
        bridge = _get_bridge()
        if not bridge:
            return
        try:
            if hasattr(bridge, "send_scraping_dq_progress"):
                bridge.send_scraping_dq_progress(username, count, max_count)
        except Exception as exc:
            log.debug(f"IPC scraping_dq_progress error: {exc}")


__all__ = ["IPCEmitter"]
