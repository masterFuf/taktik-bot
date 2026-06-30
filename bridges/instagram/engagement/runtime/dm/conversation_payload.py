"""Pure data helpers for Instagram DM conversation reading."""

from typing import Optional

_ELLIPSIS_MARKERS = ("…", "...")


def sort_threads_by_top(threads) -> list[tuple[int, object]]:
    """Return inbox threads sorted by their top bound, ignoring malformed items."""
    threads_with_pos = []
    for thread in threads:
        try:
            bounds = thread.info.get("bounds", {})
            top = bounds.get("top", 0)
            threads_with_pos.append((top, thread))
        except Exception:
            continue
    threads_with_pos.sort(key=lambda item: item[0])
    return threads_with_pos


def extract_inbox_username(content_desc: str) -> str:
    if content_desc:
        parts = content_desc.split(",")
        if parts:
            return parts[0].strip()
    return "Unknown"


def normalize_inbox_username(username: str) -> tuple[str, str]:
    username_lower = username.lower().strip()
    return username_lower, username_lower.rstrip(".").strip()


def is_already_processed(username_base: str, processed_usernames: set[str]) -> bool:
    for processed in processed_usernames:
        processed_base = processed.rstrip(".").strip()
        if (
            username_base == processed_base
            or username_base.startswith(processed_base)
            or processed_base.startswith(username_base)
        ):
            return True
    return False


def is_outgoing_last_message(content_desc: str, username: str, outgoing_prefixes) -> bool:
    """True when the inbox row shows WE sent the last message (no incoming preview).

    IG renders the row digest as "Sent <time>" / "Envoyé il y a <time>" when our message is
    the last one, vs the interlocutor's message text when they wrote last. Detecting this from
    the row's content-desc lets us skip re-opening conversations we already answered.
    """
    if not content_desc:
        return False
    rest = content_desc
    if username and content_desc.startswith(username):
        rest = content_desc[len(username):]
    rest = rest.lstrip(", ").strip()
    return any(rest.startswith(prefix) for prefix in outgoing_prefixes if prefix)


def _normalize_preview(text: str) -> str:
    """Lowercase + collapse whitespace so two renderings of the same text compare equal."""
    return " ".join((text or "").split()).strip().lower()


def _strip_username_prefix(content_desc: str, username: str) -> str:
    """Drop the leading 'username, ' part of an inbox row content-desc (same as the outgoing
    digest check) so what remains starts with the last-message preview."""
    rest = content_desc or ""
    if username and rest.startswith(username):
        rest = rest[len(username):]
    return rest.lstrip(", ").strip()


def _truncated_preview_prefix(preview: str) -> Optional[str]:
    """The visible message prefix before IG's truncation ellipsis, or None if not truncated."""
    for marker in _ELLIPSIS_MARKERS:
        idx = preview.find(marker)
        if idx > 0:
            return preview[:idx].strip()
    return None


def inbox_preview_matches_known(
    content_desc: str, username: str, known_text: str, *, min_chars: int = 6
) -> bool:
    """Conservative: True only when the inbox row's last-message preview is the SAME message
    we already stored for this thread (i.e. no new activity).

    The row content-desc embeds the last message text, often truncated with an ellipsis. We
    return True only when confident, so we never skip reading a genuine new reply:
    - non-truncated row: the full stored message must appear verbatim in the row;
    - truncated row: the visible preview prefix must be a prefix of the stored message.
    Very short messages (< ``min_chars``, e.g. "ok", a lone emoji) never match — too ambiguous.
    """
    if not content_desc or not known_text:
        return False
    norm_known = _normalize_preview(known_text)
    if len(norm_known) < min_chars:
        return False
    if norm_known in _normalize_preview(content_desc):
        return True
    cut = _truncated_preview_prefix(_strip_username_prefix(content_desc, username))
    if cut:
        norm_cut = _normalize_preview(cut)
        return len(norm_cut) >= min_chars and norm_known.startswith(norm_cut)
    return False


def has_unseen_incoming(messages: list, known_received_texts) -> bool:
    """True when a VISIBLE received message is not already on record — i.e. a genuinely NEW
    incoming message. Used to decide whether a thread we already answered (a sent message is on
    record) whose reply vanished (IG ephemeral mode) should stay answered or be re-opened for a
    reply. Conservative: a received message that doesn't normalise to a known one counts as new."""
    known = {_normalize_preview(text) for text in (known_received_texts or []) if text}
    for message in messages or []:
        if message.get("is_sent"):
            continue
        text = message.get("text")
        if text and _normalize_preview(text) not in known:
            return True
    return False


def build_up_to_date_conversation(
    *, real_username: str, inbox_username: str, last_is_ours: bool
) -> dict:
    """A lightweight 'already up to date' conversation — emitted without opening the thread
    because its last message is already on record (no new activity). The front restores the
    full history from the DB; ``up_to_date`` flags WHY it was emitted empty (vs. a fresh read)."""
    return {
        "username": real_username,
        "inbox_username": inbox_username,
        "messages": [],
        "is_group": False,
        # Still replyable when THEIR message is the last one (we just don't need to re-read it).
        "can_reply": not last_is_ours,
        "last_message_is_ours": last_is_ours,
        "up_to_date": True,
    }


def build_answered_conversation(*, real_username: str, inbox_username: str) -> dict:
    """A lightweight 'already answered' conversation (we sent the last message) — emitted
    without opening the thread. The full history (if any) is restored from the DB on the
    front side; here we only flag it as answered so the inbox triage stays accurate."""
    return {
        "username": real_username,
        "inbox_username": inbox_username,
        "messages": [],
        "is_group": False,
        "can_reply": False,
        "last_message_is_ours": True,
    }


def build_conversation_payload(
    *,
    real_username: str,
    inbox_username: str,
    messages: list,
    is_group: bool,
    can_reply: bool,
) -> dict:
    last_message_is_ours = bool(messages and messages[-1].get("is_sent", False))
    return {
        "username": real_username,
        "inbox_username": inbox_username,
        "messages": messages,
        "is_group": is_group,
        "can_reply": False if last_message_is_ours else can_reply,
        "last_message_is_ours": last_message_is_ours,
    }


__all__ = [
    "build_answered_conversation",
    "build_conversation_payload",
    "build_up_to_date_conversation",
    "extract_inbox_username",
    "has_unseen_incoming",
    "inbox_preview_matches_known",
    "is_already_processed",
    "is_outgoing_last_message",
    "normalize_inbox_username",
    "sort_threads_by_top",
]
