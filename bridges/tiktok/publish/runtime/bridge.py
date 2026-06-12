"""TikTok publish bridge runtime class."""

from __future__ import annotations

import signal
from datetime import datetime, timezone
from pathlib import Path

from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.tiktok.runtime.ipc import _ipc, send_error, send_log, send_message, send_status


class TikTokPublishBridge:
    """Bridge for TikTok post upload."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.local_path = config.get("localPath", "")
        self.caption = config.get("caption", "")
        self.hashtags = config.get("hashtags", [])
        self.package_name = config.get("packageName")
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
            device.screenshot(str(png))
            dump = device.get_xml_dump()
            if dump:
                xml.write_text(dump, encoding="utf-8")
            send_log("info", f"[artifact] {phase}: {png}")
        except Exception as e:
            send_log("warning", f"Artifact capture ({phase}) failed: {e}")

    def run(self) -> int:
        if not self.device_id:
            send_error("deviceId is required")
            return 1
        if not self.local_path:
            send_error("localPath is required")
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

        if self.package_name and self.package_name != "com.zhiliaoapp.musically":
            try:
                from taktik.core.clone import patch_selectors_for_package, set_active_package

                set_active_package(self.package_name)
                patched = patch_selectors_for_package("tiktok", self.package_name)
                send_log("info", f"ðŸ§¬ Package override: patched {patched} selector(s) for {self.package_name}")
            except Exception as e:
                send_log("warning", f"âš ï¸ Clone selector patching failed (non-fatal): {e}")

        send_status("running", "Starting TikTok upload workflow...")
        try:
            from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import TikTokUploadWorkflow

            workflow = TikTokUploadWorkflow(device, self.device_id, notifier=_ipc)
            self._capture_phase(device, "before")
            result = workflow.execute(
                local_path=self.local_path,
                caption=self.caption,
                hashtags=self.hashtags,
                package_name=self.package_name,
            )
            self._capture_phase(device, "after")

            success = result.get("success", False)
            send_status("success" if success else "error", result.get("message", ""))
            send_message(
                "upload_result",
                success=success,
                workflow="upload_post",
                message=result.get("message", ""),
                error_type=result.get("error_type"),
            )
            return 0 if success else 1

        except Exception as e:
            import traceback

            send_error(f"Upload workflow error: {e}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["TikTokPublishBridge"]
