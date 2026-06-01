"""Visibility actions for YouTube diagnostics."""

import time

from bridges.youtube.diagnostics.actions.support import try_tap, wait_for_any
from bridges.youtube.diagnostics.runtime.events import log
from bridges.youtube.diagnostics.runtime.registry import action


@action("yt.visibility.open_row")
def open_visibility_row(d, p, _S):
    result = try_tap(d, _S.detail_row_visibility, timeout=5, label="visibility-row")
    if result:
        time.sleep(1.5)
        indicator = wait_for_any(
            d,
            _S.visibility_screen_indicator,
            timeout=4,
            label="visibility-screen",
        )
        if indicator:
            log("info", "Visibility sub-screen is open")
        else:
            log("warning", "Tapped visibility row but sub-screen indicator not found")
    return result


def _set_visibility(d, selectors: list, label: str, display_name: str) -> bool:
    if not selectors:
        log("error", f"No selectors for '{display_name}'")
        return False
    time.sleep(1)
    result = try_tap(d, selectors, timeout=5, label=label)
    if result:
        log("info", f"Visibility set to {display_name.title()}")
        time.sleep(0.5)
    return result


@action("yt.visibility.set_public")
def set_visibility_public(d, p, _S):
    return _set_visibility(
        d,
        _S.visibility_row.get("public", []),
        "visibility-public",
        "public",
    )


@action("yt.visibility.set_unlisted")
def set_visibility_unlisted(d, p, _S):
    return _set_visibility(
        d,
        _S.visibility_row.get("unlisted", []),
        "visibility-unlisted",
        "unlisted",
    )


@action("yt.visibility.set_private")
def set_visibility_private(d, p, _S):
    return _set_visibility(
        d,
        _S.visibility_row.get("private", []),
        "visibility-private",
        "private",
    )


@action("yt.visibility.tap_back")
def visibility_tap_back(d, p, _S):
    result = try_tap(d, _S.visibility_back_button, timeout=3, label="visibility-back")
    if not result:
        log("info", "Back button not found via selector, using keycode")
        d.press("back")
    time.sleep(1)
    return True
