#!/usr/bin/env python3
"""
Workflow Test Bridge — Runs a real Instagram workflow with selector instrumentation.

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
import json
import time
import traceback

# Bootstrap: ensure bot root is in sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.ipc import IPC
from bridges.common.connection import ConnectionService
from bridges.common.app_manager import AppService
from loguru import logger
from taktik.core.compat.selector_tracer import SelectorTracer


# Module-level watchdog reference — set before workflow run so hooks can feed heartbeats
_active_watchdog = None
# Module-level tracer reference — used by log sink for screen context detection
_active_tracer: SelectorTracer | None = None
# Module-level last stats snapshot — captured from BaseStatsManager callback
_last_stats: dict | None = None


# ──────────────────────────────────────────────────────────────
# Screen context inference from log messages (zero-overhead)
# ──────────────────────────────────────────────────────────────

# Ordered list of (pattern, screen_name). First match wins.
_SCREEN_PATTERNS = [
    # Followers / Following list
    ("Recovered to followers list", "followers_list"),
    ("Followers list opened", "followers_list"),
    ("followers list", "followers_list"),
    ("Following list opened", "following_list"),
    ("following list", "following_list"),
    ("clickable followers found", "followers_list"),
    ("Detecting Followers list", "followers_list"),
    # Post / Reel view
    ("Post view detected", "post_view"),
    ("First post opened", "post_view"),
    ("post opened", "post_view"),
    ("Reel post", "post_view"),
    ("Post liked", "post_view"),
    ("Navigating to next post", "post_view"),
    ("Clicking Like button", "post_view"),
    ("Detecting Liked button", "post_view"),
    ("Detecting Post screen", "post_view"),
    # Story viewer
    ("Story viewer", "story_viewer"),
    ("story viewer", "story_viewer"),
    # Profile (target)
    ("Profile screen detected", "target_profile"),
    ("Profile extracted", "target_profile"),
    ("Batch profile flags", "target_profile"),
    ("Batch text:", "target_profile"),
    ("Complete profile data", "target_profile"),
    ("Profile image extracted", "target_profile"),
    ("Clicking on @", "navigating_to_profile"),
    # Own profile
    ("Confirmed: on own profile", "own_profile"),
    ("own profile", "own_profile"),
    # Home / Search
    ("Home screen", "home"),
    ("Search screen", "search"),
    # Navigation back
    ("Recovery - clicking back", "navigating_back"),
    # Comment
    ("Comment button clicked", "comment_input"),
    ("Comment field", "comment_input"),
    ("Attempting to comment", "post_view"),
]


def _infer_screen_from_log(text: str) -> str | None:
    """Return the screen name inferred from a log message, or None if no match."""
    for pattern, screen in _SCREEN_PATTERNS:
        if pattern in text:
            return screen
    return None


def _setup_log_sink(ipc: IPC):
    """Add a loguru sink that streams every log line to the renderer via IPC."""
    def _ipc_sink(message):
        record = message.record
        msg_text = str(message).rstrip()
        ipc.send("log", 
                 level=record["level"].name.lower(),
                 text=msg_text,
                 module=record.get("name", ""),
                 function=record.get("function", ""),
                 ts=record["time"].strftime("%H:%M:%S.%f")[:-3])
        # Feed watchdog heartbeat on meaningful logs (not debug noise)
        if _active_watchdog and record["level"].name.upper() in ("INFO", "SUCCESS", "WARNING"):
            _active_watchdog.heartbeat(msg_text[:80])
        # Infer screen context from log messages (zero-overhead: string matching only)
        if _active_tracer:
            screen = _infer_screen_from_log(msg_text)
            if screen:
                _active_tracer.set_screen(screen)
    logger.add(_ipc_sink, level="DEBUG", format="{message}")


def _setup_action_hooks(ipc: IPC):
    """Monkey-patch IPCEmitter + stats callback to route action events via compat IPC."""
    try:
        from taktik.core.social_media.instagram.actions.core.ipc.emitter import IPCEmitter

        # Replace IPCEmitter static methods to send via compat IPC
        @staticmethod
        def _emit_follow(username, success=True, profile_data=None):
            ipc.send("action_event", action="follow", username=username, 
                     success=success, data={"followers": (profile_data or {}).get("followers_count")})
            if _active_watchdog:
                _active_watchdog.heartbeat(f"follow @{username}")

        @staticmethod
        def _emit_like(username, likes_count=1, profile_data=None):
            ipc.send("action_event", action="like", username=username,
                     success=True, data={"count": likes_count})
            if _active_watchdog:
                _active_watchdog.heartbeat(f"like {likes_count}x @{username}")

        @staticmethod
        def _emit_profile_visit(username):
            ipc.send("action_event", action="profile_visit", username=username, success=True, data={})
            if _active_watchdog:
                _active_watchdog.heartbeat(f"visit @{username}")

        @staticmethod
        def _emit_action(action_type, username, data=None):
            ipc.send("action_event", action=action_type, username=username, success=True, data=data or {})
            if _active_watchdog:
                _active_watchdog.heartbeat(f"{action_type} @{username}")

        @staticmethod
        def _emit_profile_captured(username, profile_data=None, profile_pic_base64=None):
            ipc.send("action_event", action="profile_captured", username=username, success=True,
                     data={"full_name": (profile_data or {}).get("full_name")})
            if _active_watchdog:
                _active_watchdog.heartbeat(f"profile @{username}")

        IPCEmitter.emit_follow = _emit_follow
        IPCEmitter.emit_like = _emit_like
        IPCEmitter.emit_profile_visit = _emit_profile_visit
        IPCEmitter.emit_action = _emit_action
        IPCEmitter.emit_profile_captured = _emit_profile_captured

        logger.info("[WorkflowTest] IPCEmitter patched for compat action events")
    except Exception as e:
        logger.warning(f"[WorkflowTest] Could not patch IPCEmitter: {e}")

    # Stats callback → sends cumulative stats via IPC
    try:
        from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager

        original_init = BaseStatsManager.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            def _on_stats(stats_dict):
                ipc.send("instagram_stats", stats=stats_dict)
            self.set_on_stats_callback(_on_stats)

        BaseStatsManager.__init__ = patched_init
        logger.info("[WorkflowTest] BaseStatsManager patched for compat stats")
    except Exception as e:
        logger.warning(f"[WorkflowTest] Could not patch BaseStatsManager: {e}")

    # Also capture latest stats snapshot for final report
    try:
        from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager as BSM
        original_send = BSM._send_stats_update

        def patched_send(self):
            original_send(self)
            global _last_stats
            try:
                _last_stats = self.get_summary()
            except Exception:
                pass

        BSM._send_stats_update = patched_send
    except Exception:
        pass


# Default test configs per workflow type
DEFAULT_CONFIGS = {
    "target_followers": {
        "limits": {"maxProfiles": 3, "maxLikesPerProfile": 1},
        "probabilities": {"like": 80, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0},
    },
    "hashtag": {
        "limits": {"maxProfiles": 3, "maxLikesPerProfile": 1},
        "probabilities": {"like": 80, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0},
    },
    "feed": {
        "limits": {"maxProfiles": 3, "maxLikesPerProfile": 1},
        "probabilities": {"like": 80, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0},
    },
}


def main():
    ipc = IPC()

    # Parse config
    if len(sys.argv) < 2:
        ipc.send("error", error="No config file provided", error_code="MISSING_CONFIG")
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        ipc.send("error", error=f"Failed to read config: {e}", error_code="CONFIG_ERROR")
        sys.exit(1)

    device_id = config.get("device_id", "")
    app_name = config.get("app", "instagram")
    version = config.get("version", "")
    workflow_type = config.get("workflow", "target_followers")
    target = config.get("target", "")
    user_limits = config.get("limits", {})
    user_probs = config.get("probabilities", {})
    session_duration = config.get("session_duration", 30)
    delays = config.get("delays", {"min": 3, "max": 8})

    if not device_id:
        ipc.send("error", error="No device_id provided", error_code="MISSING_DEVICE")
        sys.exit(1)

    if not target and workflow_type in ("target_followers", "target_following", "hashtag"):
        ipc.send("error", error="No target provided for this workflow", error_code="MISSING_TARGET")
        sys.exit(1)

    # Merge with defaults
    defaults = DEFAULT_CONFIGS.get(workflow_type, DEFAULT_CONFIGS["target_followers"])
    limits = {**defaults["limits"], **user_limits}
    probs = {**defaults["probabilities"], **user_probs}

    # Start streaming logs + action events via IPC
    _setup_log_sink(ipc)
    _setup_action_hooks(ipc)

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
    # Step 2: Launch Instagram
    # ------------------------------------------------------------------
    ipc.send("step", step="launch", status="running", message="Launching Instagram...")
    app_service = AppService(conn, platform="instagram")
    if not app_service.is_installed():
        ipc.send("error", error="Instagram is not installed", error_code="APP_NOT_INSTALLED")
        sys.exit(1)
    if not app_service.launch():
        ipc.send("error", error="Failed to launch Instagram", error_code="APP_LAUNCH_FAILED")
        sys.exit(1)
    ipc.send("step", step="launch", status="done", message="Instagram launched")

    # ------------------------------------------------------------------
    # Step 3: Initialize automation + attach tracer
    # ------------------------------------------------------------------
    ipc.send("step", step="init_automation", status="running", message="Initializing automation engine...")
    try:
        from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
        from taktik.core.database import configure_db_service
        configure_db_service()

        automation = InstagramAutomation(conn.device_manager)

        # Create the SelectorTracer with real-time IPC callback
        def _on_xpath(call):
            ipc.send("selector_event",
                     xpath=call.xpath,
                     found=call.found,
                     elapsed_ms=call.elapsed_ms,
                     step=call.step,
                     error=call.error,
                     screen=call.screen)

        tracer = SelectorTracer(on_xpath_call=_on_xpath)
        tracer.attach(automation.device)

        global _active_tracer
        _active_tracer = tracer

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
        from taktik.core.compat.setup import apply_version_overrides
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
    # Step 3c: Detect app language and optimize selectors
    # ------------------------------------------------------------------
    ipc.send("step", step="language_detect", status="running", message="Detecting app language...")
    try:
        from taktik.core.social_media.instagram.ui.language import detect_and_optimize
        detected_lang = detect_and_optimize(automation.device)
        ipc.send("step", step="language_detect", status="done",
                 message=f"Language: {detected_lang.upper()}")
        ipc.send("action_event", action="language_detected", username="",
                 success=True, data={"language": detected_lang})
    except Exception as e:
        logger.warning(f"Language detection failed (non-fatal): {e}")
        ipc.send("step", step="language_detect", status="done",
                 message="Language: unknown (detection failed)")

    # ------------------------------------------------------------------
    # Step 4: Build workflow config and run (with watchdog)
    # ------------------------------------------------------------------
    ipc.send("step", step="run_workflow", status="running",
             message=f"Running {workflow_type} workflow (target={target})...")

    workflow_config = _build_workflow_config(workflow_type, target, limits, probs, session_duration, delays)
    automation.config = workflow_config

    # Start the watchdog to detect stuck states and auto-recover
    global _active_watchdog
    watchdog = None
    try:
        from taktik.core.social_media.instagram.ui.watchdog import WorkflowWatchdog
        watchdog = WorkflowWatchdog(
            automation.device,
            ipc=ipc,
            stuck_timeout=90,
            check_interval=15,
            max_recoveries=5,
        )
        _active_watchdog = watchdog
        watchdog.start()
        ipc.send("action_event", action="watchdog_started", username="",
                 success=True, data={"timeout": 90})
    except Exception as e:
        logger.warning(f"[WorkflowTest] Could not start watchdog (non-fatal): {e}")

    workflow_success = False
    workflow_error = None
    start_time = time.time()

    try:
        # Instrument the WorkflowRunner to track steps
        _instrument_workflow_runner(automation, tracer, ipc)

        automation.run_workflow()
        workflow_success = True
    except Exception as e:
        workflow_error = str(e)
        logger.exception(f"Workflow error: {e}")
        ipc.send("step", step="run_workflow", status="error", message=f"Workflow error: {e}")

    # Stop watchdog
    if watchdog:
        try:
            watchdog.stop()
            _active_watchdog = None
            ipc.send("action_event", action="watchdog_stopped", username="",
                     success=True, data=watchdog.stats)
        except Exception:
            _active_watchdog = None

    elapsed_s = round(time.time() - start_time, 1)

    # ------------------------------------------------------------------
    # Step 5: Generate report
    # ------------------------------------------------------------------
    ipc.send("step", step="report", status="running", message="Generating compatibility report...")

    tracer.detach()
    report = tracer.report()

    # Compute expected results from config
    import math
    max_profiles = limits.get("maxProfiles", limits.get("maxInteractions", limits.get("maxUnfollows", 0)))
    max_likes_pp = limits.get("maxLikesPerProfile", 0)
    like_pct = probs.get("like", 0)
    follow_pct = probs.get("follow", 0)
    comment_pct = probs.get("comment", 0)
    story_pct = probs.get("watchStories", 0)

    expected_results = {
        "profiles": max_profiles,
        "likes": math.ceil(max_profiles * max_likes_pp * like_pct / 100) if like_pct and max_likes_pp else 0,
        "follows": math.ceil(max_profiles * follow_pct / 100) if follow_pct else 0,
        "comments": math.ceil(max_profiles * comment_pct / 100) if comment_pct else 0,
        "stories": math.ceil(max_profiles * story_pct / 100) if story_pct else 0,
    }

    # Capture actual results from stats manager
    actual_results = {
        "profiles_visited": 0,
        "profiles_interacted": 0,
        "likes": 0,
        "follows": 0,
        "comments": 0,
        "stories_watched": 0,
        "errors": 0,
    }
    if _last_stats:
        actual_results = {
            "profiles_visited": _last_stats.get("profiles_visited", 0),
            "profiles_interacted": _last_stats.get("profiles_interacted", 0),
            "likes": _last_stats.get("likes", 0),
            "follows": _last_stats.get("follows", 0),
            "comments": _last_stats.get("comments", 0),
            "stories_watched": _last_stats.get("stories_watched", 0),
            "errors": _last_stats.get("errors", 0),
        }

    # Determine functional success: did the bot achieve what was asked?
    functional_success = workflow_success
    functional_notes = []
    if expected_results["profiles"] > 0 and actual_results["profiles_interacted"] == 0:
        functional_success = False
        functional_notes.append("No profiles interacted")
    if expected_results["likes"] > 0 and actual_results["likes"] == 0:
        functional_success = False
        functional_notes.append("No likes performed")

    # Enrich report with workflow metadata
    report["workflow"] = {
        "type": workflow_type,
        "target": target,
        "success": workflow_success,
        "error": workflow_error,
        "elapsed_seconds": elapsed_s,
        "limits": limits,
        "probabilities": probs,
        "session_duration": session_duration,
        "delays": delays,
    }
    report["expected_results"] = expected_results
    report["actual_results"] = actual_results
    report["functional"] = {
        "success": functional_success,
        "notes": functional_notes,
    }
    report["app"] = app_name
    report["version"] = version
    report["device_id"] = device_id

    # Send final report
    ipc.send("test_report", **report)

    # Summary status
    score = report.get("compatibility_score", 0)
    status = "passed" if score >= 80 and workflow_success else "failed"
    ipc.send("status", status=status,
             message=f"Score: {score}% | {report['unique_xpaths_found']}/{report['unique_xpaths']} selectors | {elapsed_s}s")

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
    elif workflow_type == "feed":
        action_type = "feed"
        interaction_type = "feed"
        session_wf_type = "feed"
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


def _instrument_workflow_runner(automation, tracer: SelectorTracer, ipc: IPC):
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
