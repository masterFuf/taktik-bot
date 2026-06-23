"""CLI command handling for the Instagram notifications engagement bridge."""

from __future__ import annotations

import sys

from bridges.instagram.engagement.runtime.notifications.bridge import NotificationsBridge
from bridges.instagram.engagement.runtime.notifications.events import emit_notif_error, emit_notif_json
from bridges.instagram.runtime.ipc import logger


def _connect(device_id: str, package_name: str = None, *, restart: bool = True) -> NotificationsBridge:
    bridge = NotificationsBridge(device_id, package_name=package_name)
    if not bridge.connect():
        emit_notif_error("Failed to connect to device")
        sys.exit(1)
    # Only the scan entry point restarts Instagram (fresh state). Per-row actions
    # (accept/ignore/reply) operate on the screen the user just scanned, so they
    # skip the costly force-stop + relaunch and just navigate from the current state.
    if restart:
        bridge.restart_instagram()
    return bridge


def cmd_scan(device_id: str, limit: int, package_name: str = None) -> None:
    """Read + classify the activity feed (all notification families)."""
    bridge = _connect(device_id, package_name, restart=True)
    # `limit` is interpreted as how many extra screens to scroll (0 = visible only).
    workflow = bridge.build_workflow()
    result = workflow.scan(max_scrolls=max(0, limit))
    emit_notif_json({
        "type": "result",
        "command": "scan",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "by_type": result.get("by_type", {}),
        "items": result.get("items", []),
        "requests": result.get("requests", []),
        "has_grouped_requests": result.get("has_grouped_requests", False),
        "message": result.get("message", ""),
    }, flush=True)


def cmd_list_requests(device_id: str, limit: int, package_name: str = None) -> None:
    """Enumerate pending follow requests (usernames) on the sub-screen."""
    bridge = _connect(device_id, package_name, restart=False)
    workflow = bridge.build_workflow()
    result = workflow.list_requests(max_requests=limit if limit > 0 else 50)
    emit_notif_json({
        "type": "result",
        "command": "list_requests",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "requests": result.get("requests", []),
        "message": result.get("message", ""),
    }, flush=True)


def cmd_accept(device_id: str, username: str, package_name: str = None) -> None:
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().accept_request(username)
    emit_notif_json({"type": "result", "command": "accept", **result}, flush=True)


def cmd_ignore(device_id: str, username: str, package_name: str = None) -> None:
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().ignore_request(username)
    emit_notif_json({"type": "result", "command": "ignore", **result}, flush=True)


def cmd_accept_all(device_id: str, limit: int, package_name: str = None) -> None:
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().accept_all_requests(max_requests=limit if limit > 0 else 50)
    emit_notif_json({
        "type": "result",
        "command": "accept_all",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "accepted": result.get("accepted", []),
        "message": result.get("message", ""),
    }, flush=True)


def cmd_reply(device_id: str, username: str, package_name: str = None) -> None:
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().open_mention(username)
    emit_notif_json({"type": "result", "command": "reply", **result}, flush=True)


def cmd_like(device_id: str, username: str, package_name: str = None) -> None:
    """Like the comment / mention of ``username`` inline from the feed."""
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().like_comment(username)
    emit_notif_json({"type": "result", "command": "like", **result}, flush=True)


def run_notifications_cli(args: list[str]) -> None:
    """Parse notifications bridge CLI args and dispatch the selected command."""
    package_name = None
    if "--package" in args:
        idx = args.index("--package")
        if idx + 1 < len(args):
            package_name = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if not args:
        emit_notif_error(
            "Usage: notifications.py <command> [args] [--package <pkg>]\n"
            "  scan <device_id> [scroll]\n"
            "  list_requests <device_id> [limit]\n"
            "  accept <device_id> <username>\n"
            "  ignore <device_id> <username>\n"
            "  accept_all <device_id> [max]\n"
            "  reply <device_id> <username>\n"
            "  like <device_id> <username>"
        )
        sys.exit(1)

    command = args[0]

    try:
        if command == "scan":
            if len(args) < 2:
                emit_notif_error("Usage: notifications.py scan <device_id> [scroll]")
                sys.exit(1)
            cmd_scan(args[1], int(args[2]) if len(args) > 2 else 3, package_name=package_name)

        elif command == "list_requests":
            if len(args) < 2:
                emit_notif_error("Usage: notifications.py list_requests <device_id> [limit]")
                sys.exit(1)
            cmd_list_requests(args[1], int(args[2]) if len(args) > 2 else 50, package_name=package_name)

        elif command == "accept":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py accept <device_id> <username>")
                sys.exit(1)
            cmd_accept(args[1], args[2], package_name=package_name)

        elif command == "ignore":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py ignore <device_id> <username>")
                sys.exit(1)
            cmd_ignore(args[1], args[2], package_name=package_name)

        elif command == "accept_all":
            if len(args) < 2:
                emit_notif_error("Usage: notifications.py accept_all <device_id> [max]")
                sys.exit(1)
            cmd_accept_all(args[1], int(args[2]) if len(args) > 2 else 50, package_name=package_name)

        elif command == "reply":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py reply <device_id> <username>")
                sys.exit(1)
            cmd_reply(args[1], args[2], package_name=package_name)

        elif command == "like":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py like <device_id> <username>")
                sys.exit(1)
            cmd_like(args[1], args[2], package_name=package_name)

        else:
            emit_notif_error(f"Unknown command: {command}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback

        logger.error(f"notifications bridge error: {exc}")
        emit_notif_json({"success": False, "error": str(exc), "traceback": traceback.format_exc()}, flush=True)
        sys.exit(1)


__all__ = ["run_notifications_cli"]
