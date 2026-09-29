"""
Signal handling for graceful shutdown of bridge scripts.

Usage:
    from bridges.common.signal_handler import setup_signal_handlers

    # Simple: just exit cleanly on SIGINT/SIGTERM
    setup_signal_handlers()

    # With workflow reference: call workflow.stop() before exiting
    setup_signal_handlers(workflow=my_workflow)

    # With IPC: notify Electron before exiting
    setup_signal_handlers(ipc=ipc, workflow=my_workflow)
"""

import sys
import signal
from typing import Optional, Any
from loguru import logger


# Global workflow reference for signal handlers
_workflow = None
_ipc = None


def setup_signal_handlers(workflow: Any = None, ipc: Any = None) -> None:
    """
    Register signal handlers for graceful shutdown.

    Args:
        workflow: Optional workflow object with a .stop() method.
        ipc: Optional IPC instance to notify Electron before exiting.
    """
    global _workflow, _ipc
    _workflow = workflow
    _ipc = ipc

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    if sys.platform == 'win32':
        try:
            signal.signal(signal.SIGBREAK, _handle_signal)
        except (AttributeError, ValueError):
            pass


def update_workflow(workflow: Any) -> None:
    """
    Update the workflow reference after initial setup.
    Useful when the workflow is created after signal handlers are registered.
    """
    global _workflow
    _workflow = workflow


def _handle_signal(signum, frame):
    """Internal signal handler."""
    global _workflow, _ipc
    logger.info(f"🛑 Received signal {signum}, stopping gracefully...")

    if _ipc:
        try:
            _ipc.status("stopping", "Received stop signal")
        except Exception:
            pass

    if _workflow and hasattr(_workflow, 'stop'):
        try:
            _workflow.stop()
        except Exception:
            pass

    sys.exit(0)
