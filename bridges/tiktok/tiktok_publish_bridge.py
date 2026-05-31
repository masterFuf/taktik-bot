#!/usr/bin/env python3
"""
TikTok Publish Bridge
=====================
Publie un fichier média (vidéo ou image) sur TikTok.

Config JSON fields:
  {
    "workflowType": "upload_post",
    "deviceId": "...",
    "localPath": "/absolute/path/to/file.mp4",
    "caption": "Mon texte",
    "hashtags": ["fyp", "viral"],
    "packageName": null          // optionnel, auto-détecté si absent
  }
"""

import sys
import os
import json
import signal

# Bootstrap
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.tiktok.base import logger, _ipc, send_message, send_status, send_error, send_log
from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.signal_handler import setup_signal_handlers


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

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        send_status("stopping", "Received shutdown signal")

    def run(self) -> int:
        if not self.device_id:
            send_error("deviceId is required")
            return 1
        if not self.local_path:
            send_error("localPath is required")
            return 1

        # Connect to device
        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return 1

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return 1

        # Package override patching (trill vs musically)
        if self.package_name and self.package_name != "com.zhiliaoapp.musically":
            try:
                from taktik.core.clone import set_active_package, patch_selectors_for_package
                set_active_package(self.package_name)
                patched = patch_selectors_for_package("tiktok", self.package_name)
                send_log("info", f"🧬 Package override: patched {patched} selector(s) for {self.package_name}")
            except Exception as e:
                send_log("warning", f"⚠️ Clone selector patching failed (non-fatal): {e}")

        # Run the upload workflow
        send_status("running", "Starting TikTok upload workflow...")
        try:
            from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import TikTokUploadWorkflow
            workflow = TikTokUploadWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.execute(
                local_path=self.local_path,
                caption=self.caption,
                hashtags=self.hashtags,
                package_name=self.package_name,
            )

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


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: tiktok_publish_bridge.py <config.json>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to read config: {e}"}))
        sys.exit(1)

    bridge = TikTokPublishBridge(config)
    sys.exit(bridge.run())


if __name__ == "__main__":
    main()
