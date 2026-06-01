"""Detection and capture actions for YouTube diagnostics."""

import os
import tempfile
import time

from bridges.youtube.diagnostics.runtime.events import log
from bridges.youtube.diagnostics.runtime.registry import action


@action("yt.detection.is_youtube_open")
def is_youtube_open(d, p, _S):
    try:
        app = d.app_current()
        pkg = app.get("package", "")
        is_yt = pkg == "com.google.android.youtube"
        log("info", f"Current app: {pkg} -> YouTube open: {is_yt}")
        return is_yt
    except Exception as exc:
        log("error", f"Could not get current app: {exc}")
        return False


@action("yt.detection.get_current_screen")
def get_current_screen(d, p, _S):
    try:
        app = d.app_current()
        log("info", f"Package: {app.get('package')} | Activity: {app.get('activity')}")
        return True
    except Exception as exc:
        log("error", f"Could not get current app: {exc}")
        return False


@action("yt.detection.dump_xml")
def dump_xml(d, p, _S):
    try:
        xml = d.dump_hierarchy()
        if xml:
            preview = xml[:2000] + ("..." if len(xml) > 2000 else "")
            log("info", f"XML dump ({len(xml)} chars):\n{preview}")
        else:
            log("warning", "XML dump returned empty")
        return True
    except Exception as exc:
        log("error", f"XML dump failed: {exc}")
        return False


@action("yt.detection.screenshot")
def take_screenshot(d, p, _S):
    path_ = os.path.join(
        tempfile.gettempdir(),
        "taktik_debug",
        f"yt_action_{int(time.time())}.png",
    )
    os.makedirs(os.path.dirname(path_), exist_ok=True)
    try:
        d.screenshot(path_)
        log("info", f"Screenshot saved: {path_}")
        return True
    except Exception as exc:
        log("error", f"Screenshot failed: {exc}")
        return False
