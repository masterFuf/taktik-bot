"""
Shared bridge infrastructure — eliminates the duplication across the 5
platform `base.py` files (Instagram, TikTok, Threads, YouTube, Gmail).

This module exposes:
  - A shared `_ipc` singleton (one duped stdout fd, reused everywhere).
  - Module-level wrappers (`send_message`, `send_status`, `send_error`,
    `send_log`, `send_progress`) that every bridge needs.
  - `PlatformBridgeBase`: connect + restart logic, used to be copy-pasted
    in `InstagramBridgeBase` and `ThreadsBridgeBase`.
  - `run_bridge_main(...)`: factor out the `if __name__ == "__main__"`
    boilerplate (parse JSON config, instantiate bridge, exit with code).

Each platform's `base.py` re-exports from here so existing imports like
``from bridges.instagram.base import send_status`` keep working without
any change at call sites.
"""

from __future__ import annotations

import json
import os
import signal
import sys
from typing import Any, Callable, Optional, Type

# Bootstrap must happen before importing the rest of bridges.common
# (importing this module from a bridge entrypoint guarantees setup).
from bridges.common.bootstrap import setup_environment

setup_environment()

from bridges.common.ipc import IPC
from bridges.common import signal_handler as _sig_mod
from loguru import logger


# ────────────────────────────────────────────────────────────────────────
# Shared IPC singleton
# ────────────────────────────────────────────────────────────────────────

# A single IPC instance is enough — IPC.send() writes to the duplicated
# stdout fd, which is identical regardless of how many IPC() instances
# we create. Sharing avoids duplicate `os.dup(1)` calls at import time.
_ipc: IPC = IPC()


# ────────────────────────────────────────────────────────────────────────
# Module-level IPC wrappers (used by EVERY bridge)
# ────────────────────────────────────────────────────────────────────────

def send_message(msg_type: str, **kwargs: Any) -> None:
    """Send a structured JSON message to the desktop app."""
    _ipc.send(msg_type, **kwargs)


def send_status(status: str, message: str = "") -> None:
    """Send a status update (connecting, running, completed, ...)."""
    _ipc.status(status, message)


def send_error(error: str, error_code: Optional[str] = None) -> None:
    """Send an error to the desktop app, with an optional i18n code."""
    _ipc.error(error, error_code)


def send_log(level: str, message: str) -> None:
    """Forward a log line to the desktop debug console."""
    _ipc.log(level, message)


def send_progress(current: int, total: int, action: str = "") -> None:
    """Send a progress update (e.g. 5/100 profiles processed)."""
    _ipc.progress(current, total, action)


# ────────────────────────────────────────────────────────────────────────
# Signal handling re-exports (parity with the old bases)
# ────────────────────────────────────────────────────────────────────────

def get_workflow():
    """Return the currently registered workflow reference."""
    return _sig_mod._workflow


def set_workflow(workflow: Any) -> None:
    """Register the workflow that should receive `.stop()` on SIGINT/SIGTERM."""
    _sig_mod.update_workflow(workflow)


def signal_handler(signum, frame) -> None:
    """Delegate to the shared signal handler in `bridges.common.signal_handler`."""
    _sig_mod._handle_signal(signum, frame)


# ────────────────────────────────────────────────────────────────────────
# Platform-agnostic bridge base class
# ────────────────────────────────────────────────────────────────────────

class PlatformBridgeBase:
    """
    Shared scaffolding for any bridge that needs a device connection and
    an app lifecycle (Instagram, TikTok, Threads, YouTube, ...).

    Subclasses must set:
      - `PLATFORM`: key understood by `AppService` (e.g. "instagram").
      - `DEFAULT_PACKAGE`: default Android package for that platform.

    Subclasses MAY override `_after_connect()` to inject custom logic
    after the connection is up (e.g. wrapping the device in a proxy).
    """

    PLATFORM: str = ""
    DEFAULT_PACKAGE: str = ""

    def __init__(self, device_id: str, package_name: Optional[str] = None):
        from bridges.common.connection import ConnectionService

        self.device_id = device_id
        self.package_name = package_name or self.DEFAULT_PACKAGE
        self._connection = ConnectionService(device_id)
        self._app = None
        # Backward-compatible aliases — populated by `connect()`
        self.device_manager = None
        self.device = None
        self.screen_width = 1080
        self.screen_height = 2340

    def connect(self) -> bool:
        """Open the device connection and bootstrap the AppService."""
        from bridges.common.app_manager import AppService

        if not self._connection.connect():
            return False
        self.device_manager = self._connection.device_manager
        self.device = self._connection.device
        self.screen_width, self.screen_height = self._connection.screen_size

        # Pass `package_override` only when it differs from the platform default,
        # so that auto-detection logic inside AppService still runs for cloned/
        # multi-package platforms (TikTok variants, etc.).
        override = (
            self.package_name
            if self.package_name and self.package_name != self.DEFAULT_PACKAGE
            else None
        )
        self._app = AppService(
            self._connection,
            platform=self.PLATFORM,
            package_override=override,
        )

        self._after_connect()
        return True

    def _after_connect(self) -> None:
        """Hook for subclasses to inject post-connection logic."""
        return None

    def restart(self) -> None:
        """Restart the app for a clean initial state via AppService."""
        if self._app is None:
            raise RuntimeError(
                f"{type(self).__name__}.restart() called before connect()"
            )
        self._app.restart()


# ────────────────────────────────────────────────────────────────────────
# Bridge entrypoint helpers — factor out the `main()` boilerplate
# ────────────────────────────────────────────────────────────────────────

def load_bridge_config(config_path: str) -> dict:
    """Read a JSON config file the way every bridge does it.

    Falls back to `utf-8-sig` so configs written by Electron's `fs.writeFileSync`
    on Windows (which can emit a BOM) still parse correctly.
    """
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except UnicodeError:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)


def run_bridge_main(
    bridge_factory: Callable[[dict], Any],
    *,
    usage: str = "bridge <config_path>",
    install_signal_handlers: bool = False,
) -> None:
    """
    Universal `main()` for bridges that take a single JSON config path and
    expose a `.run() -> int` method.

    Example::

        if __name__ == "__main__":
            run_bridge_main(MyBridge)

    The helper:
      1. Validates `sys.argv` and reads the config JSON.
      2. Instantiates the bridge via `bridge_factory(config)`.
      3. Calls `bridge.run()` and exits with its return code.

    On argv/JSON errors it emits a structured `{"type": "error", ...}` line
    on stdout so the Electron parent can surface the issue.
    """
    if install_signal_handlers:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": f"Usage: {usage}"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        config = load_bridge_config(config_path)
    except Exception as e:
        # Emit both a structured error (for the UI) and a log line (for stderr).
        send_error(f"Failed to load config: {e}")
        logger.error(f"Failed to load config from {config_path}: {e}")
        sys.exit(1)

    try:
        bridge = bridge_factory(config)
    except Exception as e:
        send_error(f"Failed to initialize bridge: {e}")
        logger.exception("Bridge initialization failed")
        sys.exit(1)

    try:
        sys.exit(int(bridge.run()))
    except SystemExit:
        raise
    except KeyboardInterrupt:
        logger.info("Bridge interrupted by user")
        sys.exit(0)
    except Exception as e:
        send_error(f"Bridge crashed: {e}")
        logger.exception("Bridge crashed")
        sys.exit(1)


__all__ = [
    # IPC singleton
    "_ipc",
    "IPC",
    "logger",
    # Module-level wrappers
    "send_message",
    "send_status",
    "send_error",
    "send_log",
    "send_progress",
    # Signal handling
    "get_workflow",
    "set_workflow",
    "signal_handler",
    # Base class + entrypoint
    "PlatformBridgeBase",
    "load_bridge_config",
    "run_bridge_main",
]
