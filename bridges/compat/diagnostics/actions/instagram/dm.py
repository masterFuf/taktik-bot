"""DM engagement actions for Instagram compat diagnostics (Cartography Lab).

These actions drive the **real production DM runtime** — the same reader / navigation / sender
mixins under ``taktik/core/social_media/instagram/workflows/dm_inbox/**`` that the desktop front pilots — bound
to the warm Lab device, so the Lab tests the EXACT prod code path step by step. (It previously
drove ``DMAutoReplyWorkflow``, a CLI-only engine since removed, so the probes were validating
non-production code. Rule: reuse the real production function.)

Privacy: DM body content is NEVER passed through ``logger`` calls (only counts / usernames are
logged). ``dm.read_last_incoming`` returns the read text in its result so the tester can verify
the read worked — same data path the prod reader/persistence already use.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


def _dm_runtime(a):
    """Bind the production DM runtime (workflows/dm_inbox) to the warm Lab device.

    Extends ``DMRuntime`` — the very composition ``DMBridge`` is built on — rather than
    re-listing its mixins here: a mixin added to the prod runtime then reaches the Lab
    on its own, where a parallel mixin list would have kept passing while testing an
    older capability set.

    The runtime reads a small attribute surface (``device``, ``screen_width/height``,
    ``_keyboard``), so we bind the raw uiautomator2 device the Lab facade exposes and
    supply the rest. Every method runs the exact prod code on the warm device — no
    second connection, no app restart."""
    from taktik.core.social_media.instagram.workflows.dm_inbox.runtime import DMRuntime
    from bridges.common.input.keyboard import KeyboardService

    class _LabDMRuntime(DMRuntime):
        def __init__(self, facade):
            # The prod mixins expect a raw u2 device (self.device(...), .xpath, .long_click, .info);
            # the Lab facade exposes it as `.device`.
            self.device = getattr(facade, "device", facade)
            device_id = getattr(facade, "device_id", None) or "lab"
            # The shared composer atomic types on a NAMED device: without this the Lab runtime
            # would hit its "device_id is required" guard instead of silently typing elsewhere.
            self.device_id = device_id
            try:
                info = self.device.info
                self.screen_width = int(info.get("displayWidth") or 1080)
                self.screen_height = int(info.get("displayHeight") or 1920)
            except Exception:
                self.screen_width, self.screen_height = 1080, 1920
            self._keyboard = KeyboardService(device_id)

    return _LabDMRuntime(a.device)


@action("dm.open_inbox")
def open_inbox(a, p):
    """Navigate to the Direct (DM) inbox via the PROD runtime (``navigate_to_dm_inbox``)."""
    ok = _dm_runtime(a).navigate_to_dm_inbox()
    return {"success": bool(ok), "message": "DM inbox open" if ok else "could not open DM inbox"}


@action("dm.list_unread")
def list_unread(a, p):
    """Run the PROD conversation reader (``read_conversations``) and list what it found (username +
    message count per conversation). Message bodies are NOT returned/logged here. Param: limit
    (optional, default 5; <= 0 = read all). Be on the DM inbox."""
    try:
        limit = int(p.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5
    convs = _dm_runtime(a).read_conversations(limit) or []
    items = []
    for c in convs:
        get = c.get if isinstance(c, dict) else (lambda k, d=None: getattr(c, k, d))
        items.append({
            "username": get("username") or get("real_username"),
            "messages": len(get("messages", []) or []),
        })
    logger.info(f"dm.list_unread: prod reader returned {len(items)} conversation(s)")
    return {"success": True, "count": len(items), "conversations": items,
            "message": f"{len(items)} conversation(s) read"}


@action("dm.open_thread")
def open_thread(a, p):
    """Open the conversation thread of ``username`` via the PROD runtime (``open_conversation``).
    Param: username (required). Be on the DM inbox."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    ok = _dm_runtime(a).open_conversation(username)
    return {"success": bool(ok), "message": f"thread @{username} open={ok}"}


@action("dm.read_last_incoming")
def read_last_incoming(a, p):
    """Read the LAST incoming message of the OPEN thread via the PROD message extractor
    (``_collect_text_messages``: left/right bounds heuristic, skips our own replies). A thread
    must be open. Returns the text to the Lab UI; the content is not logged."""
    msgs = _dm_runtime(a)._collect_text_messages() or []
    incoming = [m for m in msgs if not m.get("is_sent")]
    text = incoming[-1]["text"] if incoming else None
    logger.info(f"dm.read_last_incoming: {'message read' if text else 'none'} ({len(text or '')} chars)")
    return {"success": bool(text),
            "message": f"read {len(text or '')} chars" if text else "no incoming message",
            "details": {"text": text}}


@action("dm.send_reply")
def send_reply(a, p):
    """Type + send a reply in the OPEN thread via the PROD sender (``send_message``, Taktik
    keyboard). Param: text (required). A thread must be open."""
    text = (p.get("text") or "").strip()
    if not text:
        return {"success": False, "message": "text param is required"}
    ok = _dm_runtime(a).send_message(text)
    return {"success": bool(ok), "message": "reply sent" if ok else "reply failed"}


@action("dm.back_to_inbox")
def back_to_inbox(a, p):
    """Go back from an open thread to the inbox via the PROD runtime
    (``_go_back_from_conversation``)."""
    _dm_runtime(a)._go_back_from_conversation()
    return {"success": True, "message": "back to inbox"}


def _flag(p, name, default):
    value = p.get(name, default)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "oui")
    return bool(value)


def _cold_dm_runtime(a):
    """The production cold DM workflow (`ColdDMWorkflow`, the core's one engine) bound to the warm
    Lab device: the class itself, so a step changed in the workflow reaches the Lab on its own. No
    second connection, no app restart; the profile reads use the Lab's detection."""
    from bridges.common.input.keyboard import KeyboardService
    from taktik.core.social_media.instagram.workflows.cold_dm.workflow import ColdDMWorkflow

    class _LabColdDMWorkflow(ColdDMWorkflow):
        def __init__(self, bundle):
            facade = bundle.device
            # The prod mixins drive a raw (proxied) u2 device; the Lab facade exposes it as `.device`.
            self.device = getattr(facade, "device", facade)
            self.device_id = getattr(facade, "device_id", None) or "lab"
            self._keyboard = KeyboardService(self.device_id)
            self._detection = bundle.detection

        def _cold_dm_detection(self):
            return self._detection

    return _LabColdDMWorkflow(a)


@action("dm.send_cold_dm")
def send_cold_dm(a, p):
    """Cold DM to ONE recipient through the production steps of the cold DM workflow
    (`ColdDMWorkflow.reach_and_send`): search, profile, the recipient policy (skipPrivate default
    true, skipVerified default false, as the page sends them), conversation, send. Params: username
    and text (required). Not written to the base: the Lab has no session."""
    from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import (
        ColdDmRecipientPolicy,
    )

    username = (p.get("username") or "").strip().lstrip("@")
    text = (p.get("text") or "").strip()
    if not username or not text:
        return {"success": False, "message": "username and text params are required"}
    policy = ColdDmRecipientPolicy(skip_private=_flag(p, "skipPrivate", True),
                                   skip_verified=_flag(p, "skipVerified", False))
    reached = _cold_dm_runtime(a).reach_and_send(username, lambda: text, policy)
    outcome = reached["outcome"]
    sent = outcome == "sent" and bool(reached.get("send_result"))
    return {"success": sent,
            "message": f"cold DM to @{username}: {outcome}" + ("" if outcome != "sent" else f" ({reached.get('send_result')})"),
            "details": {"outcome": outcome, "send_result": reached.get("send_result")}}


@action("dm.cold_dm_check_profile")
def cold_dm_check_profile(a, p):
    """Cold DM decision on the OPEN profile, without tapping: the production evaluation of the
    cold DM bridge (``ColdDMNavigationMixin.evaluate_cold_dm_profile``: the profile detector,
    then private notice, Message button, certified badge and ``cold_dm_skip_reason``). Params:
    skipPrivate (default true), skipVerified (default false), as the page sends them. Off a
    PROFILE screen it fails and reads nothing, as the workflow does."""
    from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import (
        ColdDmRecipientPolicy,
    )

    policy = ColdDmRecipientPolicy(skip_private=_flag(p, "skipPrivate", True),
                                   skip_verified=_flag(p, "skipVerified", False))
    verdict = _cold_dm_runtime(a).evaluate_cold_dm_profile(policy)
    verdict.pop("message_button", None)
    if not verdict["on_profile"]:
        return {"success": False, "message": "not on a profile: nothing evaluated",
                "details": verdict}
    reason = verdict["skip_reason"]
    if reason:
        message = f"skip ({reason})"
    elif verdict["has_message_button"]:
        message = "DM would be attempted"
    else:
        message = "no Message button: the DM would fail"
    return {"success": True, "message": message, "details": verdict}
