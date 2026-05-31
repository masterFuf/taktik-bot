"""Media capture adapter for the Instagram desktop automation bridge runtime."""

from __future__ import annotations

from typing import Any, Dict

from bridges.instagram.runtime.ipc import send_log, send_message, send_status


class InstagramMediaCaptureRuntime:
    """Owns optional media capture lifecycle for desktop automation sessions."""

    def __init__(self, device_id: str | None, enabled: bool):
        self.device_id = device_id
        self.enabled = enabled
        self.service = None

    def start(self) -> bool:
        """Start media capture if enabled; failures are non-blocking."""
        if not self.enabled:
            send_log("info", "Media capture disabled in config")
            return True

        try:
            from taktik.core.social_media.instagram.media import MediaCaptureService

            send_status("initializing", "Starting media capture service...")

            def on_media_event(event_type: str, data: Dict[str, Any]):
                send_message(event_type, **data)

            self.service = MediaCaptureService(
                device_id=self.device_id,
                proxy_port=8888,
                desktop_bridge_callback=on_media_event,
            )
            self.service.on_profile_captured = self._on_profile
            self.service.on_media_captured = self._on_media

            if not self.service.start():
                send_log("warning", "Media capture service failed to start (continuing without it)")
                self.service = None
                return True

            send_status("media_capture_ready", "Media capture service started")
            return True

        except ImportError as e:
            send_log("warning", f"Media capture not available: {e}")
            return True
        except Exception as e:
            send_log("warning", f"Media capture failed: {e}")
            return True

    def stop(self) -> None:
        """Stop media capture if it was started."""
        if not self.service:
            return

        try:
            stats = self.service.get_stats()
            send_log(
                "info",
                f"Media capture stats: {stats['profiles_captured']} profiles, "
                f"{stats['media_captured']} media",
            )
            self.service.stop()
        except Exception as e:
            send_log("warning", f"Error stopping media capture: {e}")
        self.service = None

    @staticmethod
    def _on_profile(profile) -> None:
        send_log(
            "info",
            f"Captured profile: @{profile.username} ({profile.follower_count} followers)",
        )
        send_message(
            "profile_captured",
            username=profile.username,
            full_name=profile.full_name,
            profile_pic_url=profile.profile_pic_url,
            profile_pic_url_hd=profile.profile_pic_url_hd,
            follower_count=profile.follower_count,
            following_count=profile.following_count,
            media_count=profile.media_count,
            is_private=profile.is_private,
            is_verified=profile.is_verified,
            biography=profile.biography,
        )

    @staticmethod
    def _on_media(media) -> None:
        send_log("debug", f"Captured media: {media.media_id} ({media.like_count} likes)")
        send_message(
            "media_captured",
            media_id=media.media_id,
            media_type=media.media_type,
            image_url=media.image_url,
            like_count=media.like_count,
            comment_count=media.comment_count,
            caption=media.caption[:100] if media.caption else "",
            username=media.username,
        )
