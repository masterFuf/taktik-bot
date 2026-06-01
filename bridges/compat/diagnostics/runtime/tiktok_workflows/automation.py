"""TikTok automation workflow-test runners."""

from loguru import logger


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
