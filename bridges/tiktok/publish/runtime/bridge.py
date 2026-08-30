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
        # `video` (the gallery upload, the only thing this bridge could do) or `text`. TikTok's
        # creation screen also offers PHOTO and LIVE; neither is wired yet.
        self.post_type = (config.get("postType") or "video").strip().lower()
        self.text = config.get("text", "")
        self.to_story = bool(config.get("toStory", False))
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
            # `device` here is the raw uiautomator2 Device (not the DeviceFacade), so use its
            # native methods: screenshot(filename) saves a PNG, dump_hierarchy() returns the XML.
            device.screenshot(str(png))
            dump = device.dump_hierarchy()
            if dump:
                xml.write_text(dump, encoding="utf-8")
            send_log("info", f"[artifact] {phase}: {png}")
        except Exception as e:
            send_log("warning", f"Artifact capture ({phase}) failed: {e}")

    def _run_text_post(self, device) -> int:
        """The TEXT format: no file, no gallery, no upload -- just the composer.

        Kept in this bridge rather than given one of its own: it is the same domain, the same
        device session and the same result message. What differs is the road on the screen.
        """
        send_status("running", "Publishing a TikTok text post...")
        try:
            from taktik.core.social_media.tiktok.services.publish.text_post import publish_text_post

            self._capture_phase(device, "00_before")
            result = publish_text_post(
                device, self.device_id, self.text, to_story=self.to_story,
            )
            self._capture_phase(device, "99_after")

            success = bool(result.get("success"))
            message = result.get("error") or f"text post published to {result.get('destination')}"
            send_status("success" if success else "error", message)
            send_message(
                "upload_result",
                success=success,
                workflow="text_post",
                message=message,
                # The step it stopped at, so a failure says WHERE rather than only that it failed.
                error_type=None if success else result.get("step"),
            )
            return 0 if success else 1
        except Exception as exc:
            import traceback

            send_error(f"Text post failed: {exc}")
            send_log("error", traceback.format_exc())
            return 1

    def run(self) -> int:
        if not self.device_id:
            send_error("deviceId is required")
            return 1
        if self.post_type == "video" and not self.local_path:
            send_error("localPath is required")
            return 1
        if self.post_type == "text" and not (self.text or "").strip():
            send_error("text is required for a text post")
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

        if self.post_type == "text":
            return self._run_text_post(device)

        send_status("running", "Starting TikTok upload workflow...")
        try:
            from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import TikTokUploadWorkflow

            # Inject a per-step capture hook so each publish stage gets a screenshot + dump.
            workflow = TikTokUploadWorkflow(
                device, self.device_id, notifier=_ipc,
                step_hook=lambda phase: self._capture_phase(device, phase),
            )
            self._capture_phase(device, "00_before")
            result = workflow.execute(
                local_path=self.local_path,
                caption=self.caption,
                hashtags=self.hashtags,
                package_name=self.package_name,
            )
            self._capture_phase(device, "99_after")

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
