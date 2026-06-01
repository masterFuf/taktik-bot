"""
Shared bridge facade for historical platform `base.py` modules.

This module keeps the public compatibility surface used across platform
facades:
  - a shared `_ipc` singleton;
  - module-level JSON stdout wrappers (`send_*`);
  - signal helper re-exports;
  - compatibility re-exports for `PlatformBridgeBase` and config-file
    entrypoint helpers.

Durable ownership lives in dedicated modules:
  - `bridges.common.runtime.ipc` owns JSON stdout transport;
  - `bridges.common.runtime.signal_handler` owns signal plumbing;
  - `bridges.common.runtime.entrypoint` owns config-file launch helpers;
  - `bridges.common.runtime.platform_bridge` owns the shared device/app
    bridge scaffold.
"""

from __future__ import annotations

from typing import Any, Optional

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.common.runtime import signal_handler as _sig_mod
from bridges.common.runtime.entrypoint import load_bridge_config, run_bridge_main
from bridges.common.runtime.ipc import IPC
from bridges.common.runtime.platform_bridge import PlatformBridgeBase
from loguru import logger


_ipc: IPC = IPC()


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


def get_workflow():
    """Return the currently registered workflow reference."""
    return _sig_mod._workflow


def set_workflow(workflow: Any) -> None:
    """Register the workflow that should receive `.stop()` on SIGINT/SIGTERM."""
    _sig_mod.update_workflow(workflow)


def signal_handler(signum, frame) -> None:
    """Delegate to the shared signal handler module."""
    _sig_mod._handle_signal(signum, frame)


__all__ = [
    "_ipc",
    "IPC",
    "logger",
    "send_message",
    "send_status",
    "send_error",
    "send_log",
    "send_progress",
    "get_workflow",
    "set_workflow",
    "signal_handler",
    "PlatformBridgeBase",
    "load_bridge_config",
    "run_bridge_main",
]
