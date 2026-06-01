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
from bridges.youtube.publish.runtime.request import build_upload_request
from bridges.youtube.publish.runtime.workflow import run_youtube_upload_workflow
from bridges.youtube.base import _ipc, send_error, send_log, send_message, send_status
from bridges.youtube.runtime.session import cleanup_youtube_app, prepare_youtube_session


class YouTubeUploadBridge:
    """Bridge for YouTube video upload (Shorts or standard)."""

    SHORT_TITLE_MAX_LENGTH = 100

    def __init__(self, config: dict):
        self.config = config
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, _signum, _frame) -> None:
        send_status("stopping", "Received shutdown signal")

    def run(self) -> int:
        request = build_upload_request(
            self.config,
            self.SHORT_TITLE_MAX_LENGTH,
            send_error,
            send_log,
        )
        if not request:
            return 1

        session = prepare_youtube_session(request.device_id, send_status, send_error)
        if not session:
            return 1
        self._connection = session.connection

        try:
            return run_youtube_upload_workflow(
                device=session.device,
                device_id=request.device_id,
                request=request,
                send_status=send_status,
                send_message=send_message,
                send_error=send_error,
                send_log=send_log,
            )
        finally:
            cleanup_youtube_app(request.device_id)


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
