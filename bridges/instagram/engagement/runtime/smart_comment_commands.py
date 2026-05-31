"""CLI command handling for the Instagram Smart Comment bridge."""

from __future__ import annotations

import json
import sys
import time

from bridges.instagram.runtime.ipc import logger, send_message as send_event


def run_smart_comment_cli(args: list[str]) -> None:
    """Load config and run the requested Smart Comment bridge mode."""
    if len(args) < 1:
        print(json.dumps({"success": False, "error": "No config file provided"}))
        sys.exit(1)

    config_path = args[0]

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to load config: {e}"}))
        sys.exit(1)

    device_id = config.get("deviceId")
    if not device_id:
        print(json.dumps({"success": False, "error": "No deviceId provided"}))
        sys.exit(1)

    mode = config.get("mode", "scrape")
    package_name = config.get("packageName")

    from bridges.instagram.engagement.smart_comment import SmartCommentBridge

    bridge = SmartCommentBridge(device_id, config, package_name=package_name)

    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        sys.exit(1)

    if mode == "scrape":
        result = bridge.run_scrape()
        print(json.dumps(result, ensure_ascii=False))
        return

    if mode == "reply_all":
        _run_reply_all(bridge, config)
        return

    print(json.dumps({"success": False, "error": f"Unknown mode: {mode}"}))
    sys.exit(1)


def _run_reply_all(bridge, config: dict) -> None:
    qualified = config.get("qualifiedComments", [])
    if not qualified:
        print(json.dumps({"success": False, "error": "No qualified comments provided"}))
        sys.exit(1)

    post_url = config.get("postUrl", "").strip()
    target_username = config.get("targetUsername", "").strip().lstrip("@")

    if not post_url and not target_username:
        print(json.dumps({"success": False, "error": "No postUrl or targetUsername provided for reply mode"}))
        sys.exit(1)

    send_event("reply_progress", current=0, total=len(qualified), username="", status="Navigating to post...")
    logger.info(f"Reply mode: navigating to post (url={post_url or 'none'}, target=@{target_username or 'none'})...")

    bridge.restart_instagram()

    navigated = False
    if post_url:
        logger.info(f"Using post URL for precise navigation: {post_url}")
        if bridge.navigate_to_post_url(post_url):
            navigated = True
        else:
            logger.warning("Post URL navigation failed, trying profile fallback...")

    if not navigated and target_username:
        if not bridge._navigate_via_profile(target_username):
            print(json.dumps({"success": False, "error": f"Could not find the target post on @{target_username}'s profile"}))
            sys.exit(1)
        navigated = True

    if not navigated:
        print(json.dumps({"success": False, "error": "Could not navigate to the target post"}))
        sys.exit(1)

    if not bridge.open_comments():
        print(json.dumps({"success": False, "error": "Could not open comments"}))
        sys.exit(1)

    try:
        title = bridge.device(resourceId="com.instagram.android:id/title_text_view")
        if title.exists:
            title.click()
            time.sleep(1)
    except Exception:
        pass

    time.sleep(1)

    result = bridge.run_reply(qualified)
    print(json.dumps(result, ensure_ascii=False))
