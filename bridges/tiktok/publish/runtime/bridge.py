"""TikTok publish bridge runtime class.

The publication is `run_tiktok_publish` (core), the launcher the Agent handler
`tiktok.standalone.upload_post` (and so the CLI) calls too: read the request, patch the selectors
of a cloned TikTok, upload the video or write the text post. This bridge opens its own connection
and injects what is specific to the desktop: the stdout IPC and a screenshot plus a UI dump per
phase under `debug_ui`.
"""

from __future__ import annotations

import signal
from datetime import datetime, timezone
from pathlib import Path

from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.tiktok.runtime.ipc import _ipc, send_error, send_log, send_status


class TikTokPublishBridge:
    """Bridge for TikTok post upload."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self._connection = None
        self._artifact_dir = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        send_status("stopping", "Received shutdown signal")

    def _capture_phase(self, device, phase: str) -> None:
        """Save a before/after screenshot + UI XML dump so a publish run can be reviewed
        from disk, like the Cartography Lab action-test artifacts. Best-effort, never fatal."""
        try:
            if self._artifact_dir is None:
                bot_root = Path(__file__).resolve().parents[4]
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                safe = "".join(c for c in (self.device_id or "device") if c.isalnum() or c in "._-")
                self._artifact_dir = bot_root / "debug_ui" / "cartography" / safe / "tiktok" / "publish-runs" / stamp
                self._artifact_dir.mkdir(parents=True, exist_ok=True)
            png = self._artifact_dir / f"{phase}.png"
            xml = self._artifact_dir / f"{phase}.xml"
            # `device` here is the raw uiautomator2 Device (not the DeviceFacade), so use its
            # native methods: screenshot(filename) saves a PNG, dump_hierarchy() returns the XML.
            device.screenshot(str(png))
            dump = device.dump_hierarchy()
            if dump:
                xml.write_text(dump, encoding="utf-8")
            send_log("info", f"[artifact] {phase}: {png}")
        except Exception as e:
            send_log("warning", f"Artifact capture ({phase}) failed: {e}")

    def run(self) -> int:
        from taktik.core.social_media.tiktok.workflows.publish.agent_handler import run_tiktok_publish
        from taktik.core.social_media.tiktok.workflows.publish.payload import (
            PublishRequestError,
            publish_request_from_payload,
        )

        if not self.device_id:
            send_error("deviceId is required")
            return 1
        try:
            # Read before connecting: nothing to publish means the phone is not touched.
            publish_request_from_payload(self.config)
        except PublishRequestError as e:
            send_error(str(e))
            return 1

        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return 1

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return 1

        result = run_tiktok_publish(
            self.config,
            device=device,
            device_id=self.device_id,
            notifier=_ipc,
            step_hook=lambda phase: self._capture_phase(device, phase),
        )
        return 0 if result.get("success") else 1


__all__ = ["TikTokPublishBridge"]
