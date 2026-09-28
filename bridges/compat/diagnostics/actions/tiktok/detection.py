"""Detection actions for TikTok compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action, detection_action
from bridges.compat.diagnostics.runtime.action_test.not_applicable import absent_on_screen, not_applicable

#: The feed items that carry a caption block (`read_screen().kind`); a LIVE preview has none.
_CAPTIONED_ITEMS = ("video", "ad")


@action("tt.detection.read_screen")
def read_screen(a, p):
    """One photo of the screen and what it shows: the recognition each For You and search turn
    starts with."""
    screen = a.detection.read_screen()
    age_ms = screen.photo_age_ms
    details = {"kind": screen.kind, **screen.signals(),
               "photoAgeMs": None if age_ms is None else round(age_ms)}
    logger.info(f"Screen read on one photo: {details}")
    return {"success": screen.recognised, "message": screen.kind, "details": details}


@detection_action("tt.detection.is_action_blocked")
def is_action_blocked(a, p):
    """Is TikTok refusing the account's actions now? Reads only (production
    `DetectionActions.is_action_blocked`, the look every TikTok writing path makes)."""
    return a.detection.is_action_blocked()


@detection_action("tt.detection.is_for_you")
def is_for_you(a, p):
    return a.detection.is_on_for_you_page()


@detection_action("tt.detection.is_inbox")
def is_inbox(a, p):
    return a.detection.is_on_inbox_page()


@detection_action("tt.detection.is_ad")
def is_ad(a, p):
    return a.video_detector.is_ad_video()


@detection_action("tt.detection.is_live_preview")
def is_live_preview(a, p):
    return a.video_detector.is_live_preview()


@detection_action("tt.detection.is_liked")
def is_liked(a, p):
    return a.video_detector.is_video_liked()


@detection_action("tt.detection.is_followed")
def is_followed(a, p):
    return a.video_detector.is_user_followed()


@action("tt.detection.get_video_info")
def get_video_info(a, p):
    info = a.video_detector.get_video_info()
    logger.info(f"Video info: {info}")
    return bool(info)


@action("tt.detection.get_video_author")
def get_video_author(a, p):
    """Read the current video's author username (scraping/targeting join key, hidden by the
    bundled get_video_info)."""
    author = a.video_detector.get_video_author()
    logger.info(f"Video author: @{author}" if author else "Video author: none")
    return {"success": bool(author), "message": f"@{author}" if author else "no author", "details": {"author": author}}


@action("tt.detection.get_video_description")
def get_video_description(a, p):
    """Read the current video's FULL description (taps '...more' to expand). The AGENTS
    coverage rule requires 'more' expansions to be testable.

    Read as a For You turn reads it: one photo (`read_screen()`), and the production reader handed
    that photo. A video without a description is an item of the feed (25 of the 323 video screens
    of the 43.1.4 corpus): not applicable when that photo shows a video or an ad and no description
    on it, or a LIVE preview, which has none. Anywhere else (another screen, a sheet over the
    video, an unreadable photo) nothing was read, and the action fails.
    """
    action_id = "tt.detection.get_video_description"
    screen = a.detection.read_screen()
    desc = a.video_detector.get_video_description_full(screen)
    logger.info(f"Video description: {len(desc or '')} chars ({screen.kind})")
    if desc:
        return {"success": True, "message": f"{len(desc)} chars", "details": {"description": desc}}
    if screen.kind == "live":
        return not_applicable(action_id, "the For You item on screen is a LIVE: no description")
    if screen.kind not in _CAPTIONED_ITEMS:
        return {"success": False, "message": f"{action_id}: no video on screen ({screen.kind}), nothing read",
                "details": {"description": None}}
    return absent_on_screen(action_id, device=a.device, platform="tiktok", still_there=None,
                            what="description", where=f"on the {screen.kind}")

