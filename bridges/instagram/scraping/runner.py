"""Instagram scraping bridge runtime runner.

The bridge hands the launcher a `connect` that sets up the database and connects to the phone; the
launcher calls it once it has read the payload, so a refused payload connects nothing.
"""

from __future__ import annotations

import json

from loguru import logger

from bridges.common.network import send_network_refusal
from bridges.instagram.scraping.session import (
    configure_scraping_database,
    connect_scraping_device,
    create_scraping_connection,
    disconnect_scraping_connection,
    scraping_app,
)
from bridges.instagram.scraping.workflow import run_scraping_workflow
from taktik.core.shared.device.network_door import NetworkUnreachableError


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
    connection = None

    def connect(package_name):
        """The phone the launcher asks for, once it has read the payload, with the clean restart of the
        run's Instagram (a clone when the payload names one), as every Instagram bridge restarts it."""
        from taktik.core.social_media.instagram.workflows.common.startup import (
            InstagramRunPhone,
            start_instagram_session,
        )

        nonlocal connection
        configure_scraping_database()
        connection = create_scraping_connection(device_id)
        device_manager = connect_scraping_device(connection)
        if device_manager is None:
            raise RuntimeError("Failed to connect to device")
        app = scraping_app(connection, package_name)
        return InstagramRunPhone(device_manager=device_manager,
                                 start=lambda: start_instagram_session(app),
                                 installed_version=app.get_installed_version)

    try:
        result = run_scraping_workflow(config, connect)
        print_scraping_result(**result)
        return 0

    except NetworkUnreachableError as refused:
        # The launcher's network door, once the phone is connected: nothing was scraped.
        send_network_refusal(refused, "Scraping")
        print_scraping_result(False, error=str(refused), error_code=refused.error_code)
        return 1
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        print_scraping_result(False, error=str(e))
        return 1
    finally:
        # Only a connection the launcher asked for: a refused payload opened none.
        if connection is not None:
            disconnect_scraping_connection(connection)


__all__ = ["ScrapingRun", "print_scraping_result", "report_scraping_entry_error", "run_scraping_bridge"]
