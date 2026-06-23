"""Detection actions for TikTok compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.detection.is_for_you")
def is_for_you(a, p):
    result = a.detection.is_on_for_you_page()
    logger.info(f"For You page: {result}")
    return result


@action("tt.detection.is_inbox")
def is_inbox(a, p):
    result = a.detection.is_on_inbox_page()
    logger.info(f"Inbox page: {result}")
    return result


@action("tt.detection.is_ad")
def is_ad(a, p):
    result = a.video_detector.is_ad_video()
    logger.info(f"Is ad: {result}")
    return result


@action("tt.detection.is_liked")
def is_liked(a, p):
    result = a.video_detector.is_video_liked()
    logger.info(f"Video liked: {result}")
    return result


@action("tt.detection.is_followed")
def is_followed(a, p):
    result = a.video_detector.is_user_followed()
    logger.info(f"User followed: {result}")
    return result


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
    coverage rule requires 'more' expansions to be testable."""
    desc = a.video_detector.get_video_description_full()
    logger.info(f"Video description: {len(desc or '')} chars")
    return {"success": bool(desc), "message": f"{len(desc or '')} chars", "details": {"description": desc}}

