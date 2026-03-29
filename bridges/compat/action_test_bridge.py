"""
Action Test Bridge — Manual action testing from the Debug Panel.

Receives a JSON config with:
  {
    "device_id": "...",
    "action_id": "...",   # e.g. "popup.close_comment", "follow.follow_user"
    "params": {}          # optional action-specific params
  }

Outputs JSON lines to stdout:
  {"type": "log",    "level": "info|debug|warning|error", "message": "..."}
  {"type": "result", "success": true|false, "message": "..."}
"""

import sys
import io
import json
import time
import traceback
from loguru import logger

# Force UTF-8 on Windows to avoid UnicodeEncodeError with emojis
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── Logger setup ──────────────────────────────────────────────────────────────
logger.remove()

def _emit(obj: dict):
    print(json.dumps(obj, ensure_ascii=False), flush=True)

def _log(level: str, message: str):
    _emit({"type": "log", "level": level, "message": message})

logger.add(
    lambda msg: _log(msg.record["level"].name.lower(), msg.record["message"]),
    format="{message}",
    level="DEBUG",
)

# ── Action registry ───────────────────────────────────────────────────────────
# Each action is a function: (action_instance, params) -> bool

ACTION_REGISTRY: dict = {}

def _action(action_id: str):
    """Decorator to register an action."""
    def decorator(fn):
        ACTION_REGISTRY[action_id] = fn
        return fn
    return decorator


# =============================================================================
# FAMILY: popups
# =============================================================================

@_action("popups.is_comment_open")
def check_comment_popup(a, p):
    result = a.comment._is_comments_view_open()
    logger.info(f"Comment popup open: {result}")
    return result

@_action("popups.close_comment")
def close_comment_popup(a, p):
    return a.comment._close_comment_popup()

@_action("popups.is_likers_open")
def check_likers_popup(a, p):
    result = a.click._is_likers_popup_open()
    logger.info(f"Likers popup open: {result}")
    return result

@_action("popups.close_likers")
def close_likers_popup(a, p):
    a.click._close_likers_popup()
    return not a.click._is_likers_popup_open()

@_action("popups.close_by_swipe")
def close_popup_swipe(a, p):
    return a.click._close_popup_by_swipe_down()

@_action("popups.close_follow_suggestions")
def close_follow_suggestions(a, p):
    a.click._handle_follow_suggestions_popup()
    return True

@_action("popups.press_back")
def press_back(a, p):
    a.device.press("back")
    time.sleep(0.8)
    return True


# =============================================================================
# FAMILY: detection
# =============================================================================

@_action("detection.is_home_screen")
def is_home_screen(a, p):
    result = a.detection.is_on_home_screen()
    logger.info(f"Home screen: {result}")
    return result

@_action("detection.is_profile_screen")
def is_profile_screen(a, p):
    result = a.detection.is_on_profile_screen()
    logger.info(f"Profile screen: {result}")
    return result

@_action("detection.is_post_open")
def is_post_open(a, p):
    result = a.detection.is_on_post_screen()
    logger.info(f"Post open: {result}")
    return result

@_action("detection.get_current_screen")
def get_current_screen(a, p):
    try:
        app = a.device._device.app_current()
        logger.info(f"Current app: {app.get('package')} / activity: {app.get('activity')}")
    except Exception as e:
        logger.error(f"Could not get current app: {e}")
    return True

@_action("detection.dump_xml")
def dump_xml(a, p):
    try:
        xml = a.device.get_xml_dump()
        if xml:
            preview = xml[:2000] + ("..." if len(xml) > 2000 else "")
            logger.info(f"XML dump preview ({len(xml)} chars):\n{preview}")
        else:
            logger.warning("XML dump returned empty")
    except Exception as e:
        logger.error(f"XML dump failed: {e}")
    return True

@_action("detection.screenshot")
def take_screenshot(a, p):
    import os, tempfile
    path = os.path.join(tempfile.gettempdir(), "taktik_debug", f"action_test_{int(time.time())}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = a.device.screenshot(path)
    if result:
        logger.info(f"Screenshot saved: {path}")
    else:
        logger.error("Screenshot failed")
    return result


# =============================================================================
# FAMILY: navigation
# =============================================================================

@_action("navigation.go_home")
def go_home(a, p):
    return a.nav.navigate_to_home()

@_action("navigation.go_search")
def go_search(a, p):
    return a.nav.navigate_to_search()

@_action("navigation.go_profile_tab")
def go_profile_tab(a, p):
    return a.nav.navigate_to_profile_tab()

@_action("navigation.open_profile")
def open_profile(a, p):
    username = p.get("username", "")
    if not username:
        logger.error("Missing 'username' param")
        return False
    return a.nav.navigate_to_profile(username)

@_action("navigation.press_back")
def nav_back(a, p):
    count = int(p.get("count", 1))
    for i in range(count):
        a.device.press("back")
        time.sleep(0.6)
    return True

@_action("navigation.go_home_button")
def go_home_button(a, p):
    a.device.home()
    time.sleep(1)
    return True


# =============================================================================
# FAMILY: profile
# =============================================================================

@_action("profile.click_follow")
def click_follow(a, p):
    return a.click.click_follow_button()

@_action("profile.click_unfollow")
def click_unfollow(a, p):
    return a.click.click_unfollow_button()

@_action("profile.is_follow_available")
def is_follow_available(a, p):
    result = a.click.is_follow_button_available()
    logger.info(f"Follow button available: {result}")
    return result

@_action("profile.is_unfollow_available")
def is_unfollow_available(a, p):
    result = a.click.is_unfollow_button_available()
    logger.info(f"Unfollow button available: {result}")
    return result

@_action("profile.click_followers_count")
def click_followers(a, p):
    return a.click.click_followers_count()

@_action("profile.click_following_count")
def click_following(a, p):
    return a.click.click_following_count()

@_action("profile.click_message_button")
def click_message(a, p):
    return a.click.click_message_button()


# =============================================================================
# FAMILY: post
# =============================================================================

@_action("post.like")
def like_post(a, p):
    return a.click.like_post()

@_action("post.unlike")
def unlike_post(a, p):
    return a.click.unlike_post()

@_action("post.click_comment_button")
def click_comment_btn(a, p):
    return a.click.click_comment_button()

@_action("post.click_share_button")
def click_share(a, p):
    return a.click.click_share_button()

@_action("post.click_save_button")
def click_save(a, p):
    return a.click.click_save_button()

@_action("post.click_likes_count")
def click_likes_count(a, p):
    return a.click.click_likes_count()

@_action("post.is_liked")
def is_liked(a, p):
    result = a.click.is_post_already_liked()
    logger.info(f"Post liked: {result}")
    return result


# =============================================================================
# FAMILY: comment
# =============================================================================

@_action("comment.open_and_type")
def comment_open_and_type(a, p):
    text = p.get("text", "Test comment 🤖")
    if not a.click.click_comment_button():
        logger.error("Could not open comment box")
        return False
    time.sleep(0.8)
    a.comment._type_comment(text)
    logger.info(f"Typed comment: '{text}'")
    return True

@_action("comment.post_comment")
def post_comment(a, p):
    return a.comment._post_comment()

@_action("comment.close_popup")
def close_comment(a, p):
    return a.comment._close_comment_popup()


# =============================================================================
# FAMILY: scroll
# =============================================================================

@_action("scroll.up")
def scroll_up(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_up(scale=scale)
    return True

@_action("scroll.down")
def scroll_down(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_down(scale=scale)
    return True

@_action("scroll.left")
def scroll_left(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_left(scale=scale)
    return True

@_action("scroll.right")
def scroll_right(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_right(scale=scale)
    return True


# =============================================================================
# FAMILY: story
# =============================================================================

@_action("story.like")
def like_story(a, p):
    return a.click.click_story_like_button()

@_action("story.go_to_next")
def story_next(a, p):
    return a.nav.navigate_to_next_story()

@_action("story.go_to_previous")
def story_prev(a, p):
    a.device.swipe_right()
    return True

@_action("story.close")
def story_close(a, p):
    a.device.press("back")
    time.sleep(0.5)
    return True


# =============================================================================
# FAMILY: keyboard
# =============================================================================

@_action("keyboard.press_enter")
def kb_enter(a, p):
    return a.kb.press_enter()

@_action("keyboard.press_back")
def kb_back(a, p):
    a.device.press("back")
    return True

@_action("keyboard.hide")
def kb_hide(a, p):
    return a.kb.hide_keyboard()

@_action("keyboard.type_text")
def kb_type(a, p):
    text = p.get("text", "hello")
    return a.kb.type_text(text)


# =============================================================================
# Action runner setup
# =============================================================================

class ActionBundle:
    """Holds all action instances grouped by family."""
    pass


def _build_action_bundle(device_facade):
    """Instantiate each atomic action class separately and wire them into a bundle."""
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
    from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions
    from taktik.core.social_media.instagram.actions.atomic.scroll import ScrollActions
    from taktik.core.social_media.instagram.actions.atomic.text import TextActions
    from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction

    logger.info("Building action bundle...")
    bundle = ActionBundle()
    bundle.device   = device_facade
    bundle.nav      = NavigationActions(device_facade)
    bundle.detection = DetectionActions(device_facade)
    bundle.click    = ClickActions(device_facade)
    bundle.scroll   = ScrollActions(device_facade)
    bundle.kb       = TextActions(device_facade)
    bundle.comment  = CommentAction(device_facade)
    logger.info("Action bundle ready")
    return bundle


# =============================================================================
# Main entry point
# =============================================================================

def main():
    if len(sys.argv) < 2:
        _emit({"type": "result", "success": False, "message": "No config file provided"})
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except Exception as e:
        _emit({"type": "result", "success": False, "message": f"Failed to read config: {e}"})
        sys.exit(1)

    device_id = config.get("device_id", "")
    action_id = config.get("action_id", "")
    params = config.get("params", {})

    if not device_id:
        _emit({"type": "result", "success": False, "message": "Missing device_id"})
        sys.exit(1)

    if not action_id:
        _emit({"type": "result", "success": False, "message": "Missing action_id"})
        sys.exit(1)

    if action_id not in ACTION_REGISTRY:
        _emit({"type": "result", "success": False, "message": f"Unknown action: '{action_id}'. Available: {sorted(ACTION_REGISTRY.keys())}"})
        sys.exit(1)

    # Connect to device
    logger.info(f"Connecting to device: {device_id}")
    try:
        from taktik.core.device.device import DeviceManager
        device_manager = DeviceManager()
        raw_device = device_manager.connect_to_device(device_id)

        if not raw_device:
            _emit({"type": "result", "success": False, "message": f"Could not connect to device {device_id}"})
            sys.exit(1)

        logger.info(f"Connected to {device_id}")
    except Exception as e:
        _emit({"type": "result", "success": False, "message": f"Device connection failed: {e}"})
        sys.exit(1)

    # Build action bundle — pass the raw u2 device wrapped in DeviceFacade
    logger.info(f"Building bundle for action: {action_id}")
    try:
        from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
        device_facade = DeviceFacade(raw_device)
        bundle = _build_action_bundle(device_facade)
    except Exception as e:
        _emit({"type": "result", "success": False, "message": f"Action init failed: {e}\n{traceback.format_exc()}"})
        sys.exit(1)

    # Execute the action
    try:
        fn = ACTION_REGISTRY[action_id]
        result = fn(bundle, params)
        success = bool(result)
        msg = f"Action '{action_id}' {'succeeded' if success else 'failed'}"
        logger.info(f"{'✅' if success else '❌'} {msg}")
        _emit({"type": "result", "success": success, "message": msg})
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Action '{action_id}' raised exception: {e}\n{tb}")
        _emit({"type": "result", "success": False, "message": f"Exception: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
