"""Instagram workflow runners for compat workflow diagnostics."""

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


def run_instagram_dm(conn, device, ipc, workflow_type, limits, delays):
    """Run an Instagram DM workflow."""
    try:
        max_dms = limits.get("maxDMs", 10)

        if workflow_type == "dm_response":
            from taktik.core.social_media.instagram.engagement.dm.reader import DMReader

            ipc.send("workflow_step", step="dm_read", status="running")
            reader = DMReader(device)
            conversations = reader.read_conversations(max_conversations=max_dms)
            count = len(conversations) if conversations else 0
            ipc.send("workflow_step", step="dm_read", status="done")
            ipc.send(
                "action_event",
                action="dm_read_complete",
                username="",
                success=count > 0,
                data={"conversations": count},
            )
            return count > 0

        if workflow_type == "dm_outreach":
            from taktik.core.social_media.instagram.engagement.dm.outreach import DMOutreach

            ipc.send("workflow_step", step="dm_outreach", status="running")
            outreach = DMOutreach(device)
            sent = outreach.send_batch(max_dms=max_dms)
            ipc.send("workflow_step", step="dm_outreach", status="done")
            ipc.send(
                "action_event",
                action="dm_outreach_complete",
                username="",
                success=sent > 0,
                data={"sent": sent},
            )
            return sent > 0

        return False
    except Exception as exc:
        logger.exception(f"[WorkflowTest] DM workflow failed: {exc}")
        ipc.send("workflow_step", step=workflow_type, status="error", error=str(exc))
        return False


def run_instagram_smart_comment(conn, device, ipc, target, limits, delays):
    """Run an Instagram Smart Comment workflow."""
    try:
        from taktik.core.social_media.instagram.engagement.smart_comment.engine import SmartCommentEngine

        max_comments = limits.get("maxComments", 5)

        ipc.send("workflow_step", step="smart_comment_scrape", status="running")
        engine = SmartCommentEngine(device)
        result = engine.run(
            target_username=target if target else None,
            max_comments=max_comments,
        )
        success = result.get("success", False) if isinstance(result, dict) else bool(result)
        ipc.send("workflow_step", step="smart_comment_scrape", status="done" if success else "failed")
        ipc.send(
            "action_event",
            action="smart_comment_complete",
            username=target or "",
            success=success,
            data={"max_comments": max_comments},
        )
        return success
    except Exception as exc:
        logger.exception(f"[WorkflowTest] Smart comment failed: {exc}")
        ipc.send("workflow_step", step="smart_comment", status="error", error=str(exc))
        return False


def run_instagram_publish(conn, device, ipc, workflow_type):
    """Run an Instagram publish navigation test."""
    try:
        from taktik.core.social_media.instagram.publish.navigator import PublishNavigator

        upload_type_map = {
            "upload_post": "post",
            "upload_carousel": "carousel",
            "upload_reel": "reel",
            "upload_story": "story",
        }
        upload_type = upload_type_map.get(workflow_type, "post")

        ipc.send("workflow_step", step=f"publish_navigate_{upload_type}", status="running")
        navigator = PublishNavigator(device)
        can_navigate = navigator.navigate_to_upload(upload_type=upload_type)
        ipc.send("workflow_step", step=f"publish_navigate_{upload_type}", status="done" if can_navigate else "failed")
        ipc.send("action_event", action="publish_navigation", username="", success=can_navigate, data={"type": upload_type})

        try:
            navigator.go_back_to_home()
        except Exception:
            pass

        return can_navigate
    except Exception as exc:
        logger.exception(f"[WorkflowTest] Publish workflow failed: {exc}")
        ipc.send("workflow_step", step=f"publish_{workflow_type}", status="error", error=str(exc))
        return False


__all__ = [
    "run_instagram_dm",
    "run_instagram_publish",
    "run_instagram_scraping",
    "run_instagram_smart_comment",
]

