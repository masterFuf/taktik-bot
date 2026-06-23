"""Publish actions for TikTok compat diagnostics (Cartography Lab).

The real production publish path: ``TikTokUploadWorkflow.execute`` (full upload) plus the
granular ``services/publish/navigation`` steps. These use the RAW device (they dump the UI
hierarchy), which the bundle exposes as ``a.device.device`` — same object the prod publish
bridge passes. A media file must already be on the device.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


def _raw(a):
    # nav helpers + the upload workflow need the raw uiautomator2 device (dump_hierarchy/press);
    # the bundle facade exposes it via .device, matching what the prod publish bridge passes.
    return getattr(a.device, "device", a.device)


def _device_id(a):
    return getattr(a.device, "device_id", None) or "lab"


def _hashtags(p):
    raw = (p.get("hashtags") or "").strip()
    return [h.strip().lstrip("#") for h in raw.split(",") if h.strip()] if raw else []


@action("tt.publish.upload")
def upload(a, p):
    """Full production TikTok upload (TikTokUploadWorkflow.execute): create + gallery +
    select + advance + caption + publish. Params: local_path (required, on-device media),
    caption, hashtags (comma-list). Run on a TEST account."""
    local_path = (p.get("local_path") or "").strip()
    if not local_path:
        return {"success": False, "message": "local_path param is required"}
    from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import TikTokUploadWorkflow
    logger.info(f"tt.publish.upload: {local_path}")
    wf = TikTokUploadWorkflow(_raw(a), _device_id(a))
    r = wf.execute(local_path=local_path, caption=(p.get("caption") or ""), hashtags=_hashtags(p))
    if isinstance(r, dict):
        return {"success": bool(r.get("success", True)), "message": r.get("message") or "upload attempted", "details": r}
    return {"success": bool(r), "message": "upload attempted"}


def _nav(a):
    from taktik.core.social_media.tiktok.services.publish import navigation
    return navigation


@action("tt.publish.tap_create")
def tap_create(a, p):
    """Tap the Create (+) button — 1st publish step."""
    ok = _nav(a).tap_create_button(_raw(a))
    return {"success": bool(ok), "message": f"create tapped={ok}"}


@action("tt.publish.tap_upload")
def tap_upload(a, p):
    """Tap the Upload button (chain of fallbacks that drift)."""
    ok = _nav(a).tap_upload_button(_raw(a))
    return {"success": bool(ok), "message": f"upload tapped={ok}"}


@action("tt.publish.open_gallery")
def open_gallery(a, p):
    """Ensure the gallery picker is open (retry + permissions)."""
    ok = _nav(a).ensure_gallery_picker_open(_raw(a), _device_id(a))
    return {"success": bool(ok), "message": f"gallery open={ok}"}


@action("tt.publish.select_first_media")
def select_first_media(a, p):
    """Select the first gallery item (coordinate fallback)."""
    ok = _nav(a).select_first_gallery_item(_raw(a))
    return {"success": bool(ok), "message": f"first media selected={ok}"}


@action("tt.publish.advance_to_post")
def advance_to_post(a, p):
    """Advance from the edit screen to the post screen."""
    ok = _nav(a).advance_to_post_screen(_raw(a))
    return {"success": bool(ok), "message": f"advanced to post={ok}"}


@action("tt.publish.fill_caption")
def fill_caption(a, p):
    """Fill the caption (the most intricate publish step: caption + hashtag confirmation).
    Params: caption (required), hashtags (comma-list). Be on the post screen."""
    caption = (p.get("caption") or "").strip()
    if not caption:
        return {"success": False, "message": "caption param is required"}
    from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import TikTokUploadWorkflow
    wf = TikTokUploadWorkflow(_raw(a), _device_id(a))
    ok = wf._fill_caption(caption, _hashtags(p))
    return {"success": bool(ok), "message": f"caption filled={ok}"}
