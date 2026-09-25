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


@action("publish.ensure_gallery_open")
def ensure_gallery_open(a, p):
    """Publish gate: ensure the gallery grid is open from the camera/creation screen
    (InstagramPostWorkflow._ensure_gallery_open)."""
    _post_workflow(a)._ensure_gallery_open()
    return {"success": True, "message": "ensure_gallery_open ran"}


@action("publish.wait_publish_commit")
def wait_publish_commit(a, p):
    """Publish gate: wait for the publish to actually commit / succeed
    (InstagramPostWorkflow._wait_for_publish_commit) — the success verdict of each publish.
    Param: timeout (seconds, default 120)."""
    try:
        timeout = float(p.get("timeout") or 120.0)
    except (TypeError, ValueError):
        timeout = 120.0
    ok = _post_workflow(a)._wait_for_publish_commit(timeout=timeout)
    return {"success": bool(ok), "message": f"publish committed={ok}"}
