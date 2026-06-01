"""Instagram scraping bridge runtime runner."""

from __future__ import annotations

import json

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


def run_scraping_bridge(argv: list[str]) -> int:
    """Run the Instagram scraping bridge and emit its terminal JSON payload."""
    config = load_scraping_bridge_config(argv)
    if config is None:
        return 1

    device_id = config.get("deviceId")
    configure_scraping_database()
    connection = create_scraping_connection(device_id)
    try:
        device_manager = connect_scraping_device(connection)
        if device_manager is None:
            return 1

        scraping_config = build_scraping_config(config)
        result = run_scraping_workflow(device_manager, scraping_config, config)
        print(json.dumps(result))
        return 0

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        print(json.dumps({"success": False, "error": str(e)}))
        return 1
    finally:
        disconnect_scraping_connection(connection)


__all__ = ["run_scraping_bridge"]
