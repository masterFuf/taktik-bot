"""
YouTube Action Test Bridge — Manual action testing from the Debug Panel.

Receives a JSON config with:
  {
    "device_id": "...",
    "action_id": "...",   # e.g. "yt.upload.tap_create", "yt.visibility.set_private"
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


# Force UTF-8 on Windows
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

ACTION_REGISTRY: dict = {}


def _action(action_id: str):
    """Decorator to register an action."""
    def decorator(fn):
        ACTION_REGISTRY[action_id] = fn
        return fn
    return decorator


# ── Helpers ───────────────────────────────────────────────────────────────────

from taktik.core.shared.device.wait import wait_for_any as _wait_for_any_shared, try_tap as _try_tap_shared


def _wait_for_any(d, selectors: list, timeout: float = 6.0, label: str = "") -> str | None:
    """Bridge wrapper around the shared `wait_for_any` that forwards `_log`."""
    return _wait_for_any_shared(d, selectors, timeout=timeout, label=label, log=_log)


def _try_tap(d, selectors: list, timeout: float = 4.0, label: str = "") -> bool:
    """Bridge wrapper around the shared `try_tap` that forwards `_log`."""
    return _try_tap_shared(d, selectors, timeout=timeout, label=label, log=_log)


# =============================================================================
# FAMILY: yt.detection
# =============================================================================

@_action("yt.detection.is_youtube_open")
def is_youtube_open(d, p, _S):
    try:
        app = d.app_current()
        pkg = app.get("package", "")
        is_yt = pkg == "com.google.android.youtube"
        _log("info", f"Current app: {pkg} → YouTube open: {is_yt}")
        return is_yt
    except Exception as e:
        _log("error", f"Could not get current app: {e}")
        return False


@_action("yt.detection.get_current_screen")
def get_current_screen(d, p, _S):
    try:
        app = d.app_current()
        _log("info", f"Package: {app.get('package')} | Activity: {app.get('activity')}")
        return True
    except Exception as e:
        _log("error", f"Could not get current app: {e}")
        return False


@_action("yt.detection.dump_xml")
def dump_xml(d, p, _S):
    try:
        xml = d.dump_hierarchy()
        if xml:
            preview = xml[:2000] + ("..." if len(xml) > 2000 else "")
            _log("info", f"XML dump ({len(xml)} chars):\n{preview}")
        else:
            _log("warning", "XML dump returned empty")
        return True
    except Exception as e:
        _log("error", f"XML dump failed: {e}")
        return False


@_action("yt.detection.screenshot")
def take_screenshot(d, p, _S):
    import os
    import tempfile
    path_ = os.path.join(tempfile.gettempdir(), "taktik_debug", f"yt_action_{int(time.time())}.png")
    os.makedirs(os.path.dirname(path_), exist_ok=True)
    try:
        d.screenshot(path_)
        _log("info", f"Screenshot saved: {path_}")
        return True
    except Exception as e:
        _log("error", f"Screenshot failed: {e}")
        return False


# =============================================================================
# FAMILY: yt.navigation
# =============================================================================

@_action("yt.navigation.go_home")
def go_home(d, p, _S):
    result = _try_tap(d, _S.home_tab, timeout=4, label="home-tab")
    if result:
        time.sleep(1)
    return result


@_action("yt.navigation.press_back")
def press_back(d, p, _S):
    count = int(p.get("count", 1))
    for _ in range(count):
        d.press("back")
        time.sleep(0.6)
    return True


@_action("yt.navigation.home_button")
def home_button(d, p, _S):
    d.press("home")
    time.sleep(1)
    return True


@_action("yt.navigation.launch")
def launch_youtube(d, p, _S):
    from taktik.core.social_media.youtube.ui.selectors.upload import YOUTUBE_PACKAGE
    _log("info", "🔄 Stopping YouTube…")
    d.app_stop(YOUTUBE_PACKAGE)
    time.sleep(1)
    _log("info", "▶ Starting YouTube…")
    d.app_start(YOUTUBE_PACKAGE, "com.google.android.youtube.app.honeycomb.Shell$HomeActivity")
    time.sleep(4)
    app = d.app_current()
    is_yt = app.get("package") == YOUTUBE_PACKAGE
    _log("info" if is_yt else "warning", f"{'✅ YouTube launched' if is_yt else '⚠️ YouTube may not be in foreground'}")
    return is_yt


# =============================================================================
# FAMILY: yt.upload
# =============================================================================

@_action("yt.upload.tap_create")
def tap_create(d, p, _S):
    result = _try_tap(d, _S.create_button, timeout=5, label="create-btn")
    if result:
        time.sleep(1.5)
    return result


@_action("yt.upload.tap_short_tab")
def tap_short_tab(d, p, _S):
    result = _try_tap(d, _S.tab_short, timeout=5, label="tab-short")
    if result:
        time.sleep(1)
    return result


@_action("yt.upload.tap_video_tab")
def tap_video_tab(d, p, _S):
    result = _try_tap(d, _S.tab_video, timeout=5, label="tab-video")
    if result:
        time.sleep(1)
    return result


@_action("yt.upload.tap_gallery")
def tap_gallery(d, p, _S):
    result = _try_tap(d, _S.add_from_gallery, timeout=6, label="gallery-btn")
    if result:
        time.sleep(1.5)
    return result


@_action("yt.upload.select_first_item")
def select_first_item(d, p, _S):
    result = _try_tap(d, _S.gallery_first_item, timeout=5, label="gallery-first")
    if result:
        time.sleep(1)
    return result


@_action("yt.upload.tap_next")
def tap_next(d, p, _S):
    result = _try_tap(d, _S.next_button, timeout=6, label="next-btn")
    if result:
        time.sleep(2)
    return result


@_action("yt.upload.tap_upload")
def tap_upload(d, p, _S):
    result = _try_tap(d, _S.upload_button, timeout=6, label="upload-btn")
    if result:
        time.sleep(2)
    return result


@_action("yt.upload.dismiss_notification")
def dismiss_notification(d, p, _S):
    result = _try_tap(d, _S.notification_cancel, timeout=3, label="notif-cancel")
    if not result:
        _log("info", "No notification dialog visible")
    else:
        time.sleep(0.5)
    return True  # Not finding it is OK


# =============================================================================
# FAMILY: yt.visibility
# =============================================================================

@_action("yt.visibility.open_row")
def open_visibility_row(d, p, _S):
    """Tap the Visibility row on the Add Details screen to open the visibility sub-screen."""
    result = _try_tap(d, _S.detail_row_visibility, timeout=5, label="visibility-row")
    if result:
        time.sleep(1.5)
        # Confirm we landed on the visibility sub-screen
        indicator = _wait_for_any(d, _S.visibility_screen_indicator, timeout=4, label="visibility-screen")
        if indicator:
            _log("info", "✅ Visibility sub-screen is open")
        else:
            _log("warning", "⚠️ Tapped visibility row but sub-screen indicator not found")
    return result


@_action("yt.visibility.set_public")
def set_visibility_public(d, p, _S):
    """Select Public on the Set Visibility screen (must already be open)."""
    selectors = _S.visibility_row.get("public", [])
    if not selectors:
        _log("error", "No selectors for 'public'")
        return False
    time.sleep(1)  # Let options render
    result = _try_tap(d, selectors, timeout=5, label="visibility-public")
    if result:
        _log("info", "✅ Visibility set to Public")
        time.sleep(0.5)
    return result


@_action("yt.visibility.set_unlisted")
def set_visibility_unlisted(d, p, _S):
    """Select Unlisted on the Set Visibility screen (must already be open)."""
    selectors = _S.visibility_row.get("unlisted", [])
    if not selectors:
        _log("error", "No selectors for 'unlisted'")
        return False
    time.sleep(1)
    result = _try_tap(d, selectors, timeout=5, label="visibility-unlisted")
    if result:
        _log("info", "✅ Visibility set to Unlisted")
        time.sleep(0.5)
    return result


@_action("yt.visibility.set_private")
def set_visibility_private(d, p, _S):
    """Select Private on the Set Visibility screen (must already be open)."""
    selectors = _S.visibility_row.get("private", [])
    if not selectors:
        _log("error", "No selectors for 'private'")
        return False
    time.sleep(1)
    result = _try_tap(d, selectors, timeout=5, label="visibility-private")
    if result:
        _log("info", "✅ Visibility set to Private")
        time.sleep(0.5)
    return result


@_action("yt.visibility.tap_back")
def visibility_tap_back(d, p, _S):
    """Tap the back button from the Set Visibility screen."""
    result = _try_tap(d, _S.visibility_back_button, timeout=3, label="visibility-back")
    if not result:
        _log("info", "Back button not found via selector — using keycode")
        d.press("back")
    time.sleep(1)
    return True


# =============================================================================
# FAMILY: yt.keyboard
# =============================================================================

@_action("yt.keyboard.tap_title")
def tap_title_field(d, p, _S):
    """Tap the title/caption EditText on the Add Details screen to focus it."""
    result = _try_tap(d, _S.title_input, timeout=5, label="title-input")
    if result:
        time.sleep(0.5)
        _log("info", "✅ Title field focused")
    return result


@_action("yt.keyboard.type_title")
def type_title(d, p, _S):
    """Clear the title field and type new text."""
    text = p.get("text", "")
    if not text:
        _log("warning", "No 'text' param provided — clearing field only")

    # Tap to focus
    found = _wait_for_any(d, _S.title_input, timeout=5, label="title-input")
    if not found:
        _log("error", "Title field not found")
        return False

    try:
        el = d.xpath(found)
        el.click()
        time.sleep(0.4)
        # Clear existing text
        d.clear_text()
        time.sleep(0.2)
        if text:
            d.send_keys(text)
            time.sleep(0.3)
        _log("info", f"✅ Title typed: {text!r}")
        return True
    except Exception as e:
        _log("error", f"type_title failed: {e}")
        return False


@_action("yt.keyboard.clear_title")
def clear_title(d, p, _S):
    """Tap the title field and clear its content."""
    found = _wait_for_any(d, _S.title_input, timeout=5, label="title-input")
    if not found:
        _log("error", "Title field not found")
        return False
    try:
        d.xpath(found).click()
        time.sleep(0.4)
        d.clear_text()
        time.sleep(0.2)
        _log("info", "✅ Title field cleared")
        return True
    except Exception as e:
        _log("error", f"clear_title failed: {e}")
        return False


@_action("yt.keyboard.tap_description")
def tap_description_row(d, p, _S):
    """Tap the Description row on the Add Details screen to open the full-screen editor."""
    result = _try_tap(d, _S.detail_row_description, timeout=5, label="description-row")
    if result:
        time.sleep(1)
        # Check that full-screen EditText appeared
        found = _wait_for_any(d, _S.description_edittext, timeout=3, label="description-edittext")
        if found:
            _log("info", "✅ Description editor is open")
        else:
            _log("warning", "⚠️ Tapped description row but full-screen editor not detected")
    return result


@_action("yt.keyboard.type_description")
def type_description(d, p, _S):
    """Open the description editor and type text (appends to existing content)."""
    text = p.get("text", "")
    if not text:
        _log("warning", "No 'text' param provided")
        return False

    # Tap the description row to open the editor
    tapped = _try_tap(d, _S.detail_row_description, timeout=5, label="description-row")
    if not tapped:
        _log("error", "Could not open description editor")
        return False
    time.sleep(1)

    # Find the full-screen EditText
    found = _wait_for_any(d, _S.description_edittext, timeout=4, label="description-edittext")
    if not found:
        _log("error", "Description EditText not found after opening row")
        return False

    try:
        d.xpath(found).click()
        time.sleep(0.3)
        d.send_keys(text)
        time.sleep(0.3)
        _log("info", f"✅ Description typed: {text!r}")
        return True
    except Exception as e:
        _log("error", f"type_description failed: {e}")
        return False


# =============================================================================
# Main entry point
# =============================================================================

def main():
    # Bootstrap sys.path so taktik imports work
    import os
    bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)

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
        _emit({"type": "result", "success": False,
               "message": f"Unknown action: '{action_id}'. Available: {sorted(ACTION_REGISTRY.keys())}"})
        sys.exit(1)

    # Connect to device
    _log("info", f"Connecting to device: {device_id}")
    try:
        from taktik.core.shared.device.manager import DeviceManager
        device_manager = DeviceManager(device_id=device_id)
        if not device_manager.connect(verify_atx=False):
            _emit({"type": "result", "success": False, "message": f"Could not connect to device {device_id}"})
            sys.exit(1)
        raw_device = device_manager.device
        _log("info", f"Connected to {device_id}")
    except Exception as e:
        _emit({"type": "result", "success": False, "message": f"Device connection failed: {e}"})
        sys.exit(1)

    # Load YouTube selectors
    try:
        from taktik.core.social_media.youtube.ui.selectors.upload import UPLOAD_SELECTORS as _S
    except Exception as e:
        _emit({"type": "result", "success": False, "message": f"Failed to load YouTube selectors: {e}"})
        sys.exit(1)

    # Install selector tracer
    tracer = SelectorTracer()
    _original_xpath = raw_device.xpath

    def _traced_xpath(expr, *args, **kwargs):
        return _TracedSelector(_original_xpath(expr, *args, **kwargs), expr, tracer)

    raw_device.xpath = _traced_xpath

    # Execute the action
    try:
        fn = ACTION_REGISTRY[action_id]
        result = fn(raw_device, params, _S)
        success = bool(result)
        msg = f"Action '{action_id}' {'succeeded' if success else 'failed'}"
        matched = sum(1 for t in tracer.traces if t["found"])
        _log("info", f"{'✅' if success else '❌'} {msg} — selectors: {matched}/{len(tracer.traces)} matched")
        _emit({
            "type": "result",
            "success": success,
            "message": msg,
            "selector_traces": tracer.traces,
        })
    except Exception as e:
        tb = traceback.format_exc()
        _log("error", f"Action '{action_id}' raised exception: {e}\n{tb}")
        _emit({
            "type": "result",
            "success": False,
            "message": f"Exception: {e}",
            "selector_traces": tracer.traces,
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
