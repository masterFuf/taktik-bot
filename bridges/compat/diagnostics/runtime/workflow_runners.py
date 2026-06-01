"""Platform workflow runners for compat workflow diagnostics."""

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


def run_tiktok_automation(conn, device, ipc, workflow_type, target, limits, probs, delays):
    """Run a TikTok automation workflow."""
    try:
        max_videos = limits.get("maxVideos", limits.get("maxFollowers", 15))
        like_pct = probs.get("like", 30)
        follow_pct = probs.get("follow", 10)
        favorite_pct = probs.get("favorite", 5)

        if workflow_type == "for_you":
            from taktik.core.social_media.tiktok.workflows.for_you import ForYouWorkflow

            ipc.send("workflow_step", step="tiktok_for_you", status="running")
            wf = ForYouWorkflow(device)
            success = wf.run(
                max_videos=max_videos,
                like_probability=like_pct,
                follow_probability=follow_pct,
                favorite_probability=favorite_pct,
            )
            ipc.send("workflow_step", step="tiktok_for_you", status="done" if success else "failed")
            return success

        if workflow_type == "hashtag":
            from taktik.core.social_media.tiktok.workflows.hashtag import HashtagWorkflow

            ipc.send("workflow_step", step="tiktok_hashtag", status="running")
            wf = HashtagWorkflow(device)
            success = wf.run(
                search_query=target,
                max_videos=max_videos,
                like_probability=like_pct,
                follow_probability=follow_pct,
                favorite_probability=favorite_pct,
            )
            ipc.send("workflow_step", step="tiktok_hashtag", status="done" if success else "failed")
            return success

        if workflow_type == "target":
            from taktik.core.social_media.tiktok.workflows.target import TargetWorkflow

            ipc.send("workflow_step", step="tiktok_target", status="running")
            wf = TargetWorkflow(device)
            success = wf.run(
                target_accounts=[target],
                max_videos=max_videos,
                like_probability=like_pct,
                follow_probability=follow_pct,
                favorite_probability=favorite_pct,
            )
            ipc.send("workflow_step", step="tiktok_target", status="done" if success else "failed")
            return success

        if workflow_type == "followers":
            from taktik.core.social_media.tiktok.workflows.followers import FollowersWorkflow

            ipc.send("workflow_step", step="tiktok_followers", status="running")
            wf = FollowersWorkflow(device)
            success = wf.run(
                targets=[target],
                max_followers=limits.get("maxFollowers", 10),
                like_probability=like_pct,
                follow_probability=follow_pct,
                favorite_probability=favorite_pct,
            )
            ipc.send("workflow_step", step="tiktok_followers", status="done" if success else "failed")
            return success

        return False
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok automation failed: {exc}")
        ipc.send("workflow_step", step=f"tiktok_{workflow_type}", status="error", error=str(exc))
        return False


def run_tiktok_dm(conn, device, ipc, workflow_type, limits):
    """Run a TikTok DM workflow."""
    try:
        max_dms = limits.get("maxDMs", 10)

        if workflow_type == "dm_read":
            from taktik.core.social_media.tiktok.engagement.dm.reader import TikTokDMReader

            ipc.send("workflow_step", step="tiktok_dm_read", status="running")
            reader = TikTokDMReader(device)
            conversations = reader.read_conversations(max_conversations=max_dms)
            count = len(conversations) if conversations else 0
            ipc.send("workflow_step", step="tiktok_dm_read", status="done")
            ipc.send(
                "action_event",
                action="tiktok_dm_read_complete",
                username="",
                success=count > 0,
                data={"conversations": count},
            )
            return count > 0

        if workflow_type == "dm_outreach":
            from taktik.core.social_media.tiktok.engagement.dm.outreach import TikTokDMOutreach

            ipc.send("workflow_step", step="tiktok_dm_outreach", status="running")
            outreach = TikTokDMOutreach(device)
            sent = outreach.send_batch(max_dms=max_dms)
            ipc.send("workflow_step", step="tiktok_dm_outreach", status="done")
            ipc.send(
                "action_event",
                action="tiktok_dm_outreach_complete",
                username="",
                success=sent > 0,
                data={"sent": sent},
            )
            return sent > 0

        return False
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok DM failed: {exc}")
        ipc.send("workflow_step", step=f"tiktok_{workflow_type}", status="error", error=str(exc))
        return False


def run_tiktok_unfollow(conn, device, ipc, limits):
    """Run TikTok unfollow workflow."""
    try:
        from taktik.core.social_media.tiktok.workflows.unfollow import UnfollowWorkflow

        max_unfollows = limits.get("maxUnfollows", 20)

        ipc.send("workflow_step", step="tiktok_unfollow", status="running")
        wf = UnfollowWorkflow(device)
        success = wf.run(max_unfollows=max_unfollows)
        ipc.send("workflow_step", step="tiktok_unfollow", status="done" if success else "failed")
        return success
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok unfollow failed: {exc}")
        ipc.send("workflow_step", step="tiktok_unfollow", status="error", error=str(exc))
        return False


def run_tiktok_publish(conn, device, ipc):
    """Run TikTok publish navigation test."""
    try:
        from taktik.core.social_media.tiktok.publish.navigator import TikTokPublishNavigator

        ipc.send("workflow_step", step="tiktok_upload_navigate", status="running")
        navigator = TikTokPublishNavigator(device)
        can_navigate = navigator.navigate_to_upload()
        ipc.send("workflow_step", step="tiktok_upload_navigate", status="done" if can_navigate else "failed")
        try:
            navigator.go_back()
        except Exception:
            pass
        return can_navigate
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok publish failed: {exc}")
        ipc.send("workflow_step", step="tiktok_upload", status="error", error=str(exc))
        return False


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


__all__ = [
    "run_instagram_dm",
    "run_instagram_publish",
    "run_instagram_scraping",
    "run_instagram_smart_comment",
    "run_tiktok_automation",
    "run_tiktok_dm",
    "run_tiktok_publish",
    "run_tiktok_scraping",
    "run_tiktok_unfollow",
]

