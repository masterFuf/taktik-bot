"""Content-publishing actions for Instagram compat diagnostics (Cartography Lab).

The REAL publish orchestrators (``ContentWorkflow``) — vs the low-level ``publish.*`` atomics
that re-implement the flow. Built on the warm device (device_manager=facade, nav=a.nav,
detection=a.detection). Each takes a media file path that must already be on the device.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


def _content(a):
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    return ContentWorkflow(a.device, a.nav, a.detection)


def _hashtags(p):
    raw = (p.get("hashtags") or "").strip()
    return [h.strip().lstrip("#") for h in raw.split(",") if h.strip()] if raw else None


def _result(r, fallback):
    if isinstance(r, dict):
        return {"success": bool(r.get("success", True)), "message": r.get("message") or fallback, "details": r}
    return {"success": bool(r), "message": fallback}


@action("content.publish_photo")
def publish_photo(a, p):
    """Publish a single PHOTO via the real orchestrator (ContentWorkflow.post_single_photo):
    open creation + select media + caption/location/hashtags + share. Params: image_path
    (required, on-device path), caption, location, hashtags (comma-list)."""
    image_path = (p.get("image_path") or "").strip()
    if not image_path:
        return {"success": False, "message": "image_path param is required"}
    logger.info(f"content.publish_photo: {image_path}")
    r = _content(a).post_single_photo(image_path, caption=(p.get("caption") or None),
                                      location=(p.get("location") or None), hashtags=_hashtags(p))
    return _result(r, "photo published")


@action("content.publish_reel")
def publish_reel(a, p):
    """Publish a REEL via the real orchestrator (ContentWorkflow.post_reel): draft modal +
    multi-screen publish loop. Params: video_path (required), caption, hashtags (comma-list)."""
    video_path = (p.get("video_path") or "").strip()
    if not video_path:
        return {"success": False, "message": "video_path param is required"}
    logger.info(f"content.publish_reel: {video_path}")
    r = _content(a).post_reel(video_path, caption=(p.get("caption") or None), hashtags=_hashtags(p))
    return _result(r, "reel published")


@action("content.publish_story")
def publish_story(a, p):
    """Publish a STORY via the real orchestrator (ContentWorkflow.post_story). Params:
    image_path (required), duration (seconds, default 5)."""
    image_path = (p.get("image_path") or "").strip()
    if not image_path:
        return {"success": False, "message": "image_path param is required"}
    try:
        duration = int(p.get("duration") or 5)
    except (TypeError, ValueError):
        duration = 5
    r = _content(a).post_story(image_path, duration=duration)
    return _result(r, "story published")


@action("content.add_location")
def add_location(a, p):
    """Add a location to the post being composed (ContentUIHelpersMixin._add_location: open
    picker + type + select) — no atomic publish.* equivalent. Param: location (required).
    Be on the composer screen."""
    location = (p.get("location") or "").strip()
    if not location:
        return {"success": False, "message": "location param is required"}
    ok = _content(a)._add_location(location)
    return {"success": bool(ok), "message": f"location added={ok}"}
