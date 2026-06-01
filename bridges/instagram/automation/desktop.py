#!/usr/bin/env python3
"""
Desktop Bridge for TAKTIK Bot
This script allows the TAKTIK Desktop app to launch bot sessions programmatically.
It accepts a JSON configuration and runs the appropriate workflow.
"""

import sys
import os
import json
import logging

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.instagram.automation.runtime.bridge import DesktopBridge
from bridges.instagram.automation.runtime.entrypoint import run_desktop_config
from bridges.instagram.automation.runtime.input import load_desktop_config
from bridges.instagram.runtime.ipc import (
    logger,
    send_error,
    send_log,
    setup_stats_callback,
)

# Configure logging for desktop integration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Main entry point."""
    try:
        # Setup stats IPC callback before any workflow runs
        setup_stats_callback()
        config = load_desktop_config(send_log)

        if config is None:
            send_error("No configuration provided. Use: desktop_bridge <config.json> or pipe JSON to stdin")
            sys.exit(1)

        sys.exit(run_desktop_config(config, DesktopBridge))

    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON configuration: {str(e)}")
        sys.exit(1)
    except Exception as e:
        send_error(f"Bridge error: {str(e)}")
        logger.exception("Bridge error")
        sys.exit(1)


if __name__ == "__main__":
    main()
