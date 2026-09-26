"""TikTok scraping bridge runtime.

The run is `run_tiktok_scraping` (core), the launcher the Agent handlers
`tiktok.automation.scraping` and `tiktok.standalone.tiktok_scraping` (and so the CLI) call too:
read the payload, start TikTok, scrape, file the session and its profiles. Both desktop entries
land here: `tiktok_scraping_bridge` (its config file, `TikTokScrapingBridge`) and the
`scraping` branch of the `tiktok_bridge` dispatcher (`run_scraping_workflow`). This module only
injects what is specific to the desktop: the startup that prints on stdout, its IPC for the live
events, the stop signal.
"""

from __future__ import annotations

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def run_scraping_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok scraping workflow. True when it ran to its end."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"Starting TikTok Scraping workflow on device: {device_id}")
    send_status("starting", "Initializing TikTok Scraping workflow")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.scraping.agent_handler import (
            run_tiktok_scraping,
        )

        run_tiktok_scraping(
            config,
            notifier=_ipc,
            tiktok_startup=tiktok_startup_provider(device_id),
            workflow_hook=set_workflow,
        )
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Scraping workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


class TikTokScrapingBridge:
    """One `tiktok_scraping_bridge` process: the app's config file, then the run."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def run(self) -> int:
        logger.info("TikTok Scraping Bridge started")
        return 0 if run_scraping_workflow(self.config) else 1


__all__ = ["TikTokScrapingBridge", "run_scraping_workflow"]
