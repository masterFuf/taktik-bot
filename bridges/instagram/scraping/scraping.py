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
from bridges.instagram.runtime.ipc import _ipc
from taktik.core.app.ai.providers.openrouter import AIService
from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow
from taktik.core.database import configure_db_service
from loguru import logger
from bridges.instagram.scraping.runtime.commands import load_scraping_bridge_config
from bridges.instagram.scraping.runtime.config import build_scraping_config

# Signal handlers for graceful shutdown
setup_signal_handlers()


def _build_scraping_ai_service(*, api_key: str, ipc=None, vision_model: str = None, text_model: str = None):
    """Bridge-owned AI provider factory for Instagram scraping workflows."""
    return AIService(api_key=api_key, ipc=ipc, vision_model=vision_model, text_model=text_model)

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

        # Run scraping workflow
        logger.info(f"Starting scraping workflow: {scraping_config['type']}")
        if scraping_config.get('enrich_profiles', False):
            logger.info("Enriched scraping enabled - will visit each profile for details")
        if scraping_config.get('deep_qualify', False):
            logger.info(f"🔬 Deep qualify enabled — max_following={scraping_config.get('deep_qualify_max_following', 30)}")
        else:
            logger.info(f"🔬 Deep qualify OFF — config received deepQualify={config.get('deepQualify')!r}, enrichProfiles={config.get('enrichProfiles')!r}")
        workflow = ScrapingWorkflow(
            device_manager,
            scraping_config,
            ai_notifier=_ipc,
            ai_service_factory=_build_scraping_ai_service,
        )
        result = workflow.run()

        # Output result as JSON for Electron to parse
        print(json.dumps({
            "success": result.get('success', False),
            "totalScraped": result.get('total_scraped', 0),
            "error": result.get('error')
        }))

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
