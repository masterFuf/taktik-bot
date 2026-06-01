"""Runtime stdout/bootstrap primitives shared by bridge entrypoints."""

from .bootstrap import setup_environment
from .entrypoint import run_bridge_main
from .ipc import IPC
from .platform_bridge import PlatformBridgeBase
from .signal_handler import setup_signal_handlers

__all__ = [
    "IPC",
    "PlatformBridgeBase",
    "run_bridge_main",
    "setup_environment",
    "setup_signal_handlers",
]
