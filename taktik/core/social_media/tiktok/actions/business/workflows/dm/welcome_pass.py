"""The AI welcome pass over a new-followers list: qualify each follower, record them for the
attribution, follow back, and welcome the ones the policy allows.

It runs after a `scrape` of the new-followers flow, only when BOTH `ai.enabled` and
`ai.newFollowers.enabled` are set: a run that says nothing about AI lists and stops. The decision
itself is `services/welcome` (pure policy, the anti-duplicate guard, the qualification walk); this
module does the device work around it, for the desktop bridge and the CLI alike. What differs
between hosts is injected: the qualifier (the AI service, and where its verdicts are printed), the
notifier, and whether this host sends the welcome DM at all.

The DM itself is not written here: the texts come from the app (which holds the account persona)
and the send goes through the production cold-DM path, which navigates by verified arrival and
confirms a send by the composer EMPTYING rather than by the click landing.

What a device run between two test accounts settled: this page shows a DISPLAY NAME and never a
handle, so `navigate_to_user_profile` cannot be the way in. Handing it the display name reported
`profile_unreachable` for every follower just listed. The row is opened instead, and the handle
is read off the profile that opens -- which also keeps the verdict from being filed under a
username nobody has. A display name whose emoji the XML dump ate came back as its real handle.

STILL UNVERIFIED on a phone: the follow-back and the DM themselves. That run's AI declined all
three followers (small personal accounts against a niche operated account), a legitimate outcome
that means no send has run yet.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Dict, List, Mapping, Optional

from loguru import logger

from taktik.core.social_media.tiktok.services.welcome import (
    NewFollowerWelcomePass,
    WelcomeDmGuard,
    WelcomePolicy,
    follow_back_targets,
    summarize,
    welcome_dm_targets,
)

#: (device, username) -> the engagement verdict, or None.
Qualifier = Callable[[Any, str], Optional[dict]]
#: (ai_config, language) -> a qualifier, or None when no AI service can be built.
QualifierFactory = Callable[[Mapping[str, Any], str], Optional[Qualifier]]
WorkflowHook = Callable[[Any], None]


def _log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _emit(notifier: Any, method: str, *args: Any, **kwargs: Any) -> None:
    target = getattr(notifier, method, None)
    if callable(target):
        target(*args, **kwargs)


def run_welcome_pass(
    followers: List[Any],
    policy: WelcomePolicy,
    *,
    workflow: Any,
    started: Any,
    device_id: Optional[str],
    ai_config: Mapping[str, Any],
    language: str,
    notifier: Any,
    qualifier_factory: Optional[QualifierFactory],
    outreach_notifier: Any = None,
    workflow_hook: Optional[WorkflowHook] = None,
    send_welcome_dms: bool = True,
) -> Dict[str, Any]:
    """Qualify each new follower, then act on the decisions. Never fails the scrape.

    A broken AI setup, an unreachable database or a refused guard must cost the welcome pass,
    not the list the operator asked for, which is already emitted by then.
    """
    try:
        return _run(
            followers, policy, workflow=workflow, started=started, device_id=device_id,
            ai_config=ai_config, language=language, notifier=notifier,
            qualifier_factory=qualifier_factory, outreach_notifier=outreach_notifier,
            workflow_hook=workflow_hook, send_welcome_dms=send_welcome_dms,
        )
    except Exception as exc:
        logger.error(f"Passe IA nouveaux followers en échec: {exc}")
        _emit(notifier, "log", "warning", f"AI welcome pass failed: {exc}")
        return {"error": str(exc)}


def _run(followers, policy, *, workflow, started, device_id, ai_config, language, notifier,
         qualifier_factory, outreach_notifier, workflow_hook, send_welcome_dms) -> Dict[str, Any]:
    qualify = qualifier_factory(ai_config, language) if qualifier_factory is not None else None
    if qualify is None:
        # No service means no verdict, and no verdict means no decision. Falling back to
        # "follow everyone back" here would be the run doing something nobody asked for.
        logger.warning("🤖 Passe IA demandée mais aucun service IA disponible — aucune décision prise")
        _emit(notifier, "log", "warning", "AI welcome pass skipped: no AI service available")
        return {"skipped": "no_ai_service"}

    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    device = started.device
    dm_actions = DMActions(device)
    # Shown name -> the handle its profile turned out to carry.
    resolved_handles: Dict[str, str] = {}

    def _visit(shown_name: str) -> bool:
        handle = dm_actions.open_new_follower_profile(shown_name)
        if handle:
            resolved_handles[shown_name] = handle
        return bool(handle)

    def _qualify_visited(shown_name: str):
        # Under the REAL handle. A verdict filed under a display name lands on a username
        # nobody has, and the "have we already written to this person?" guard never matches.
        return qualify(device, resolved_handles.get(shown_name) or shown_name)

    _emit(notifier, "status", "running", f"Qualifying {len(followers)} new follower(s)")
    decisions = NewFollowerWelcomePass(
        policy=policy, visit_profile=_visit, qualify=_qualify_visited, log=_log
    ).decide(followers)

    # Every decision travels under the handle its profile carried, so what follows -- the
    # follow-back, the DM, the duplicate guard -- addresses the person and not the label the
    # inbox happened to print. Rebuilt rather than mutated: `WelcomeDecision` is frozen.
    decisions = [
        replace(decision, username=resolved_handles[decision.username])
        if resolved_handles.get(decision.username)
        else decision
        for decision in decisions
    ]
    stats = summarize(decisions)
    logger.info(f"🤖 Décisions IA: {stats}")
    _emit(notifier, "log", "info", f"AI welcome pass: {stats}")

    # The attribution's raw material, and it costs nothing here: every profile has just been
    # opened and every handle is already in hand. A separate scan would open the same profiles
    # a second time.
    _record_followers_as_notifications(started.bot_username, followers, resolved_handles)

    followed_back = _follow_back_decided(workflow, follow_back_targets(decisions), notifier)
    welcome = _welcome_decided(
        welcome_dm_targets(decisions), policy, started=started, device_id=device_id, notifier=notifier,
        outreach_notifier=outreach_notifier, workflow_hook=workflow_hook, send_welcome_dms=send_welcome_dms,
    )
    return {
        "summary": stats,
        "decisions": [decision.to_dict() for decision in decisions],
        "follow_back": followed_back,
        "welcome_dm": welcome,
    }


def _record_followers_as_notifications(
    bot_username: Optional[str],
    followers: List[Any],
    resolved_handles: Dict[str, str],
) -> None:
    """Write one `new_follower` notification per resolved follower. Best-effort, never raises.

    Only the resolved ones. A row filed under a display name joins to nothing, so the follower
    would read as "never engaged" -- a confident wrong answer, and worse than no row at all.
    """
    from taktik.core.database.tiktok_notifications import record_scan_notifications
    from taktik.core.social_media.tiktok.actions.business.workflows.notifications.scan import (
        NEW_FOLLOWER_TYPE,
    )

    items = []
    for follower in followers or []:
        shown = (getattr(follower, "username", None) or (
            follower.get("username") if isinstance(follower, dict) else "") or "").strip()
        handle = resolved_handles.get(shown)
        if not handle:
            continue
        activity = getattr(follower, "activity", None)
        if activity is None and isinstance(follower, dict):
            activity = follower.get("activity")
        items.append({
            "type": NEW_FOLLOWER_TYPE,
            "username": handle,
            "time": activity or "",
            "label": shown,
        })

    if not items:
        return
    try:
        flags = record_scan_notifications(bot_username, items)
        logger.info(f"🔔 {sum(flags)} nouvelle(s) notification(s) enregistrée(s)")
    except Exception as exc:
        logger.warning(f"Enregistrement des notifications impossible: {exc}")


def _follow_back_decided(workflow, handles: List[str], notifier) -> List[Dict[str, Any]]:
    """Follow back through the SAME path the manual follow-back mode uses.

    UNVERIFIED on a phone: the qualification pass opens every listed profile before this runs,
    and TikTok's "New followers" section is a list of followers not yet seen. If opening the
    profiles clears it, `open_new_followers_page` will not find the section and every name here
    comes back `page_unavailable`. The workflow reports that per name rather than claiming a
    follow, so the failure is visible. If it happens, the fix is to follow from the profile the
    pass is already standing on, not to loosen the page check.
    """
    if not handles:
        return []
    logger.info(f"➕ Follow-back IA de {len(handles)} follower(s)")
    _emit(notifier, "status", "running", f"Following back {len(handles)} follower(s)")
    results = workflow.follow_back_users(handles)
    done = sum(1 for result in results if result.get("success"))
    logger.success(f"✅ Follow-back IA : {done}/{len(handles)}")
    return results


def _welcome_decided(handles: List[str], policy: WelcomePolicy, *, started, device_id, notifier,
                     outreach_notifier, workflow_hook, send_welcome_dms) -> Dict[str, Any]:
    """Send the welcome DMs the pass decided on, through the production cold-DM path.

    Two guards stand between a decision and a message. The account must be resolvable -- without
    one nothing could be recorded afterwards, so the same welcome would go out again at every
    run -- and the anti-duplicate guard must be able to ANSWER. `WelcomeDmGuard` returns UNKNOWN
    when it cannot, and UNKNOWN is refused: an outreach with no duplicate protection is worse
    than no outreach.
    """
    if not handles:
        return {"sent": False, "recipients": []}
    if not send_welcome_dms:
        logger.warning(f"✉️ Welcome DM non envoyé par cet hôte : {len(handles)} destinataire(s) décidé(s)")
        _emit(notifier, "log", "warning", f"Welcome DM not sent from this host: {len(handles)} recipient(s)")
        return {"sent": False, "recipients": list(handles), "reason": "not_sent_from_this_host"}
    if not policy.messages:
        logger.warning("✉️ Welcome DM demandé sans message fourni — rien envoyé")
        _emit(notifier, "log", "warning", "Welcome DM requested but no message text was provided")
        return {"sent": False, "recipients": list(handles), "reason": "no_message"}

    from taktik.core.database.tiktok_dm import (
        record_welcome_dm,
        resolve_account_id,
        sent_dm_already_recorded,
        thread_carries_our_message,
    )

    account_id = resolve_account_id(started.bot_username)
    if not account_id:
        logger.warning("✉️ Compte connecté non résolu — welcome DM annulé (rien ne serait enregistré)")
        _emit(notifier, "log", "warning", "Welcome DM cancelled: the logged-in account could not be resolved")
        return {"sent": False, "recipients": list(handles), "reason": "account_unresolved"}

    guard = WelcomeDmGuard(
        sent_dm_probe=sent_dm_already_recorded,
        thread_probe=thread_carries_our_message,
        log=_log,
    )
    allowed, skipped = guard.filter_recipients(account_id, handles)
    if skipped:
        logger.info(f"✉️ Welcome DM ignoré pour {len(skipped)} destinataire(s): {skipped}")
        _emit(notifier, "log", "info", f"Welcome DM skipped for {len(skipped)} recipient(s)")
    if not allowed:
        return {"sent": False, "recipients": list(handles), "skipped": skipped, "reason": "all_skipped"}

    from taktik.core.social_media.tiktok.actions.business.workflows.dm import outreach

    manager = started.manager
    outreach_workflow = outreach.TikTokDMOutreachWorkflow(
        device_id,
        notifier=outreach_notifier if outreach_notifier is not None else notifier,
        # The guard runs again inside the workflow, right before each send. The list was
        # filtered minutes and several profile visits ago; the last word belongs to the check
        # that happens where the message would actually leave.
        duplicate_checker=guard.as_duplicate_checker(),
        sent_dm_recorder=record_welcome_dm,
        # Reuse the session the startup already opened rather than connecting a second time:
        # the outreach path restarts TikTok itself, which is the clean state it wants.
        manager_factory=lambda device_id=None: manager,
    )
    if not outreach_workflow.connect():
        logger.error("✉️ Impossible de réutiliser la session device pour le welcome DM")
        _emit(notifier, "log", "warning", "Welcome DM skipped: device session unavailable")
        return {"sent": False, "recipients": list(handles), "skipped": skipped, "reason": "session_unavailable"}

    if workflow_hook is not None:
        workflow_hook(outreach_workflow)
    _emit(notifier, "status", "running", f"Welcoming {len(allowed)} new follower(s)")
    result = outreach_workflow.run(
        allowed,
        list(policy.messages),
        delay_min=policy.delay_min,
        delay_max=policy.delay_max,
        max_dms=policy.max_dms,
        account_id=account_id,
        session_id=str(device_id),
    )
    logger.success(
        f"✅ Welcome DM: {result.get('dms_success', 0)} envoyé(s), "
        f"{result.get('dms_failed', 0)} échec(s)"
    )
    return {"sent": True, "recipients": list(allowed), "skipped": skipped, "result": result}


__all__ = ["Qualifier", "QualifierFactory", "run_welcome_pass"]
