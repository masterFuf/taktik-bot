#!/usr/bin/env python3
"""
YouTube Upload Bridge
=====================
Bridge for publishing a video (Short or standard Video) on YouTube.

Config JSON:
  {
    "workflowType": "upload_post",
    "deviceId": "...",
    "localPath": "/absolute/path/to/file.mp4",
    "title": "My video title",
    "description": "Optional description",
    "uploadType": "short"        // "short" | "video" (default: "short")
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
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.youtube.base import logger, _ipc, send_message, send_status, send_error, send_log
from bridges.common.connection import ConnectionService
from bridges.common.signal_handler import setup_signal_handlers


class YouTubeUploadBridge:
    """Bridge for YouTube video upload (Shorts or standard)."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.local_path = config.get("localPath", "")
        self.title = config.get("title", "")
        self.description = config.get("description", "")
        self.upload_type = config.get("uploadType", "short").lower()  # "short" | "video"
        self.visibility = config.get("visibility", "public").lower()  # "public" | "unlisted" | "private"
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
        if not os.path.isfile(self.local_path):
            send_error(f"File not found: {self.local_path}")
            return 1

        # ── Connect ──────────────────────────────────────────────────────────
        send_status("connecting", f"Connecting to device {self.device_id}…")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return 1

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return 1

        # ── Setup DB ─────────────────────────────────────────────────────────
        try:
            from taktik.core.database import configure_db_service
            configure_db_service()
        except Exception as e:
            send_error(f"Database setup failed: {e}")
            return 1

        # ── Run workflow ─────────────────────────────────────────────────────
        send_status("running", "Starting YouTube upload workflow…")
        try:
            from taktik.core.social_media.youtube.workflows.publish.upload_workflow import (
                YouTubeUploadWorkflow,
                set_callbacks as _set_upload_callbacks,
            )

            # Inject IPC callbacks so the workflow can emit log/status events
            # without importing `bridges.common.ipc` directly.
            _set_upload_callbacks(log=send_log, status=send_status)

            workflow = YouTubeUploadWorkflow(device, self.device_id)
            result = workflow.execute(
                local_path=self.local_path,
                title=self.title,
                description=self.description,
                upload_type=self.upload_type,
                visibility=self.visibility,
            )

            success = result.get("success", False)
            send_status("success" if success else "error", result.get("message", ""))
            send_message(
                "upload_result",
                success=success,
                workflow="upload_post",
                upload_type=self.upload_type,
                message=result.get("message", ""),
                error_type=result.get("error_type"),
            )
            return 0 if success else 1

        except Exception as e:
            import traceback
            send_error(f"Upload workflow error: {e}")
            send_log("error", traceback.format_exc())
            return 1
        finally:
            from bridges.common.app_manager import force_stop_app
            force_stop_app(self.device_id, "youtube")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: youtube_upload_bridge.py <config.json>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to read config: {e}"}))
        sys.exit(1)

    bridge = YouTubeUploadBridge(config)
    sys.exit(bridge.run())


if __name__ == "__main__":
    main()
