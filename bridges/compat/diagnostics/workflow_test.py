#!/usr/bin/env python3
"""
Workflow Test Bridge â€” Runs a real Instagram workflow with selector instrumentation.

Launches a full workflow (target_followers, hashtag, feed, etc.) on the connected device,
with the SelectorTracer attached to record every XPath call. At the end, generates a
compatibility report showing which selectors worked and which failed.

Config JSON (passed as argv[1] temp file):
  {
    "device_id": "CE7S00081E2148",
    "app": "instagram",
    "version": "417.0.0.54.77",
    "workflow": "target_followers",
    "target": "natgeo",
    "limits": {
      "maxProfiles": 3,
      "maxLikesPerProfile": 1
    },
    "probabilities": {
      "like": 80,
      "follow": 0,
      "comment": 0,
      "watchStories": 0,
      "likeStories": 0
    }
  }

Output: IPC messages with step-by-step progress and a final compatibility report.
"""

import sys
import os
import time
import traceback

# Bootstrap: ensure bot root is in sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.ipc import IPC
from bridges.common.device.connection import ConnectionService
from bridges.common.device.app_manager import AppService
from bridges.compat.diagnostics.runtime.workflow_catalog import (
    INSTAGRAM_AUTOMATION_WF,
    INSTAGRAM_DM_WF,
    INSTAGRAM_PUBLISH_WF,
    INSTAGRAM_SCRAPING_WF,
    TIKTOK_AUTOMATION_WF,
    TIKTOK_DM_WF,
    TIKTOK_SCRAPING_WF,
)
from bridges.compat.diagnostics.runtime.workflow_observability import (
    clear_active_watchdog,
    get_last_stats,
    set_active_tracer,
    set_active_watchdog,
    setup_action_hooks,
    setup_log_sink,
)
from bridges.compat.diagnostics.runtime.workflow_request import load_workflow_test_request
from bridges.compat.diagnostics.runtime.workflow_report import build_workflow_report
from loguru import logger


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Workflow runners per category (non-automation)
# Each returns True/False for success.
# They reuse the real workflow code from the bot with tracer attached.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays):
    """Run an Instagram scraping workflow (account, hashtag, post_url, e_story)."""
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
        ipc.send("action_event", action="scraping_complete", username=target,
                 success=count > 0, data={"count": count, "type": scrape_type})
        logger.info(f"[WorkflowTest] Scraping {scrape_type} complete: {count} results")
        return count > 0
    except Exception as e:
        logger.exception(f"[WorkflowTest] Scraping failed: {e}")
        ipc.send("workflow_step", step=f"scraping_{workflow_type}", status="error", error=str(e))
        return False


def _run_instagram_dm(conn, device, ipc, workflow_type, limits, delays):
    """Run an Instagram DM workflow (dm_response or dm_outreach)."""
    try:
        max_dms = limits.get("maxDMs", 10)

        if workflow_type == "dm_response":
            from taktik.core.social_media.instagram.engagement.dm.reader import DMReader
            ipc.send("workflow_step", step="dm_read", status="running")
            reader = DMReader(device)
            conversations = reader.read_conversations(max_conversations=max_dms)
            count = len(conversations) if conversations else 0
            ipc.send("workflow_step", step="dm_read", status="done")
            ipc.send("action_event", action="dm_read_complete", username="",
                     success=count > 0, data={"conversations": count})
            return count > 0

        elif workflow_type == "dm_outreach":
            from taktik.core.social_media.instagram.engagement.dm.outreach import DMOutreach
            ipc.send("workflow_step", step="dm_outreach", status="running")
            outreach = DMOutreach(device)
            sent = outreach.send_batch(max_dms=max_dms)
            ipc.send("workflow_step", step="dm_outreach", status="done")
            ipc.send("action_event", action="dm_outreach_complete", username="",
                     success=sent > 0, data={"sent": sent})
            return sent > 0

        return False
    except Exception as e:
        logger.exception(f"[WorkflowTest] DM workflow failed: {e}")
        ipc.send("workflow_step", step=workflow_type, status="error", error=str(e))
        return False


def _run_instagram_smart_comment(conn, device, ipc, target, limits, delays):
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
        ipc.send("action_event", action="smart_comment_complete", username=target or "",
                 success=success, data={"max_comments": max_comments})
        return success
    except Exception as e:
        logger.exception(f"[WorkflowTest] Smart comment failed: {e}")
        ipc.send("workflow_step", step="smart_comment", status="error", error=str(e))
        return False


def _run_instagram_publish(conn, device, ipc, workflow_type):
    """Run an Instagram publish workflow (post, carousel, reel, story).

    For compat testing, we test the navigation to the upload screen and
    verify the UI elements are reachable â€” we don't actually publish content.
    """
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
        ipc.send("workflow_step", step=f"publish_navigate_{upload_type}",
                 status="done" if can_navigate else "failed")
        ipc.send("action_event", action="publish_navigation", username="",
                 success=can_navigate, data={"type": upload_type})

        # Navigate back to home after test
        try:
            navigator.go_back_to_home()
        except Exception:
            pass

        return can_navigate
    except Exception as e:
        logger.exception(f"[WorkflowTest] Publish workflow failed: {e}")
        ipc.send("workflow_step", step=f"publish_{workflow_type}", status="error", error=str(e))
        return False



def _run_tiktok_automation(conn, device, ipc, workflow_type, target, limits, probs, delays):
    """Run a TikTok automation workflow (for_you, hashtag, target, followers)."""
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

        elif workflow_type == "hashtag":
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

        elif workflow_type == "target":
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

        elif workflow_type == "followers":
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
    except Exception as e:
        logger.exception(f"[WorkflowTest] TikTok automation failed: {e}")
        ipc.send("workflow_step", step=f"tiktok_{workflow_type}", status="error", error=str(e))
        return False


def _run_tiktok_dm(conn, device, ipc, workflow_type, limits):
    """Run a TikTok DM workflow (dm_read or dm_outreach)."""
    try:
        max_dms = limits.get("maxDMs", 10)

        if workflow_type == "dm_read":
            from taktik.core.social_media.tiktok.engagement.dm.reader import TikTokDMReader
            ipc.send("workflow_step", step="tiktok_dm_read", status="running")
            reader = TikTokDMReader(device)
            conversations = reader.read_conversations(max_conversations=max_dms)
            count = len(conversations) if conversations else 0
            ipc.send("workflow_step", step="tiktok_dm_read", status="done")
            ipc.send("action_event", action="tiktok_dm_read_complete", username="",
                     success=count > 0, data={"conversations": count})
            return count > 0

        elif workflow_type == "dm_outreach":
            from taktik.core.social_media.tiktok.engagement.dm.outreach import TikTokDMOutreach
            ipc.send("workflow_step", step="tiktok_dm_outreach", status="running")
            outreach = TikTokDMOutreach(device)
            sent = outreach.send_batch(max_dms=max_dms)
            ipc.send("workflow_step", step="tiktok_dm_outreach", status="done")
            ipc.send("action_event", action="tiktok_dm_outreach_complete", username="",
                     success=sent > 0, data={"sent": sent})
            return sent > 0

        return False
    except Exception as e:
        logger.exception(f"[WorkflowTest] TikTok DM failed: {e}")
        ipc.send("workflow_step", step=f"tiktok_{workflow_type}", status="error", error=str(e))
        return False


def _run_tiktok_unfollow(conn, device, ipc, limits):
    """Run TikTok unfollow workflow."""
    try:
        from taktik.core.social_media.tiktok.workflows.unfollow import UnfollowWorkflow
        max_unfollows = limits.get("maxUnfollows", 20)

        ipc.send("workflow_step", step="tiktok_unfollow", status="running")
        wf = UnfollowWorkflow(device)
        success = wf.run(max_unfollows=max_unfollows)
        ipc.send("workflow_step", step="tiktok_unfollow", status="done" if success else "failed")
        return success
    except Exception as e:
        logger.exception(f"[WorkflowTest] TikTok unfollow failed: {e}")
        ipc.send("workflow_step", step="tiktok_unfollow", status="error", error=str(e))
        return False


def _run_tiktok_publish(conn, device, ipc):
    """Run TikTok publish (upload post) â€” navigation test only."""
    try:
        from taktik.core.social_media.tiktok.publish.navigator import TikTokPublishNavigator
        ipc.send("workflow_step", step="tiktok_upload_navigate", status="running")
        navigator = TikTokPublishNavigator(device)
        can_navigate = navigator.navigate_to_upload()
        ipc.send("workflow_step", step="tiktok_upload_navigate",
                 status="done" if can_navigate else "failed")
        try:
            navigator.go_back()
        except Exception:
            pass
        return can_navigate
    except Exception as e:
        logger.exception(f"[WorkflowTest] TikTok publish failed: {e}")
        ipc.send("workflow_step", step="tiktok_upload", status="error", error=str(e))
        return False


def _run_tiktok_scraping(conn, device, ipc, workflow_type, target, limits):
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
        ipc.send("action_event", action="tiktok_scraping_complete", username=target,
                 success=count > 0, data={"count": count, "type": scrape_type})
        return count > 0
    except Exception as e:
        logger.exception(f"[WorkflowTest] TikTok scraping failed: {e}")
        ipc.send("workflow_step", step=f"tiktok_scraping_{workflow_type}", status="error", error=str(e))
        return False



def main():
    ipc = IPC()

    request = load_workflow_test_request(ipc, sys.argv)
    device_id = request.device_id
    app_name = request.app_name
    version = request.version
    workflow_type = request.workflow_type
    target = request.target
    limits = request.limits
    probs = request.probabilities
    session_duration = request.session_duration
    delays = request.delays

    # Start streaming logs + action events via IPC
    setup_log_sink(ipc)
    setup_action_hooks(ipc)

    logger.info(f"[WorkflowTest] device={device_id} app={app_name} v={version} workflow={workflow_type} target={target}")
    ipc.send("status", status="initializing", message="Initializing workflow test...")

    # ------------------------------------------------------------------
    # Step 1: Connect to device
    # ------------------------------------------------------------------
    ipc.send("step", step="connect", status="running", message=f"Connecting to {device_id}...")
    conn = ConnectionService(device_id)
    if not conn.connect():
        ipc.send("error", error=f"Failed to connect to {device_id}", error_code="CONNECTION_ERROR")
        sys.exit(1)
    ipc.send("step", step="connect", status="done", message="Connected")

    # ------------------------------------------------------------------
    # Step 2: Launch app (Instagram or TikTok)
    # ------------------------------------------------------------------
    platform_label = app_name.capitalize()
    ipc.send("step", step="launch", status="running", message=f"Launching {platform_label}...")
    app_service = AppService(conn, platform=app_name)
    if not app_service.is_installed():
        ipc.send("error", error=f"{platform_label} is not installed", error_code="APP_NOT_INSTALLED")
        sys.exit(1)
    if not app_service.launch():
        ipc.send("error", error=f"Failed to launch {platform_label}", error_code="APP_LAUNCH_FAILED")
        sys.exit(1)
    ipc.send("step", step="launch", status="done", message=f"{platform_label} launched")

    # ------------------------------------------------------------------
    # Step 3: Initialize automation + attach tracer
    # ------------------------------------------------------------------
    ipc.send("step", step="init_automation", status="running", message="Initializing automation engine...")

    # Create the SelectorTracer with real-time IPC callback
    def _on_xpath(call):
        ipc.send("selector_event",
                 xpath=call.xpath,
                 found=call.found,
                 elapsed_ms=call.elapsed_ms,
                 step=call.step,
                 error=call.error,
                 screen=call.screen)

    from taktik.core.compat.selectors.tracer import SelectorTracer

    tracer = SelectorTracer(on_xpath_call=_on_xpath)
    automation = None
    device = None

    try:
        from taktik.core.database import configure_db_service
        configure_db_service()

        if app_name == "instagram":
            from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
            automation = InstagramAutomation(conn.device_manager)
            device = automation.device
        elif app_name == "tiktok":
            # TikTok uses device_manager directly for most workflows
            device = conn.device_manager
        else:
            device = conn.device_manager

        tracer.attach(device)
        set_active_tracer(tracer)

        ipc.send("step", step="init_automation", status="done", message="Automation ready, tracer attached")
    except Exception as e:
        ipc.send("error", error=f"Automation init failed: {e}", error_code="AUTOMATION_INIT_ERROR")
        logger.exception("Automation init failed")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 3b: Apply version-specific selector overrides
    # ------------------------------------------------------------------
    ipc.send("step", step="version_overrides", status="running",
             message=f"Applying selector overrides for {app_name} v{version}...")
    try:
        from taktik.core.compat.selectors.setup import apply_version_overrides
        patched_count = apply_version_overrides(app_name, version)
        ipc.send("step", step="version_overrides", status="done",
                 message=f"Patched {patched_count} selector(s) for v{version}")
        if patched_count > 0:
            ipc.send("action_event", action="version_overrides_applied", username="",
                     success=True, data={"version": version, "patched": patched_count})
    except Exception as e:
        logger.warning(f"Version override failed (non-fatal): {e}")
        ipc.send("step", step="version_overrides", status="done",
                 message="Version overrides: skipped (error)")

    # ------------------------------------------------------------------
    # Step 3c: Detect app language and optimize selectors (Instagram only)
    # ------------------------------------------------------------------
    if app_name == "instagram":
        ipc.send("step", step="language_detect", status="running", message="Detecting app language...")
        try:
            from taktik.core.social_media.instagram.ui.language import detect_and_optimize
            detected_lang = detect_and_optimize(device)
            ipc.send("step", step="language_detect", status="done",
                     message=f"Language: {detected_lang.upper()}")
            ipc.send("action_event", action="language_detected", username="",
                     success=True, data={"language": detected_lang})
        except Exception as e:
            logger.warning(f"Language detection failed (non-fatal): {e}")
            ipc.send("step", step="language_detect", status="done",
                     message="Language: unknown (detection failed)")

    # ------------------------------------------------------------------
    # Step 4: Run the workflow (dispatch by platform + category)
    # ------------------------------------------------------------------
    ipc.send("step", step="run_workflow", status="running",
             message=f"Running {workflow_type} workflow (target={target})...")

    watchdog = None
    workflow_success = False
    workflow_error = None
    start_time = time.time()

    try:
        # â”€â”€ Instagram Automation workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if app_name == "instagram" and workflow_type in INSTAGRAM_AUTOMATION_WF:
            workflow_config = _build_workflow_config(workflow_type, target, limits, probs, session_duration, delays)
            automation.config = workflow_config

            # Start the watchdog to detect stuck states and auto-recover
            try:
                from taktik.core.social_media.instagram.ui.watchdog import WorkflowWatchdog
                watchdog = WorkflowWatchdog(
                    device, ipc=ipc,
                    stuck_timeout=90, check_interval=15, max_recoveries=5,
                )
                set_active_watchdog(watchdog)
                watchdog.start()
                ipc.send("action_event", action="watchdog_started", username="",
                         success=True, data={"timeout": 90})
            except Exception as e:
                logger.warning(f"[WorkflowTest] Could not start watchdog (non-fatal): {e}")

            _instrument_workflow_runner(automation, tracer, ipc)
            automation.run_workflow()
            workflow_success = True

        # â”€â”€ Instagram Scraping workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type in INSTAGRAM_SCRAPING_WF:
            tracer.begin_step(f"scraping:{workflow_type}")
            workflow_success = _run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ Instagram DM workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type in INSTAGRAM_DM_WF:
            tracer.begin_step(f"dm:{workflow_type}")
            workflow_success = _run_instagram_dm(conn, device, ipc, workflow_type, limits, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ Instagram Smart Comment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type == "smart_comment":
            tracer.begin_step("smart_comment")
            workflow_success = _run_instagram_smart_comment(conn, device, ipc, target, limits, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ Instagram Publish workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type in INSTAGRAM_PUBLISH_WF:
            tracer.begin_step(f"publish:{workflow_type}")
            workflow_success = _run_instagram_publish(conn, device, ipc, workflow_type)
            tracer.end_step(success=workflow_success)


        # â”€â”€ TikTok Automation workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type in TIKTOK_AUTOMATION_WF:
            tracer.begin_step(f"tiktok:{workflow_type}")
            workflow_success = _run_tiktok_automation(conn, device, ipc, workflow_type, target, limits, probs, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok DM workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type in TIKTOK_DM_WF:
            tracer.begin_step(f"tiktok_dm:{workflow_type}")
            workflow_success = _run_tiktok_dm(conn, device, ipc, workflow_type, limits)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok Unfollow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type == "unfollow":
            tracer.begin_step("tiktok:unfollow")
            workflow_success = _run_tiktok_unfollow(conn, device, ipc, limits)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok Publish â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type == "upload_post":
            tracer.begin_step("tiktok:upload_post")
            workflow_success = _run_tiktok_publish(conn, device, ipc)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok Scraping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type in TIKTOK_SCRAPING_WF:
            tracer.begin_step(f"tiktok_scraping:{workflow_type}")
            workflow_success = _run_tiktok_scraping(conn, device, ipc, workflow_type, target, limits)
            tracer.end_step(success=workflow_success)


        else:
            workflow_error = f"Unsupported workflow: {app_name}/{workflow_type}"
            ipc.send("step", step="run_workflow", status="error", message=workflow_error)

    except Exception as e:
        workflow_error = str(e)
        logger.exception(f"Workflow error: {e}")
        ipc.send("step", step="run_workflow", status="error", message=f"Workflow error: {e}")

    # Stop watchdog
    if watchdog:
        try:
            watchdog.stop()
            clear_active_watchdog()
            ipc.send("action_event", action="watchdog_stopped", username="",
                     success=True, data=watchdog.stats)
        except Exception:
            clear_active_watchdog()

    elapsed_s = round(time.time() - start_time, 1)

    # ------------------------------------------------------------------
    # Step 5: Generate report
    # ------------------------------------------------------------------
    ipc.send("step", step="report", status="running", message="Generating compatibility report...")

    tracer.detach()
    report, score, status, status_message = build_workflow_report(
        tracer,
        workflow_type=workflow_type,
        target=target,
        workflow_success=workflow_success,
        workflow_error=workflow_error,
        elapsed_s=elapsed_s,
        limits=limits,
        probs=probs,
        session_duration=session_duration,
        delays=delays,
        app_name=app_name,
        version=version,
        device_id=device_id,
        last_stats=get_last_stats(),
    )

    # Send final report
    ipc.send("test_report", **report)

    # Summary status
    ipc.send("status", status=status, message=status_message)

    conn.disconnect()
    logger.info(f"[WorkflowTest] Done: score={score}%, workflow_success={workflow_success}")


def _build_workflow_config(workflow_type: str, target: str, limits: dict, probs: dict, session_duration: int = 30, delays: dict = None) -> dict:
    """Build a workflow config matching the format expected by InstagramAutomation."""
    import math

    max_profiles = limits.get("maxProfiles", 3)
    max_likes = limits.get("maxLikesPerProfile", 1)
    like_pct = probs.get("like", 80)
    follow_pct = probs.get("follow", 0)
    comment_pct = probs.get("comment", 0)
    story_pct = probs.get("watchStories", 0)
    story_like_pct = probs.get("likeStories", 0)

    # Determine action type
    if workflow_type in ("target_followers", "target_following"):
        action_type = "interact_with_followers"
        interaction_type = "followers" if workflow_type == "target_followers" else "following"
        session_wf_type = "target_followers"
    elif workflow_type == "hashtag":
        action_type = "hashtag"
        interaction_type = "hashtag"
        session_wf_type = "hashtag"
    elif workflow_type in ("post_likers", "post_url"):
        action_type = "post_url"
        interaction_type = "post_likers"
        session_wf_type = "post_url"
    elif workflow_type == "feed":
        action_type = "feed"
        interaction_type = "feed"
        session_wf_type = "feed"
    elif workflow_type == "notifications":
        action_type = "notifications"
        interaction_type = "notifications"
        session_wf_type = "notifications"
    elif workflow_type == "unfollow":
        action_type = "unfollow"
        interaction_type = "unfollow"
        session_wf_type = "unfollow"
    else:
        action_type = "interact_with_followers"
        interaction_type = "followers"
        session_wf_type = "target_followers"

    target_list = [t.strip() for t in target.split(",") if t.strip()]

    action_config = {
        "type": action_type,
        "target_username": target_list[0] if target_list else target,
        "target_usernames": target_list,
        "hashtag": target if action_type == "hashtag" else None,
        "interaction_type": interaction_type,
        "max_interactions": max_profiles,
        "like_posts": True,
        "max_likes_per_profile": max_likes,
        "probabilities": {
            "like_percentage": like_pct,
            "follow_percentage": follow_pct,
            "comment_percentage": comment_pct,
            "story_percentage": story_pct,
            "story_like_percentage": story_like_pct,
        },
        "like_settings": {"enabled": like_pct > 0, "like_carousels": True, "like_reels": True},
        "follow_settings": {"enabled": follow_pct > 0},
        "story_settings": {"enabled": story_pct > 0},
        "story_like_settings": {"enabled": story_like_pct > 0},
        "comment_settings": {"enabled": comment_pct > 0, "custom_comments": []},
    }

    if action_type == "feed":
        action_config = {
            "type": "feed",
            "max_interactions": max_profiles,
            "like_percentage": like_pct,
            "follow_percentage": follow_pct,
            "comment_percentage": comment_pct,
            "story_watch_percentage": story_pct,
        }
    elif action_type == "notifications":
        action_config = {
            "type": "notifications",
            "max_interactions": limits.get("maxInteractions", max_profiles),
            "like_percentage": like_pct,
            "follow_percentage": follow_pct,
            "comment_percentage": comment_pct,
        }
    elif action_type == "unfollow":
        max_unfollows = limits.get("maxUnfollows", 10)
        action_config = {
            "type": "unfollow",
            "max_unfollows": max_unfollows,
            "unfollow_mode": "non_followers",
            "skip_verified": False,
            "skip_business": False,
        }
    elif action_type == "post_url":
        action_config["type"] = "post_url"
        action_config["post_url"] = target

    return {
        "filters": {
            "min_followers": 0,
            "max_followers": 999999999,
            "min_followings": 0,
            "max_followings": 999999999,
            "min_posts": 0,
            "privacy_relation": "public_and_private",
            "blacklist_words": [],
        },
        "session_settings": {
            "workflow_type": session_wf_type,
            "total_profiles_limit": max_profiles,
            "total_follows_limit": math.ceil(max_profiles * follow_pct / 100) if follow_pct else 0,
            "total_likes_limit": math.ceil(max_profiles * max_likes * like_pct / 100) if like_pct else 0,
            "session_duration_minutes": session_duration,
            "delay_between_actions": delays or {"min": 3, "max": 8},
            "randomize_actions": False,
        },
        "actions": [action_config],
    }


def _instrument_workflow_runner(automation, tracer, ipc: IPC):
    """Monkey-patch WorkflowRunner.run_workflow_step to track steps in the tracer."""
    runner = automation.workflow_runner
    original_run_step = runner.run_workflow_step

    def instrumented_run_step(action):
        action_type = action.get("type", "unknown")
        step_name = action.get("id", action_type)

        tracer.begin_step(step_name)
        ipc.send("workflow_step", step=step_name, status="running")

        try:
            result = original_run_step(action)
            tracer.end_step(success=result)
            ipc.send("workflow_step", step=step_name, status="done" if result else "failed")
            return result
        except Exception as e:
            tracer.end_step(success=False, error=str(e))
            ipc.send("workflow_step", step=step_name, status="error", error=str(e))
            raise

    runner.run_workflow_step = instrumented_run_step


if __name__ == "__main__":
    main()
