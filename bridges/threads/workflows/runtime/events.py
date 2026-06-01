"""Shared Threads workflow IPC event adapters."""

from bridges.threads.base import (
    send_log,
    send_status,
    send_threads_action,
    send_threads_profile_visit,
    send_threads_stats,
)


def build_threads_callbacks() -> dict:
    """Return callbacks expected by Threads core workflows."""

    def forward_log(level: str, message: str) -> None:
        send_log(level, message)

    def forward_stats(stats) -> None:
        send_threads_stats(**stats.as_dict())

    def forward_profile_visit(info: dict) -> None:
        send_threads_profile_visit(
            username=info.get("username") or "",
            followers=info.get("followers"),
            is_private=bool(info.get("is_private", False)),
        )

    def forward_action(action: str, username: str, details: dict) -> None:
        send_threads_action(action, username, details)

    return {
        "on_log": forward_log,
        "on_stats": forward_stats,
        "on_profile_visit": forward_profile_visit,
        "on_action": forward_action,
    }


def emit_threads_completion(prefix: str, stats) -> None:
    """Emit final stats and completion status for a Threads workflow."""
    send_threads_stats(**stats.as_dict())
    summary = (
        f"visited={stats.profiles_visited} follows={stats.follows} "
        f"likes={stats.likes} reposts={stats.reposts} errors={stats.errors}"
    )
    send_status("completed", f"{prefix} finished - {summary}")


__all__ = ["build_threads_callbacks", "emit_threads_completion"]
