"""Instagram scraping workflow-test runner."""

from loguru import logger


def run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays):
    """Run an Instagram scraping workflow."""
    try:
        from taktik.core.social_media.instagram.scraping.engine import ScrapingEngine

        scrape_type_map = {
            "scrape_account": "target",
            "scrape_hashtag": "hashtag",
            "scrape_post_url": "post",
            "scrape_e_story": "story_viewers",
        }
        scrape_type = scrape_type_map.get(workflow_type, "target")
        max_results = limits.get("maxResults", 100)

        engine = ScrapingEngine(device)
        ipc.send("workflow_step", step=f"scraping_{scrape_type}", status="running")

        results = engine.scrape(
            scrape_type=scrape_type,
            target=target,
            max_results=max_results,
            delay_min=delays.get("min", 2) if delays else 2,
            delay_max=delays.get("max", 5) if delays else 5,
        )

        count = len(results) if results else 0
        ipc.send("workflow_step", step=f"scraping_{scrape_type}", status="done")
        ipc.send(
            "action_event",
            action="scraping_complete",
            username=target,
            success=count > 0,
            data={"count": count, "type": scrape_type},
        )
        logger.info(f"[WorkflowTest] Scraping {scrape_type} complete: {count} results")
        return count > 0
    except Exception as exc:
        logger.exception(f"[WorkflowTest] Scraping failed: {exc}")
        ipc.send("workflow_step", step=f"scraping_{workflow_type}", status="error", error=str(exc))
        return False
