"""Runtime stdout/bootstrap primitives shared by bridge entrypoints."""

from .bootstrap import setup_environment
from .ipc import IPC
from .signal_handler import setup_signal_handlers
from .bridge_base import PlatformBridgeBase, run_bridge_main

__all__ = [
    "IPC",
    "PlatformBridgeBase",
    "run_bridge_main",
    "setup_environment",
    "setup_signal_handlers",
]
