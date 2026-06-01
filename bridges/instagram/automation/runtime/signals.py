"""Signal handling for the Instagram desktop automation bridge."""

from __future__ import annotations

import signal

from bridges.common.runtime.signal_handler import setup_signal_handlers


def register_desktop_shutdown_handlers(handler, *, ipc) -> None:
    setup_signal_handlers(ipc=ipc)
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
