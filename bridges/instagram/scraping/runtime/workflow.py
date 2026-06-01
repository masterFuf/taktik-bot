"""Workflow runner for the Instagram scraping bridge."""

from __future__ import annotations

from loguru import logger

from bridges.instagram.runtime.ipc import _ipc
from bridges.instagram.scraping.runtime.ai import build_scraping_ai_service
from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow


def run_scraping_workflow(device_manager, scraping_config: dict, bridge_config: dict) -> dict:
    logger.info(f"Starting scraping workflow: {scraping_config['type']}")
    if scraping_config.get('enrich_profiles', False):
        logger.info("Enriched scraping enabled - will visit each profile for details")
    if scraping_config.get('deep_qualify', False):
        logger.info(
            f"\U0001f52c Deep qualify enabled \u2014 "
            f"max_following={scraping_config.get('deep_qualify_max_following', 30)}"
        )
    else:
        logger.info(
            f"\U0001f52c Deep qualify OFF \u2014 config received "
            f"deepQualify={bridge_config.get('deepQualify')!r}, "
            f"enrichProfiles={bridge_config.get('enrichProfiles')!r}"
        )

    workflow = ScrapingWorkflow(
        device_manager,
        scraping_config,
        ai_notifier=_ipc,
        ai_service_factory=build_scraping_ai_service,
    )
    result = workflow.run()

    return {
        "success": result.get('success', False),
        "totalScraped": result.get('total_scraped', 0),
        "error": result.get('error'),
    }
