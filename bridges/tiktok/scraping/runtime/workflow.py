"""TikTok scraping bridge workflow runner."""

from __future__ import annotations

import time
from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.scraping.runtime.config import build_scraping_config, create_scraping_session
from bridges.tiktok.scraping.runtime.events import (
    send_scraped_profile,
    send_scraping_completed,
    send_scraping_progress,
)
from bridges.tiktok.scraping.runtime.persistence import (
    save_scraped_profile,
    update_scraping_session,
)


def run_scraping_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok scraping workflow."""
    from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow import ScrapingWorkflow

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    enrich_profiles = config.get("enrichProfiles", True)
    max_profiles_to_enrich = config.get("maxProfilesToEnrich", 50)
    save_to_db = config.get("saveToDb", True)

    logger.info(f"Starting TikTok Scraping workflow on device: {device_id}")
    logger.info(f"Enrichment: {'enabled' if enrich_profiles else 'disabled'}, max: {max_profiles_to_enrich}")
    send_status("starting", "Initializing TikTok Scraping workflow")

    try:
        manager, _ = tiktok_startup(device_id, fetch_profile=True)
        device = manager.device_manager.device
        navigation = NavigationActions(device)

        wf_config = build_scraping_config(config)
        workflow = ScrapingWorkflow(device, navigation, wf_config)
        set_workflow(workflow)

        session_id = create_scraping_session(config) if save_to_db else None

        workflow.set_on_status_callback(lambda s, m: send_status(s, m))
        workflow.set_on_progress_callback(
            lambda scraped, total, current: send_scraping_progress(scraped, total, current)
        )
        workflow.set_on_profile_callback(lambda p: send_scraped_profile(p))
        workflow.set_on_error_callback(lambda m: send_error(m))

        if save_to_db and session_id:
            workflow.set_on_save_profile_callback(lambda p: save_scraped_profile(session_id, p, "tiktok"))

        start_time = time.time()
        all_profiles = workflow.run()
        duration = int(time.time() - start_time)

        if save_to_db and session_id:
            update_scraping_session(
                session_id,
                len(all_profiles),
                "COMPLETED" if not workflow.stopped else "STOPPED",
                duration,
            )

        send_scraping_completed(len(all_profiles))
        send_status("completed", f"Scraped {len(all_profiles)} profiles")
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


__all__ = ["run_scraping_workflow"]
