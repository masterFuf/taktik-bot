"""Upload flow actions for YouTube diagnostics."""

import time

from bridges.youtube.diagnostics.actions.support import try_tap
from bridges.youtube.diagnostics.runtime.events import log
from bridges.youtube.diagnostics.runtime.registry import action


@action("yt.upload.tap_create")
def tap_create(d, p, _S):
    result = try_tap(d, _S.create_button, timeout=5, label="create-btn")
    if result:
        time.sleep(1.5)
    return result


@action("yt.upload.tap_short_tab")
def tap_short_tab(d, p, _S):
    result = try_tap(d, _S.tab_short, timeout=5, label="tab-short")
    if result:
        time.sleep(1)
    return result


@action("yt.upload.tap_video_tab")
def tap_video_tab(d, p, _S):
    result = try_tap(d, _S.tab_video, timeout=5, label="tab-video")
    if result:
        time.sleep(1)
    return result


@action("yt.upload.tap_gallery")
def tap_gallery(d, p, _S):
    result = try_tap(d, _S.add_from_gallery, timeout=6, label="gallery-btn")
    if result:
        time.sleep(1.5)
    return result


@action("yt.upload.select_first_item")
def select_first_item(d, p, _S):
    result = try_tap(d, _S.gallery_first_item, timeout=5, label="gallery-first")
    if result:
        time.sleep(1)
    return result


@action("yt.upload.tap_next")
def tap_next(d, p, _S):
    result = try_tap(d, _S.next_button, timeout=6, label="next-btn")
    if result:
        time.sleep(2)
    return result


@action("yt.upload.tap_upload")
def tap_upload(d, p, _S):
    result = try_tap(d, _S.upload_button, timeout=6, label="upload-btn")
    if result:
        time.sleep(2)
    return result


@action("yt.upload.dismiss_notification")
def dismiss_notification(d, p, _S):
    result = try_tap(d, _S.notification_cancel, timeout=3, label="notif-cancel")
    if not result:
        log("info", "No notification dialog visible")
    else:
        time.sleep(0.5)
    return True
