"""Instagram scraping bridge runtime runner."""

from __future__ import annotations

import json

from loguru import logger

from bridges.instagram.scraping.runtime.session import (
    configure_scraping_database,
    connect_scraping_device,
    create_scraping_connection,
    disconnect_scraping_connection,
    scraping_installed_version,
)
from bridges.instagram.scraping.runtime.workflow import run_scraping_workflow


def print_scraping_result(success: bool, **fields) -> None:
    """The bridge's last line: the run's verdict, and what it scraped when it ran."""
    print(json.dumps({"type": "scraping_result", "success": success, **fields}))


def report_scraping_entry_error(message: str, _reason: str) -> None:
    """An entry failure (no file, unreadable file), in the bridge's own final JSON."""
    print_scraping_result(False, error=message)


class ScrapingRun:
    """One Instagram scraping run, from its config file (read by `run_bridge_main`)."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        return run_scraping_bridge(self.config)


def run_scraping_bridge(config: dict) -> int:
    """Run the Instagram scraping bridge and emit its terminal JSON payload."""
    if not config.get('deviceId'):
        print_scraping_result(False, error="No deviceId provided")
        return 1

    device_id = config.get("deviceId")
    configure_scraping_database()
    connection = create_scraping_connection(device_id)
    try:
        device_manager = connect_scraping_device(connection)
        if device_manager is None:
            print_scraping_result(False, error="Failed to connect to device")
            return 1

        result = run_scraping_workflow(
            device_manager,
            config,
            installed_version=scraping_installed_version(connection, config.get("packageName")),
        )
        print_scraping_result(**result)
        return 0

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        print_scraping_result(False, error=str(e))
        return 1
    finally:
        disconnect_scraping_connection(connection)


__all__ = ["ScrapingRun", "print_scraping_result", "report_scraping_entry_error", "run_scraping_bridge"]
