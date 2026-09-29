"""Instagram publish bridge runtime class.

The one Instagram publisher of the desktop app: post, reel, carousel and story all go through
this bridge. It connects the device when the launcher asks for it and translates the result into
JSON events; the request is read, refused or run by the launcher the CLI and the Lab call too,
`run_instagram_publish` (`instagram.content.publish`). The config file carries `deviceId`,
`mediaPaths` (or `localPath`), `caption`, `hashtags`, `postType`, `packageName` and `botUsername`.
"""

from __future__ import annotations

import signal

from bridges.common.device.connection import ConnectionService
from bridges.common.signal_handler import setup_signal_handlers
from bridges.instagram.common.ipc import _ipc, send_error, send_log, send_status


class DeviceConnectionFailed(RuntimeError):
    """The bridge could not connect the phone the launcher asked for."""


class InstagramPublishBridge:
    """Bridge for Instagram post/reel/carousel/story publishing."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self._connection = None
        self._stop_requested = False

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        self._stop_requested = True
        send_status("stopping", "Received shutdown signal")

    def _connected_device(self):
        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            raise DeviceConnectionFailed("Failed to connect to device")
        return self._connection.device

    def run(self) -> int:
        from taktik.core.social_media.instagram.workflows.publish.agent_handler import run_instagram_publish
        from taktik.core.social_media.instagram.workflows.publish.payload import PublishRequestError

        if not self.device_id:
            send_error("deviceId is required")
            return 1

        try:
            result = run_instagram_publish(
                self.config,
                device_id=self.device_id,
                connect=self._connected_device,
                log=send_log,
                status=send_status,
            )
        except PublishRequestError as exc:
            send_error(str(exc))
            return 1
        except DeviceConnectionFailed as exc:
            send_error(str(exc), "device_connection_failed")
            return 1
        finally:
            self._disconnect()

        if result.get("success"):
            send_status("completed", result.get("message", "Published"))
            return 0
        send_error(result.get("message", "Publish failed"), result.get("error_type"))
        return 1

    def _disconnect(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.disconnect()
        except Exception as exc:  # noqa: BLE001 - the publication is over either way
            send_log("warning", f"Device disconnect failed: {exc}")
