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
    "build_conversation_payload",
    "extract_inbox_username",
    "is_already_processed",
    "normalize_inbox_username",
    "sort_threads_by_top",
]
