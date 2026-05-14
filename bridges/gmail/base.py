#!/usr/bin/env python3
"""
Gmail Bridge Base — Common utilities for Gmail bridges.

Mirrors bridges/tiktok/base.py: bootstrap + IPC singleton + helper senders.
"""

import sys
import os

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.ipc import IPC
from loguru import logger

_ipc = IPC()


def send_message(msg_type: str, **kwargs):
    """Send a structured JSON message to the desktop app."""
    _ipc.send(msg_type, **kwargs)


def send_status(status: str, message: str = ""):
    """Send status update to desktop app."""
    _ipc.status(status, message)


def send_error(error: str):
    """Send error to desktop app."""
    _ipc.error(error)


def send_log(level: str, message: str):
    """Send log message to desktop app."""
    _ipc.log(level, message)
