"""TikTok unfollow capabilities for the Cartography Lab, on the production workflow itself.

Both actions build the production `UnfollowWorkflow` on the session's device and call its own
steps, so what the Lab shows is what a run does:
- `tt.unfollow.preview_rows` (read-only): for each visible row of OUR following list, the handle
  paired to it, its button's state, and the decision the run would take (`row_refusal`: friends,
  followed too recently, follow date unknown, or unfollow). Nothing is tapped.
- `tt.unfollow.unfollow_one` (DESTRUCTIVE): one pass of `process_rows` limited to one unfollow:
  the decision, the tap, the proof by the row (it must offer to follow again), the confirmation
  sheet only if it shows, and the record in the base. Test account only.

Open our following list first (`tt.followers.open_own_following`).
"""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.models import UnfollowConfig
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow import UnfollowWorkflow
from taktik.core.social_media.tiktok.services.followers.stop_policy import normalize_username
from taktik.core.social_media.tiktok.ui.labels import classify_follow_button


def _raw(a):
    device = getattr(a, "device", None)
    return getattr(device, "_device", None) or device


def _flag(value, default=False):
    if value in (None, ""):
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "oui")


def _workflow(a, p, *, max_unfollows=1):
    """The production workflow on the session's phone, configured from the Lab params."""
    config = UnfollowConfig(
        max_unfollows=max_unfollows,
        include_friends=_flag(p.get("include_friends")),
        min_delay=0,
        max_delay=0,
        min_follow_age_days=int(float(p.get("min_follow_age_days") or 0)),
        bot_username=(str(p.get("account") or "").strip().lstrip("@") or None),
    )
    return UnfollowWorkflow(_raw(a), config)


@action("tt.unfollow.preview_rows")
def preview_rows(a, p):
    """What the unfollow would do with each visible row, without tapping anything."""
    workflow = _workflow(a, p)
    rows = []
    for button in workflow.visible_row_buttons():
        label = getattr(button, "text", "") or ""
        handle = workflow._resolve_username(button)
        rows.append({
            "handle": handle,
            "label": label,
            "state": classify_follow_button(label) or "unknown",
            "decision": workflow.row_refusal(label, handle) or "unfollow",
        })
    to_unfollow = sum(1 for row in rows if row["decision"] == "unfollow")
    logger.info(f"tt.unfollow.preview_rows: {len(rows)} row(s), {to_unfollow} to unfollow")
    return {
        "success": bool(rows),
        "message": f"{len(rows)} row(s), {to_unfollow} to unfollow" if rows else "no Following/Friends row on screen",
        "details": {"rows": rows[:20], "account": workflow.config.bot_username,
                    "minFollowAgeDays": workflow.config.min_follow_age_days},
    }


@action("tt.unfollow.unfollow_one")
def unfollow_one(a, p):
    """DESTRUCTIVE. Unfollow one account of the visible list through the production steps."""
    workflow = _workflow(a, p, max_unfollows=1)
    if not workflow.config.bot_username:
        return {"success": False, "message": "param 'account' required: the unfollow is written under it"}

    buttons = workflow.visible_row_buttons()
    wanted = normalize_username(p.get("username"))
    if wanted:
        buttons = [b for b in buttons if normalize_username(workflow._resolve_username(b)) == wanted]
        if not buttons:
            return {"success": False, "message": f"@{wanted}: no Following/Friends row on screen"}

    unfollowed = workflow.process_rows(buttons)
    stats = workflow.stats.to_dict()
    if unfollowed:
        message = "1 unfollow confirmed by the row" + ("" if stats["recorded"] else " (not written)")
    elif stats["unconfirmed"]:
        message = "tapped, but the row did not confirm the unfollow (not counted)"
    elif stats["refusals"]:
        message = f"kept: {', '.join(stats['refusals'])}"
    else:
        message = "no row to unfollow"
    return {"success": bool(unfollowed), "message": message, "details": stats}
