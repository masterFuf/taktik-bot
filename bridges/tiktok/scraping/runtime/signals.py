"""Signal handling for the TikTok scraping bridge."""

from __future__ import annotations

import signal
import sys

from bridges.tiktok.runtime.ipc import get_workflow, logger


def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}, stopping workflow...")
    workflow = get_workflow()
    if workflow:
        workflow.stop()
    sys.exit(0)


def register_scraping_signal_handlers() -> None:
    """Register graceful shutdown handlers for scraping workflow runs."""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


__all__ = ["register_scraping_signal_handlers", "signal_handler"]
