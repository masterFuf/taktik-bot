#!/usr/bin/env python3
"""
YouTube Upload Bridge
=====================
Bridge for publishing a video (Short or standard Video) on YouTube.

Config JSON (declared in `taktik/core/contract/publish.py`):
  {
    "deviceId": "...",
    "localPath": "/absolute/path/to/file.mp4",
    "title": "My video title",
    "description": "Optional description",
    "uploadType": "short"        // "short" | "video" (default: "short")
  }
"""

import os
import signal
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.bootstrap import setup_environment

setup_environment()

from bridges.common.entrypoint import CONFIG_ERROR, report_error_message, run_bridge_main
from bridges.common.signal_handler import setup_signal_handlers
from bridges.youtube.publish.workflow import run_youtube_upload_workflow
from bridges.common.bridge_base import _ipc, send_error, send_log, send_message, send_status
from bridges.youtube.common.session import cleanup_youtube_app, prepare_youtube_session


class YouTubeUploadBridge:
    """Bridge for YouTube video upload (Shorts or standard)."""

    def __init__(self, config: dict):
        self.config = config
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, _signum, _frame) -> None:
        send_status("stopping", "Received shutdown signal")

    def run(self) -> int:
        from taktik.core.social_media.youtube.workflows.publish.payload import (
            YouTubeUploadRequestError,
            check_upload_file,
            youtube_upload_request_from_payload,
        )

        device_id = self.config.get("deviceId")
        if not device_id:
            send_error("deviceId is required")
            return 1
        try:
            # Read before connecting: a missing file means the phone is not touched.
            request = youtube_upload_request_from_payload(self.config)
            check_upload_file(request)
        except YouTubeUploadRequestError as exc:
            send_error(str(exc))
            return 1

        session = prepare_youtube_session(device_id, send_status, send_error)
        if not session:
            return 1
        self._connection = session.connection

        try:
            return run_youtube_upload_workflow(
                device=session.device,
                device_id=device_id,
                config=self.config,
                upload_type=request.upload_type,
                send_status=send_status,
                send_message=send_message,
                send_error=send_error,
                send_log=send_log,
            )
        finally:
            cleanup_youtube_app(device_id)


def main() -> None:
    run_bridge_main(YouTubeUploadBridge, usage="youtube_upload_bridge.py <config.json>",
                    report_error=report_error_message, messages={CONFIG_ERROR: "Failed to read config: {error}"},
                    catch_crashes=False)


if __name__ == "__main__":
    main()
