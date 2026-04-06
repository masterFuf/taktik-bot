"""
TikTok Action Test Bridge — Manual action testing from the Debug Panel.

Receives a JSON config with:
  {
    "device_id": "...",
    "action_id": "...",   # e.g. "tt.popups.close_popup", "tt.video.like"
    "params": {}          # optional action-specific params
  }

Outputs JSON lines to stdout:
  {"type": "log",    "level": "info|debug|warning|error", "message": "..."}
  {"type": "result", "success": true|false, "message": "...", "selector_traces": [...]}
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


# =============================================================================
# Selector tracing
# =============================================================================

class SelectorTracer:
    """Records every XPath selector check performed during an action."""

    def __init__(self):
        self.traces: list[dict] = []

    def record(self, xpath_str: str, found: bool) -> None:
        self.traces.append({"xpath": xpath_str, "found": found})
        icon = "✓" if found else "✗"
        short = xpath_str if len(xpath_str) <= 80 else "…" + xpath_str[-77:]
        _log("debug", f"[selector] {icon} {short}")


class _TracedSelector:
    """Wraps a uiautomator2 XPathSelector and records .exists checks."""

    __slots__ = ('_o', '_xpath', '_tracer')

    def __init__(self, original, xpath_str: str, tracer: SelectorTracer):
        object.__setattr__(self, '_o', original)
        object.__setattr__(self, '_xpath', xpath_str)
        object.__setattr__(self, '_tracer', tracer)

    @property
    def exists(self) -> bool:
        o = object.__getattribute__(self, '_o')
        t = object.__getattribute__(self, '_tracer')
        x = object.__getattribute__(self, '_xpath')
        result = o.exists
        t.record(x, result)
        return result

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_o'), name)

    def __bool__(self):
        return bool(object.__getattribute__(self, '_o'))


# ── Action registry ───────────────────────────────────────────────────────────

ACTION_REGISTRY: dict = {}

def _action(action_id: str):
    def decorator(fn):
        ACTION_REGISTRY[action_id] = fn
        return fn
    return decorator


# =============================================================================
# FAMILY: popups
# =============================================================================

@_action("tt.popups.has_popup")
def has_popup(a, p):
    result = a.popup_detector.has_popup()
    logger.info(f"Has popup: {result}")
    return result

@_action("tt.popups.close_popup")
def close_popup(a, p):
    return a.popup.close_popup()

@_action("tt.popups.close_collections")
def close_collections(a, p):
    return a.popup.close_collections_popup()

@_action("tt.popups.close_follow_friends")
def close_follow_friends(a, p):
    return a.popup.close_follow_friends_popup()

@_action("tt.popups.dismiss_notification")
def dismiss_notification(a, p):
    return a.popup.dismiss_notification_banner()

@_action("tt.popups.close_comments")
def close_comments(a, p):
    return a.popup.close_comments_section()

@_action("tt.popups.close_system")
def close_system_popup(a, p):
    return a.popup.close_system_popup()

@_action("tt.popups.has_collections")
def has_collections(a, p):
    result = a.popup_detector.has_collections_popup()
    logger.info(f"Has collections popup: {result}")
    return result

@_action("tt.popups.has_comments")
def has_comments(a, p):
    result = a.popup_detector.has_comments_section_open()
    logger.info(f"Has comments open: {result}")
    return result


# =============================================================================
# FAMILY: detection
# =============================================================================

@_action("tt.detection.is_for_you")
def is_for_you(a, p):
    result = a.detection.is_on_for_you_page()
    logger.info(f"For You page: {result}")
    return result

@_action("tt.detection.is_inbox")
def is_inbox(a, p):
    result = a.detection.is_on_inbox_page()
    logger.info(f"Inbox page: {result}")
    return result

@_action("tt.detection.is_ad")
def is_ad(a, p):
    result = a.video_detector.is_ad_video()
    logger.info(f"Is ad: {result}")
    return result

@_action("tt.detection.is_liked")
def is_liked(a, p):
    result = a.video_detector.is_video_liked()
    logger.info(f"Video liked: {result}")
    return result

@_action("tt.detection.is_followed")
def is_followed(a, p):
    result = a.video_detector.is_user_followed()
    logger.info(f"User followed: {result}")
    return result

@_action("tt.detection.get_video_info")
def get_video_info(a, p):
    info = a.video_detector.get_video_info()
    logger.info(f"Video info: {info}")
    return bool(info)


# =============================================================================
# FAMILY: navigation
# =============================================================================

@_action("tt.navigation.go_home")
def go_home(a, p):
    return a.nav.navigate_to_home()

@_action("tt.navigation.go_inbox")
def go_inbox(a, p):
    return a.nav.navigate_to_inbox()

@_action("tt.navigation.go_profile")
def go_profile(a, p):
    return a.nav.navigate_to_profile()

@_action("tt.navigation.go_back")
def go_back(a, p):
    return a.nav.go_back()


# =============================================================================
# FAMILY: video
# =============================================================================

@_action("tt.video.like")
def like_video(a, p):
    return a.video.click_like_button()

@_action("tt.video.double_tap_like")
def double_tap_like(a, p):
    return a.video.double_tap_like()

@_action("tt.video.click_comment")
def click_comment(a, p):
    return a.video.click_comment_button()

@_action("tt.video.click_share")
def click_share(a, p):
    return a.video.click_share_button()

@_action("tt.video.click_favorite")
def click_favorite(a, p):
    return a.video.click_favorite_button()

@_action("tt.video.follow")
def follow_author(a, p):
    return a.video.click_video_follow_button()


# =============================================================================
# FAMILY: scroll
# =============================================================================

@_action("tt.scroll.next_video")
def next_video(a, p):
    return a.scroll.scroll_to_next_video()

@_action("tt.scroll.watch_video")
def watch_video(a, p):
    duration = float(p.get("duration", 3.0))
    return a.scroll.watch_video(duration=duration)

@_action("tt.scroll.profile_down")
def scroll_profile_down(a, p):
    return a.scroll.scroll_profile_videos(direction="down")

@_action("tt.scroll.profile_up")
def scroll_profile_up(a, p):
    return a.scroll.scroll_profile_videos(direction="up")


# =============================================================================
# FAMILY: search
# =============================================================================

@_action("tt.search.open")
def open_search(a, p):
    return a.search.open_search()

@_action("tt.search.submit")
def search_submit(a, p):
    query = p.get("query", "")
    if not query:
        logger.error("Missing 'query' param")
        return False
    return a.search.search_and_submit(query)

@_action("tt.search.click_first")
def search_click_first(a, p):
    return a.search.click_first_video_result()


# =============================================================================
# Action runner setup
# =============================================================================

class ActionBundle:
    pass


def _build_action_bundle(device_facade):
    from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.tiktok.actions.atomic.detection_actions import DetectionActions
    from taktik.core.social_media.tiktok.actions.atomic.click_actions import ClickActions
    from taktik.core.social_media.tiktok.actions.atomic.popup_actions import PopupActions
    from taktik.core.social_media.tiktok.actions.atomic.popup_detector import PopupDetector
    from taktik.core.social_media.tiktok.actions.atomic.scroll_actions import ScrollActions
    from taktik.core.social_media.tiktok.actions.atomic.search_actions import SearchActions
    from taktik.core.social_media.tiktok.actions.atomic.video_actions import VideoActions
    from taktik.core.social_media.tiktok.actions.atomic.video_detector import VideoDetector

    logger.info("Building TikTok action bundle...")
    bundle = ActionBundle()
    bundle.device         = device_facade
    bundle.nav            = NavigationActions(device_facade)
    bundle.detection      = DetectionActions(device_facade)
    bundle.click          = ClickActions(device_facade)
    bundle.popup          = PopupActions(device_facade)
    bundle.popup_detector = PopupDetector(device_facade)
    bundle.scroll         = ScrollActions(device_facade)
    bundle.search         = SearchActions(device_facade)
    bundle.video          = VideoActions(device_facade)
    bundle.video_detector = VideoDetector(device_facade)
    logger.info("TikTok action bundle ready")
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

    # Build action bundle
    logger.info(f"Building bundle for action: {action_id}")
    try:
        from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade
        device_facade = DeviceFacade(raw_device)
        bundle = _build_action_bundle(device_facade)
    except Exception as e:
        _emit({"type": "result", "success": False, "message": f"Action init failed: {e}\n{traceback.format_exc()}"})
        sys.exit(1)

    # Install selector tracer
    tracer = SelectorTracer()
    _original_xpath = device_facade._device.xpath

    def _traced_xpath(expr, *args, **kwargs):
        return _TracedSelector(_original_xpath(expr, *args, **kwargs), expr, tracer)

    device_facade._device.xpath = _traced_xpath

    # Execute the action
    try:
        fn = ACTION_REGISTRY[action_id]
        result = fn(bundle, params)
        success = bool(result)
        msg = f"Action '{action_id}' {'succeeded' if success else 'failed'}"
        matched = sum(1 for t in tracer.traces if t["found"])
        logger.info(f"{'✅' if success else '❌'} {msg} — selectors: {matched}/{len(tracer.traces)} matched")
        _emit({
            "type": "result",
            "success": success,
            "message": msg,
            "selector_traces": tracer.traces,
        })
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Action '{action_id}' raised exception: {e}\n{tb}")
        _emit({
            "type": "result",
            "success": False,
            "message": f"Exception: {e}",
            "selector_traces": tracer.traces,
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
