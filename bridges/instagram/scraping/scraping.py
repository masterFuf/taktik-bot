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

from bridges.common.runtime.signal_handler import setup_signal_handlers
from loguru import logger
from bridges.instagram.scraping.runtime.commands import load_scraping_bridge_config
from bridges.instagram.scraping.runtime.config import build_scraping_config
from bridges.instagram.scraping.runtime.session import (
    configure_scraping_database,
    connect_scraping_device,
    create_scraping_connection,
    disconnect_scraping_connection,
)
from bridges.instagram.scraping.runtime.workflow import run_scraping_workflow

# Signal handlers for graceful shutdown
setup_signal_handlers()


def main():
    config = load_scraping_bridge_config(sys.argv)
    if config is None:
        sys.exit(1)

    device_id = config.get('deviceId')
    configure_scraping_database()
    connection = create_scraping_connection(device_id)
    try:
        device_manager = connect_scraping_device(connection)
        if device_manager is None:
            sys.exit(1)

        scraping_config = build_scraping_config(config)

        result = run_scraping_workflow(device_manager, scraping_config, config)
        print(json.dumps(result))

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        disconnect_scraping_connection(connection)

if __name__ == '__main__':
    main()
