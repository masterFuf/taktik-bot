"""Publishing gates for Instagram compat diagnostics (Cartography Lab).

Steps of `InstagramPostWorkflow`, the one publishing workflow (desktop publish bridge, CLI
`taktik publish`); the whole flow is on the workflow test bench, which runs it with
`stop_before_share`. The Lab actions of the older `ContentWorkflow` went with it.
"""

from bridges.compat.diagnostics.actions.instagram import action


def _post_workflow(a):
    # InstagramPostWorkflow uses the RAW device (app_start/shell/xpath) + auto-detects the
    # active package — same object the prod publish bridge passes (self._connection.device).
    from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow
    raw = getattr(a.device, "device", a.device)
    device_id = getattr(a.device, "device_id", None) or "lab"
    return InstagramPostWorkflow(raw, device_id)


@action("publish.advance_to_composer")
def advance_to_composer(a, p):
    """Publish gate: advance from the gallery/editor to the composer screen
    (InstagramPostWorkflow._advance_to_composer) — make-or-break of the publish flow."""
    ok = _post_workflow(a)._advance_to_composer()
    return {"success": bool(ok), "message": f"advanced to composer={ok}"}


@action("publish.answer_permission_prompts")
def answer_permission_prompts(a, p):
    """Publish gate: answer Android's camera then microphone prompts "Only this time", never a
    lasting grant (InstagramPostWorkflow._answer_permission_prompts). No prompt: nothing tapped."""
    workflow = _post_workflow(a)
    err = workflow._answer_permission_prompts()
    answered = workflow.permission_prompts_answered
    if err:
        return {"success": False, "message": err["message"],
                "details": {"answered": answered, "error_type": err["error_type"]}}
    return {"success": True, "message": f"permission prompts answered only this time: {answered}",
            "details": {"answered": answered}}


@action("publish.dismiss_story_promo")
def dismiss_story_promo(a, p):
    """Publish gate: close Instagram's information window over the story editor through its
    acknowledgement ("OK"), never "View settings" (InstagramPostWorkflow._acknowledge_information_windows,
    the step run before "Your story"). No window, or the button already showing: nothing tapped."""
    from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
        CONTENT_CREATION_SELECTORS as CC,
    )

    workflow = _post_workflow(a)
    windows = workflow._acknowledge_information_windows(CC.story_publish_xpaths())
    if not windows.ok:
        return {"success": False, "message": f"window left on screen: {windows.left_on_screen}",
                "details": {"acknowledged": windows.acknowledged,
                            "error_type": "information_window_unanswered"}}
    return {"success": True, "message": f"information windows acknowledged: {windows.acknowledged}",
            "details": {"acknowledged": windows.acknowledged}}


@action("publish.ensure_gallery_open")
def ensure_gallery_open(a, p):
    """Publish gate: ensure the gallery grid is open from the camera/creation screen
    (InstagramPostWorkflow._ensure_gallery_open)."""
    _post_workflow(a)._ensure_gallery_open()
    return {"success": True, "message": "ensure_gallery_open ran"}


def _timeout(p, default: float) -> float:
    try:
        return float(p.get("timeout") or default)
    except (TypeError, ValueError):
        return default


@action("publish.wait_publish_commit")
def wait_publish_commit(a, p):
    """Publish gate: wait for the composer to close after "Share", the share verdict of a post,
    reel or carousel (InstagramPostWorkflow._wait_for_publish_commit). Not the story's: see
    `publish.wait_story_published`. Param: timeout (seconds, default 120)."""
    ok = _post_workflow(a)._wait_for_publish_commit(timeout=_timeout(p, 120.0))
    return {"success": bool(ok), "message": f"publish committed={ok}"}


@action("publish.wait_upload_finished")
def wait_upload_finished(a, p):
    """Publish gate: after the share of a post, reel or carousel, wait for Instagram's upload
    indicator (feed pending row, Reels snackbar) to come and go
    (InstagramPostWorkflow._wait_for_upload_confirmation). Its verdict alone deletes the pushed
    media. Reads only. Param: timeout (seconds, default 180)."""
    ok = _post_workflow(a)._wait_for_upload_confirmation(timeout=_timeout(p, 180.0))
    return {"success": bool(ok), "message": f"upload finished on screen={ok}"}


@action("publish.read_own_story")
def read_own_story(a, p):
    """Read our own bubble of the feed tray (InstagramPostWorkflow._own_story_state): "posted"
    (seen whole, its ring on), "empty" (seen whole, no ring), or unread (not on the feed, tray
    scrolled). Reads only, no gesture."""
    state = _post_workflow(a)._own_story_state()
    return {"success": state is not None, "message": f"own story: {state or 'not read'}",
            "details": {"state": state}}


@action("publish.wait_story_published")
def wait_story_published(a, p):
    """Publish gate: the story's verdict after "Your story" (InstagramPostWorkflow._wait_for_story_commit):
    "confirmed" when our bubble goes from `before` ("empty") to its ring on, "shared" when back
    on the feed with nothing to compare, "not_committed" when the editor stays open. Reads only,
    except an information window over the feed, closed by its "OK".
    Params: before ("empty" or "posted", from `publish.read_own_story`), timeout (seconds, default 120)."""
    before = str(p.get("before") or "empty")
    verdict = _post_workflow(a)._wait_for_story_commit(before, timeout=_timeout(p, 120.0))
    return {"success": verdict == "confirmed", "message": f"story verdict: {verdict}",
            "details": {"verdict": verdict, "before": before}}
