"""Instagram publish bridge runtime class.

Scaffold of the Instagram publish bridge (see
`docs/instagram/publish-electron-to-bot-migration.md`). The bridge contract,
device connection and per-`postType` dispatch are in place; each flow body
(post / reel / carousel / story) is ported from the Electron services
incrementally and validated on device. Until a flow is ported, it returns a
clear terminal error and the Electron path remains the active publisher.
"""

from __future__ import annotations

import signal

from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.instagram.runtime.ipc import _ipc, send_error, send_log, send_status


SUPPORTED_POST_TYPES = ("post", "reel", "carousel", "story")


class InstagramPublishBridge:
    """Bridge for Instagram post/reel/carousel/story publishing."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        # Single or multi-media input (carousel uses several paths).
        self.media_paths = config.get("mediaPaths") or (
            [config["localPath"]] if config.get("localPath") else []
        )
        self.caption = config.get("caption", "")
        self.hashtags = config.get("hashtags", [])
        self.post_type = (config.get("postType") or "post").lower()
        self.package_name = config.get("packageName")
        self._connection = None
        self._stop_requested = False

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        self._stop_requested = True
        send_status("stopping", "Received shutdown signal")

    def run(self) -> int:
        if not self.device_id:
            send_error("deviceId is required")
            return 1
        if self.post_type not in SUPPORTED_POST_TYPES:
            send_error(f"Unsupported postType '{self.post_type}' (expected one of {SUPPORTED_POST_TYPES})")
            return 1
        if self.post_type != "story" and not self.media_paths:
            send_error("At least one media path is required (mediaPaths/localPath)")
            return 1

        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)

        try:
            dispatch = {
                "post": self._run_post,
                "reel": self._run_reel,
                "carousel": self._run_carousel,
                "story": self._run_story,
            }
            return dispatch[self.post_type]()
        finally:
            try:
                if self._connection is not None:
                    self._connection.disconnect()
            except Exception:
                pass

    # --- Flow owners (ported incrementally from the Electron publish services) ---

    def _run_post(self) -> int:
        return self._publish("post")

    def _run_reel(self) -> int:
        return self._publish("reel")

    def _run_carousel(self) -> int:
        return self._publish("carousel")

    def _run_story(self) -> int:
        return self._publish("story")

    def _publish(self, post_type: str) -> int:
        """Publish via the core Instagram publish workflow.

        Thin adapter: connect the device, delegate to InstagramPostWorkflow (which owns
        the selector flow and media push for post/reel/carousel/story), and translate
        its result into IPC events.
        """
        if not self._connection.connect():
            send_error("Failed to connect to device", "device_connection_failed")
            return 1

        from taktik.core.social_media.instagram.workflows.publish.post_workflow import (
            InstagramPostWorkflow,
        )

        workflow = InstagramPostWorkflow(
            self._connection.device,
            self.device_id,
            log=send_log,
            status=send_status,
            package_name=self.package_name,
            post_type=post_type,
        )
        result = workflow.execute(
            caption=self.caption,
            hashtags=self.hashtags,
            media_paths=self.media_paths,
        )
        if result.get("success"):
            send_status("completed", result.get("message", f"{post_type} published"))
            return 0
        send_error(result.get("message", "Publish failed"), result.get("error_type"))
        return 1
