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

import json
import os
import signal
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.youtube.base import _ipc, logger, send_error, send_log, send_message, send_status
from bridges.youtube.runtime.session import cleanup_youtube_app, prepare_youtube_session


class YouTubeUploadBridge:
    """Bridge for YouTube video upload (Shorts or standard)."""

    SHORT_TITLE_MAX_LENGTH = 100

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.local_path = config.get("localPath", "")
        self.title = config.get("title", "")
        self.description = config.get("description", "")
        self.upload_type = config.get("uploadType", "short").lower()
        self.visibility = config.get("visibility", "public").lower()
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, _signum, _frame) -> None:
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

        if self.upload_type == "short" and self.title:
            chars = list(self.title.strip())
            if len(chars) > self.SHORT_TITLE_MAX_LENGTH:
                self.title = "".join(chars[:self.SHORT_TITLE_MAX_LENGTH]).strip()
                send_log(
                    "warning",
                    f"YouTube Shorts title trimmed to {self.SHORT_TITLE_MAX_LENGTH} characters",
                )

        session = prepare_youtube_session(self.device_id, send_status, send_error)
        if not session:
            return 1
        self._connection = session.connection

        send_status("running", "Starting YouTube upload workflow...")
        try:
            from taktik.core.social_media.youtube.workflows.publish.upload_workflow import (
                YouTubeUploadWorkflow,
                set_callbacks as set_upload_callbacks,
            )

            # Keep core workflow bridge-agnostic by injecting stdout callbacks here.
            set_upload_callbacks(log=send_log, status=send_status)

            workflow = YouTubeUploadWorkflow(session.device, self.device_id)
            result = workflow.execute(
                local_path=self.local_path,
                title=self.title,
                description=self.description,
                upload_type=self.upload_type,
                visibility=self.visibility,
            )

            success = bool(result.get("success", False))
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

        except Exception as exc:
            import traceback

            send_error(f"Upload workflow error: {exc}")
            send_log("error", traceback.format_exc())
            return 1
        finally:
            cleanup_youtube_app(self.device_id)


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: youtube_upload_bridge.py <config.json>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
    except Exception as exc:
        print(json.dumps({"type": "error", "message": f"Failed to read config: {exc}"}))
        sys.exit(1)

    bridge = YouTubeUploadBridge(config)
    sys.exit(bridge.run())


if __name__ == "__main__":
    main()
