"""Pure data helpers for Instagram DM conversation reading."""


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
    "extract_inbox_username",
    "is_already_processed",
    "is_outgoing_last_message",
    "normalize_inbox_username",
    "sort_threads_by_top",
]
