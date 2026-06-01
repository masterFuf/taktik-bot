#!/usr/bin/env python3
"""
Scraping Bridge for TAKTIK Desktop
Connects the Electron app to the Python scraping workflow
"""

import sys
import json
import os

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.signal_handler import setup_signal_handlers
from taktik.core.database import configure_db_service
from loguru import logger
from bridges.instagram.scraping.runtime.commands import load_scraping_bridge_config
from bridges.instagram.scraping.runtime.config import build_scraping_config
from bridges.instagram.scraping.runtime.workflow import run_scraping_workflow

# Signal handlers for graceful shutdown
setup_signal_handlers()


def main():
    config = load_scraping_bridge_config(sys.argv)
    if config is None:
        sys.exit(1)

    device_id = config.get('deviceId')
    try:
        configure_db_service()
        logger.info("Database service configured (local SQLite)")
    except Exception as e:
        logger.warning(f"Could not configure database service: {e}")

    connection = ConnectionService(device_id)
    try:
        # Connect via ConnectionService
        if not connection.connect():
            print(json.dumps({"success": False, "error": "Failed to connect to device"}))
            sys.exit(1)
        device_manager = connection.device_manager

        scraping_config = build_scraping_config(config)

        result = run_scraping_workflow(device_manager, scraping_config, config)
        print(json.dumps(result))

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        try:
            connection.disconnect()
        except Exception:
            pass

if __name__ == '__main__':
    main()
