"""Keyboard actions for YouTube diagnostics."""

import time

from bridges.youtube.diagnostics.actions.support import try_tap, wait_for_any
from bridges.youtube.diagnostics.runtime.events import log
from bridges.youtube.diagnostics.runtime.registry import action


@action("yt.keyboard.tap_title")
def tap_title_field(d, p, _S):
    result = try_tap(d, _S.title_input, timeout=5, label="title-input")
    if result:
        time.sleep(0.5)
        log("info", "Title field focused")
    return result


@action("yt.keyboard.type_title")
def type_title(d, p, _S):
    text = p.get("text", "")
    if not text:
        log("warning", "No 'text' param provided, clearing field only")

    found = wait_for_any(d, _S.title_input, timeout=5, label="title-input")
    if not found:
        log("error", "Title field not found")
        return False

    try:
        el = d.xpath(found)
        el.click()
        time.sleep(0.4)
        d.clear_text()
        time.sleep(0.2)
        if text:
            d.send_keys(text)
            time.sleep(0.3)
        log("info", f"Title typed: {text!r}")
        return True
    except Exception as exc:
        log("error", f"type_title failed: {exc}")
        return False


@action("yt.keyboard.clear_title")
def clear_title(d, p, _S):
    found = wait_for_any(d, _S.title_input, timeout=5, label="title-input")
    if not found:
        log("error", "Title field not found")
        return False
    try:
        d.xpath(found).click()
        time.sleep(0.4)
        d.clear_text()
        time.sleep(0.2)
        log("info", "Title field cleared")
        return True
    except Exception as exc:
        log("error", f"clear_title failed: {exc}")
        return False


@action("yt.keyboard.tap_description")
def tap_description_row(d, p, _S):
    result = try_tap(d, _S.detail_row_description, timeout=5, label="description-row")
    if result:
        time.sleep(1)
        found = wait_for_any(d, _S.description_edittext, timeout=3, label="description-edittext")
        if found:
            log("info", "Description editor is open")
        else:
            log("warning", "Tapped description row but full-screen editor not detected")
    return result


@action("yt.keyboard.type_description")
def type_description(d, p, _S):
    text = p.get("text", "")
    if not text:
        log("warning", "No 'text' param provided")
        return False

    tapped = try_tap(d, _S.detail_row_description, timeout=5, label="description-row")
    if not tapped:
        log("error", "Could not open description editor")
        return False
    time.sleep(1)

    found = wait_for_any(d, _S.description_edittext, timeout=4, label="description-edittext")
    if not found:
        log("error", "Description EditText not found after opening row")
        return False

    try:
        d.xpath(found).click()
        time.sleep(0.3)
        d.send_keys(text)
        time.sleep(0.3)
        log("info", f"Description typed: {text!r}")
        return True
    except Exception as exc:
        log("error", f"type_description failed: {exc}")
        return False
