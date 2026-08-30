#!/usr/bin/env python3
"""TikTok new-followers workflow bridge runner (inbox v2 - Phase 1).

Two modes, set by the config:
- scrape, the default: open the new-followers page, list the items and emit them
    without acting, so the front can display them and the user select.
- follow_back: follow back the selected usernames and emit one result event per
    username.

On top of `scrape`, an OPTIONAL AI welcome pass: qualify each new follower's profile and let
the verdict decide whether to follow back and whether to send a welcome DM. It is off unless
BOTH `ai.enabled` and `ai.newFollowers.enabled` are set — a run that says nothing about AI
scrapes and stops, exactly as it did before. See `services/welcome/decision.py` for the block.

The DM itself is not written here and not sent here: the texts come from the app (which holds
the account persona) and the send goes through the production cold-DM path, which navigates by
verified arrival and confirms a send by the composer EMPTYING rather than by the click landing.

VERIFIED ON DEVICE 2026-08-30, and exactly this far. A real new follower was produced between the
two test accounts, and the pass then: read the list (3 followers), opened each row, resolved each
one to its REAL handle, and qualified all three with a reason. The strongest of those: the inbox
showed `"vic............"` — a display name whose emoji the XML dump ate — and the pass came back
with `@vic961226`.

What that run also settled, and what the first attempts got wrong: this page shows a DISPLAY NAME
and never a handle, so `navigate_to_user_profile` cannot be the way in. Handing it the display
name reported `profile_unreachable` for every follower it had just listed. The row is opened
instead, and the handle is read off the profile that opens — which also keeps the verdict from
being filed under a username nobody has.

STILL UNVERIFIED: the follow-back and the DM themselves. The AI declined all three followers
(`not_relevant`, score 0.00 — they are small personal accounts and the operated account is a
niche one), which is a legitimate outcome and not a failure, but it means no send has run. The
send is left to the atomic that measures its own outcome rather than to a claim made here.

The desktop side is also not wired yet: `TikTokNewFollowersStdoutService.handleScrapeOutput`
routes `new_follower`/`status`/`error` only, so the `ai_relevance`, `follow_back_result` and
`dm_result` lines this pass emits are dropped by the front until it is taught to read them.
"""

import os
import sqlite3
from dataclasses import replace
from typing import Any, Dict, List, Optional

from bridges.tiktok.runtime.ipc import (
    logger,
    send_error,
    send_log,
    send_profile_classification,
    send_relevance,
    send_status,
    set_workflow,
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.engagement.runtime.dm_callbacks import (
    wire_follow_back_callbacks,
    wire_new_followers_read_callbacks,
)
from bridges.tiktok.workflows.engagement.runtime.dm_persistence import (
    record_sent,
    resolve_account_id,
)
from taktik.core.social_media.tiktok.services.welcome import (
    NewFollowerWelcomePass,
    WelcomeDmGuard,
    follow_back_targets,
    parse_welcome_policy,
    summarize,
    welcome_dm_targets,
)

_PLATFORM = "tiktok"


def _bridge_log(level: str, message: str) -> None:
    """Core -> loguru adapter. stderr only: stdout carries the bridge's JSON contract."""
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def run_new_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok new-followers workflow (scrape ou follow-back)."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    mode = config.get("mode", "scrape")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
            DMConfig,
            DMWorkflow,
        )

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)

        workflow_config = DMConfig(
            delay_between_conversations=config.get("delayBetweenActions", 1.0),
        )
        workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)

        if mode == "follow_back":
            usernames = config.get("usernames", [])
            if not usernames:
                send_error("No usernames to follow back")
                return False

            logger.info(f"➕ Follow-back de {len(usernames)} follower(s) sur {device_id}")
            send_status("running", f"Following back {len(usernames)} follower(s)")

            wire_follow_back_callbacks(workflow)
            results = workflow.follow_back_users(usernames)
            done = sum(1 for r in results if r.get("success"))

            logger.success(f"✅ Follow-back terminé : {done}/{len(usernames)}")
            send_status("completed", f"Followed back {done}/{len(usernames)}")
            return True

        # mode == "scrape"
        max_items = config.get("maxItems", 50)
        logger.info(f"👥 Scrape des nouveaux followers sur {device_id} (max {max_items})")
        send_status("running", "Reading new followers")

        wire_new_followers_read_callbacks(workflow)
        followers = workflow.read_new_followers(max_items=max_items)

        logger.success(f"✅ {len(followers)} nouveaux followers listés")

        # The AI pass runs only when the config asked for it, by name. Reading the list is what
        # this mode promises; anything beyond that has to be requested.
        policy = parse_welcome_policy(config.get("ai"))
        if policy.enabled and followers:
            _run_welcome_pass(config, manager, workflow, bot_username, followers, policy)

        send_status("completed", f"Listed {len(followers)} new followers")
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"New followers error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


# ---------------------------------------------------------------------------
# AI welcome pass
# ---------------------------------------------------------------------------


def _run_welcome_pass(config, manager, workflow, bot_username, followers, policy) -> None:
    """Qualify each new follower, then act on the decisions. Never fails the scrape.

    A broken AI setup, an unreachable database or a refused guard must cost the welcome pass,
    not the list the operator asked for — which is already emitted and persisted by then.
    """
    try:
        from bridges.tiktok.workflows.automation.runtime.ai import create_tiktok_ai_service
        from taktik.core.social_media.tiktok.actions.atomic.navigation.navigation_actions import (
            NavigationActions,
        )
        from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
            build_tiktok_profile_qualifier,
        )

        ai_config = config.get("ai") or {}
        ai_enabled, ai_service = create_tiktok_ai_service(
            ai_config=ai_config, ipc=None, log=_bridge_log
        )
        if not ai_enabled or ai_service is None:
            # No service means no verdict, and no verdict means no decision. Falling back to
            # "follow everyone back" here would be the run doing something nobody asked for.
            logger.warning("🤖 Passe IA demandée mais aucun service IA disponible — aucune décision prise")
            send_log("warning", "AI welcome pass skipped: no AI service available")
            return

        device = manager.device_manager.device
        navigation = NavigationActions(device)  # noqa: F841 — kept for the back-navigation below

        # The new-followers page shows a DISPLAY NAME and never a handle. Handing that name to
        # `navigate_to_user_profile` searches for somebody who does not exist under it, which is
        # why the first device run of this pass reported `profile_unreachable` for all three
        # followers it had just listed. The row is opened instead, and the profile it opens is
        # where the real handle is read.
        from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
        from taktik.core.social_media.tiktok.services.navigation.reset import (
            return_to_tiktok_shell,
        )

        dm_actions = DMActions(device)
        # shown name -> the handle its profile turned out to carry.
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

        # NOTE: `install_profile_ai_hooks` is NOT used here on purpose. It patches
        # `VideoInteractionMixin._interact_with_profile_posts`, which only the Followers and
        # Target-profiles workflows enter; DMWorkflow does not inherit that mixin, so the hook
        # would install cleanly, log "installed" and never fire once. The qualifier below is
        # the same function that hook runs, called directly.
        qualify = build_tiktok_profile_qualifier(
            ai_service,
            ai_config,
            log=_bridge_log,
            emit_relevance=lambda username, payload: send_relevance(
                username,
                relevant=payload.get("relevant"),
                score=payload.get("score"),
                reason=payload.get("reason"),
                follow=payload.get("follow"),
                comment=payload.get("comment"),
                like=payload.get("like"),
            ),
            emit_classification=lambda username, classification: send_profile_classification(
                username,
                classification,
                result=f"[{classification.get('niche_category', '?')}] {classification.get('niche', '?')}",
            ),
            language=config.get("language") or config.get("appLanguage") or "en",
        )

        send_status("running", f"Qualifying {len(followers)} new follower(s)")
        welcome_pass = NewFollowerWelcomePass(
            policy=policy,
            visit_profile=_visit,
            qualify=_qualify_visited,
            log=_bridge_log,
        )
        decisions = welcome_pass.decide(followers)

        # Every decision travels under the handle its profile carried, so what follows — the
        # follow-back, the DM, the duplicate guard — addresses the person and not the label the
        # inbox happened to print. Rebuilt rather than mutated: `WelcomeDecision` is frozen, and
        # deliberately so.
        decisions = [
            replace(decision, username=resolved_handles[decision.username])
            if resolved_handles.get(decision.username)
            else decision
            for decision in decisions
        ]
        stats = summarize(decisions)
        logger.info(f"🤖 Décisions IA: {stats}")
        send_log("info", f"AI welcome pass: {stats}")

        # The attribution's raw material, and it costs nothing here: every profile has just been
        # opened and every handle is already in hand. Recording it lets the front answer "of the
        # people who followed us, how many had we engaged first?" -- see
        # bridges/tiktok/engagement/runtime/notifications/persistence.py. A separate scan would
        # have opened the same profiles a second time for the same thirteen seconds apiece.
        _record_followers_as_notifications(bot_username, followers, resolved_handles)

        _follow_back_decided(workflow, follow_back_targets(decisions))
        _welcome_decided(config, manager, bot_username, welcome_dm_targets(decisions), policy)

    except Exception as exc:
        logger.error(f"Passe IA nouveaux followers en échec: {exc}")
        send_log("warning", f"AI welcome pass failed: {exc}")


def _record_followers_as_notifications(
    bot_username: Optional[str],
    followers: List[Any],
    resolved_handles: Dict[str, str],
) -> None:
    """Write one `new_follower` notification per resolved follower. Best-effort, never raises.

    Only the resolved ones. A row filed under a display name joins to nothing, so the follower
    would read as "never engaged" -- a confident wrong answer, and worse than no row at all.
    """
    from bridges.tiktok.engagement.runtime.notifications.scan import NEW_FOLLOWER_TYPE
    from bridges.tiktok.engagement.runtime.notifications.persistence import (
        record_scan_notifications,
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


def _follow_back_decided(workflow, handles: List[str]) -> None:
    """Follow back through the SAME path the manual follow-back mode uses.

    UNVERIFIED (no device available for this lot): the qualification pass opens every listed
    profile before this runs, and TikTok's "New followers" section is a list of followers not
    yet seen. If opening the profiles clears it, `open_new_followers_page` will not find the
    section and every name here comes back `page_unavailable`. The workflow reports that per
    name rather than claiming a follow, so the failure is visible — but whether it happens can
    only be measured on a phone. If it does, the fix is to follow from the profile the pass is
    already standing on, not to loosen the page check.
    """
    if not handles:
        return
    logger.info(f"➕ Follow-back IA de {len(handles)} follower(s)")
    send_status("running", f"Following back {len(handles)} follower(s)")
    wire_follow_back_callbacks(workflow)
    results = workflow.follow_back_users(handles)
    done = sum(1 for result in results if result.get("success"))
    logger.success(f"✅ Follow-back IA : {done}/{len(handles)}")


def _welcome_decided(config, manager, bot_username, handles: List[str], policy) -> None:
    """Send the welcome DMs the pass decided on, through the production cold-DM path.

    Two guards stand between a decision and a message. The account must be resolvable — without
    one nothing could be recorded afterwards, so the same welcome would go out again at every
    run — and the anti-duplicate guard must be able to ANSWER. `WelcomeDmGuard` returns UNKNOWN
    when it cannot, and UNKNOWN is refused: an outreach with no duplicate protection is worse
    than no outreach.
    """
    if not handles:
        return
    if not policy.messages:
        logger.warning("✉️ Welcome DM demandé sans message fourni — rien envoyé")
        send_log("warning", "Welcome DM requested but no message text was provided")
        return

    account_id = resolve_account_id(bot_username)
    if not account_id:
        logger.warning("✉️ Compte connecté non résolu — welcome DM annulé (rien ne serait enregistré)")
        send_log("warning", "Welcome DM cancelled: the logged-in account could not be resolved")
        return

    guard = WelcomeDmGuard(
        sent_dm_probe=sent_dm_already_recorded,
        thread_probe=thread_carries_our_message,
        log=_bridge_log,
    )
    allowed, skipped = guard.filter_recipients(account_id, handles)
    if skipped:
        logger.info(f"✉️ Welcome DM ignoré pour {len(skipped)} destinataire(s): {skipped}")
        send_log("info", f"Welcome DM skipped for {len(skipped)} recipient(s)")
    if not allowed:
        return

    from bridges.tiktok.engagement.runtime.dm_outreach import BridgeNotifier
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach import (
        TikTokDMOutreachWorkflow,
    )

    device_id = config.get("deviceId")
    outreach = TikTokDMOutreachWorkflow(
        device_id,
        notifier=BridgeNotifier(),
        # The guard runs again inside the workflow, right before each send. The list was
        # filtered minutes and several profile visits ago; the last word belongs to the check
        # that happens where the message would actually leave.
        duplicate_checker=guard.as_duplicate_checker(),
        sent_dm_recorder=_record_welcome_dm,
        # Reuse the session `tiktok_startup` already opened rather than connecting a second
        # time: the outreach path restarts TikTok itself, which is the clean state it wants.
        manager_factory=lambda device_id=None: manager,
    )
    if not outreach.connect():
        logger.error("✉️ Impossible de réutiliser la session device pour le welcome DM")
        send_log("warning", "Welcome DM skipped: device session unavailable")
        return

    set_workflow(outreach)
    send_status("running", f"Welcoming {len(allowed)} new follower(s)")
    result = outreach.run(
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


# ---------------------------------------------------------------------------
# Anti-duplicate probes
# ---------------------------------------------------------------------------
# These go to the repositories rather than to `SentDMService` / `DmConversationService`, and
# they RAISE instead of returning False. Both services catch Exception and answer False, which
# reads as "never contacted" whether nobody was written to or the query blew up — that swallow
# is how Instagram's cold DM ran for months with no duplicate protection at all. `WelcomeDmGuard`
# turns a raise into UNKNOWN and refuses the send; a False here would be a blind outreach.


def _open_database() -> sqlite3.Connection:
    """Open the local database, or raise. A missing file is a refusal, not an empty answer."""
    from taktik.core.database.local.paths import get_default_database_path

    db_path = get_default_database_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"local database not found at {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def sent_dm_already_recorded(account_id: int, handle: str) -> bool:
    """Has this account already written to @handle on TikTok? Raises when it cannot answer.

    `sent_dms` is SHARED with the cold DM workflow on purpose: someone we already wrote to is
    not a stranger to greet, whichever flow wrote first.
    """
    from taktik.core.database.repositories.messaging import SentDMRepository

    connection = _open_database()
    try:
        return SentDMRepository(connection).check_already_sent(account_id, handle, _PLATFORM)
    finally:
        connection.close()


def thread_carries_our_message(account_id: int, handle: str) -> bool:
    """Does a thread with @handle already hold a message WE sent? Raises when it cannot answer.

    `sent_dms` alone misses a conversation started from the inbox — a manual answer, an
    auto-reply, the DM read workflow — and none of those write that marker.
    """
    from taktik.core.database.repositories.messaging import (
        DmMessageRepository,
        DmThreadRepository,
    )

    connection = _open_database()
    try:
        threads = DmThreadRepository(connection)
        # `find_sync_id_for_inbox` does not create the tables itself; on a standalone database
        # the desktop has never opened, the lookup would raise and refuse every recipient.
        threads.ensure_table()
        sync_id = threads.find_sync_id_for_inbox(_PLATFORM, account_id, handle)
        if not sync_id:
            return False
        return DmMessageRepository(connection).has_sent_message(_PLATFORM, sync_id)
    finally:
        connection.close()


def _record_welcome_dm(
    account_id: int,
    recipient: str,
    message: str,
    success: bool,
    error_message: Optional[str] = None,
    session_id: Optional[str] = None,
    platform: str = _PLATFORM,
) -> None:
    """Record a SENT welcome DM: the shared duplicate marker + the conversation itself.

    Only successes. `check_already_sent` matches a row whatever its `success` value, so writing
    a failed attempt would lock that recipient out of every later one — the opposite of what a
    failure means. The cost is stated rather than hidden: a privacy-blocked account is visited
    again on the next run, which spends a profile visit and sends nothing.
    """
    if not success:
        logger.info(f"✉️ Welcome DM non abouti pour @{recipient} ({error_message or 'send failed'})")
        return

    from bridges.common.persistence.database import SentDMService

    try:
        SentDMService.record(account_id, recipient, message, True, None, session_id, platform=platform)
    except Exception as exc:
        logger.warning(f"[WELCOME] Marqueur sent_dms non écrit pour @{recipient}: {exc}")
    # The certain half of the direction question: the TikTok reader cannot see who wrote a
    # bubble, so a later inbox read recognises our own message only from this row.
    record_sent(account_id, recipient, message)


__all__ = [
    "run_new_followers_workflow",
    "sent_dm_already_recorded",
    "thread_carries_our_message",
]
