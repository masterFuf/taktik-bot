"""
Bootstrap utilities for bridge scripts.
Handles UTF-8 encoding, loguru configuration, and Python path setup.

Usage:
    from bridges.common.bootstrap import setup_environment
    setup_environment()  # Call at the top of every bridge script
"""

import sys
import os
from loguru import logger


_initialized = False

def setup_environment(log_level: str = "DEBUG"):
    """
    Initialize the bridge environment:
    1. Force UTF-8 encoding on Windows (emoji support)
    2. Configure loguru with a standard format
    3. Add the bot directory to sys.path so 'taktik' module is importable

    Call this once at the top of every bridge script.
    Safe to call multiple times — only the first call takes effect.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True
    _setup_utf8()
    _setup_loguru(log_level)
    _setup_python_path()


def _setup_utf8():
    """Force UTF-8 encoding for stdout/stderr on Windows to support emojis."""
    if sys.platform == 'win32':
        import io
        # line_buffering=True ensures real-time output to Electron
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True
        )


def _setup_loguru(level: str = "DEBUG"):
    """Configure loguru with a standard format for bridge scripts."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        level=level,
        colorize=False
    )


def _setup_python_path():
    """
    Add the bot root directory to sys.path so that 'taktik' module is importable.
    
    Directory structure:
        bot/                    <-- this gets added to sys.path
        ├── bridges/
        │   ├── common/         <-- this file lives here
        │   ├── instagram/
        │   └── tiktok/
        └── taktik/
            └── core/
    """
    # common/ -> bridges/ -> bot/
    bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)
