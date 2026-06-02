"""TikTok scraping workflow-test runner."""

from loguru import logger


def run_tiktok_scraping(conn, device, ipc, workflow_type, target, limits):
    """Run a TikTok scraping workflow."""
    try:
        from taktik.core.social_media.tiktok.scraping.engine import TikTokScrapingEngine

        scrape_type_map = {
            "scrape_account": "account",
            "scrape_hashtag": "hashtag",
            "scrape_post": "post",
        }
        scrape_type = scrape_type_map.get(workflow_type, "account")
        max_results = limits.get("maxResults", 100)

        ipc.send("workflow_step", step=f"tiktok_scraping_{scrape_type}", status="running")
        engine = TikTokScrapingEngine(device)
        results = engine.scrape(scrape_type=scrape_type, target=target, max_results=max_results)
        count = len(results) if results else 0
        ipc.send("workflow_step", step=f"tiktok_scraping_{scrape_type}", status="done")
        ipc.send(
            "action_event",
            action="tiktok_scraping_complete",
            username=target,
            success=count > 0,
            data={"count": count, "type": scrape_type},
        )
        return count > 0
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok scraping failed: {exc}")
        ipc.send("workflow_step", step=f"tiktok_scraping_{workflow_type}", status="error", error=str(exc))
        return False
