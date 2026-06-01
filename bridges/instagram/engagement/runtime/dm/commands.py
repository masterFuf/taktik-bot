"""CLI command handling for the Instagram DM bridge."""

from __future__ import annotations

import sys
import time

from bridges.instagram.engagement.runtime.dm.bridge import DMBridge
from bridges.instagram.engagement.runtime.dm.events import emit_dm_error, emit_dm_json
from bridges.instagram.engagement.runtime.dm.session import ensure_dm_inbox, return_to_inbox
from bridges.instagram.runtime.ipc import logger


def cmd_read(device_id: str, limit: int, package_name: str = None):
    """Read DM conversations."""
    bridge = DMBridge(device_id, package_name=package_name)

    if not bridge.connect():
        emit_dm_error("Failed to connect to device")
        sys.exit(1)

    bridge.restart_instagram()

    if not bridge.navigate_to_dm_inbox():
        emit_dm_error("Cannot navigate to DM inbox")
        sys.exit(1)

    time.sleep(2)
    conversations = bridge.read_conversations(limit)

    # Leave the inbox in a deterministic state for the next command. Without
    # this, the following send process can start from the bottom of a long DM
    # list and fail to find conversations that were read near the top.
    try:
        bridge._reset_inbox_to_top(strategy="auto")
    except Exception as exc:
        logger.warning(f"Could not reset DM inbox to top after read: {exc}")

    emit_dm_json(
        {
            "type": "result",
            "success": True,
            "conversations": conversations,
            "total": len(conversations),
        }
    )


def cmd_send(device_id: str, username: str, message: str, package_name: str = None):
    """Send a DM message. Ensures Instagram is open and we're in DM inbox before sending."""
    bridge = DMBridge(device_id, package_name=package_name)

    if not bridge.connect():
        emit_dm_error("Failed to connect to device")
        sys.exit(1)

    if not ensure_dm_inbox(bridge):
        emit_dm_error("Cannot navigate to DM inbox")
        sys.exit(1)

    if bridge.open_conversation(username):
        pass
    else:
        logger.info(f"Utilisateur {username} non visible, scroll en haut et reessai...")
        bridge._ensure_primary_tab()
        bridge._reset_inbox_to_top(strategy="scroll")

        if not bridge.open_conversation(username):
            emit_dm_error(f"Cannot find conversation with {username}")
            sys.exit(1)

    if bridge.send_message(message):
        return_to_inbox(bridge)
        emit_dm_json(
            {
                "success": True,
                "username": username,
                "message": message,
            }
        )
    else:
        emit_dm_error("Failed to send message")
        sys.exit(1)


def run_dm_cli(args: list[str]) -> None:
    """Parse DM bridge CLI args and dispatch the selected command."""
    package_name = None
    if "--package" in args:
        idx = args.index("--package")
        if idx + 1 < len(args):
            package_name = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if not args:
        emit_dm_error(
            "Usage: dm_bridge.py <command> [args] [--package <pkg>]\n"
            "  read <device_id> <limit>\n"
            "  send <device_id> <username> <message>"
        )
        sys.exit(1)

    command = args[0]

    try:
        if command == "read":
            if len(args) < 3:
                emit_dm_error("Usage: dm_bridge.py read <device_id> <limit>")
                sys.exit(1)
            cmd_read(args[1], int(args[2]), package_name=package_name)

        elif command == "send":
            if len(args) < 4:
                emit_dm_error("Usage: dm_bridge.py send <device_id> <username> <message>")
                sys.exit(1)
            cmd_send(args[1], args[2], args[3], package_name=package_name)

        elif command not in ["read", "send"] and len(args) >= 1:
            try:
                limit = int(args[1]) if len(args) > 1 else 10
                cmd_read(command, limit, package_name=package_name)
            except ValueError:
                emit_dm_error(f"Unknown command: {command}")
                sys.exit(1)

        else:
            emit_dm_error(f"Unknown command: {command}")
            sys.exit(1)

    except Exception as e:
        import traceback

        emit_dm_json(
            {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )
        sys.exit(1)
