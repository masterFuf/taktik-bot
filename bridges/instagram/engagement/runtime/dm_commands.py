"""CLI command handling for the Instagram DM bridge."""

from __future__ import annotations

import json
import sys
import time

from bridges.instagram.runtime.ipc import logger
from bridges.instagram.engagement.dm import DMBridge
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


def cmd_read(device_id: str, limit: int, package_name: str = None):
    """Read DM conversations."""
    bridge = DMBridge(device_id, package_name=package_name)

    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        sys.exit(1)

    bridge.restart_instagram()

    if not bridge.navigate_to_dm_inbox():
        print(json.dumps({"success": False, "error": "Cannot navigate to DM inbox"}))
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

    print(json.dumps({
        "type": "result",
        "success": True,
        "conversations": conversations,
        "total": len(conversations),
    }))


def _ensure_dm_inbox(bridge: DMBridge) -> bool:
    """
    Ensure Instagram is open and we're in the DM inbox.
    Handles the case where the user left Instagram or navigated away.
    Returns True if we're in the inbox, False if navigation failed.
    """
    inbox = bridge.device(resourceId=DM_SELECTORS.inbox_thread_list_resource_id)
    if inbox.exists(timeout=2):
        logger.info("Already in DM inbox")
        bridge._ensure_primary_tab()
        return True

    ig_elements = [
        bridge.device(resourceId=resource_id)
        for resource_id in DM_SELECTORS.instagram_open_probe_resource_ids
    ]
    ig_is_open = any(e.exists(timeout=1) for e in ig_elements)

    if ig_is_open:
        logger.info("Instagram is open but not in DM inbox, navigating...")
        if bridge.navigate_to_dm_inbox():
            time.sleep(2)
            bridge._ensure_primary_tab()
            bridge._scroll_to_top_of_inbox()
            return True

    logger.info("Instagram not in DM inbox, restarting app...")
    bridge.restart_instagram()
    time.sleep(3)

    if not bridge.navigate_to_dm_inbox():
        logger.error("Failed to navigate to DM inbox after restart")
        return False

    time.sleep(2)
    bridge._ensure_primary_tab()
    bridge._scroll_to_top_of_inbox()
    return True


def cmd_send(device_id: str, username: str, message: str, package_name: str = None):
    """Send a DM message. Ensures Instagram is open and we're in DM inbox before sending."""
    bridge = DMBridge(device_id, package_name=package_name)

    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        sys.exit(1)

    if not _ensure_dm_inbox(bridge):
        print(json.dumps({"success": False, "error": "Cannot navigate to DM inbox"}))
        sys.exit(1)

    if bridge.open_conversation(username):
        pass
    else:
        logger.info(f"Utilisateur {username} non visible, scroll en haut et reessai...")
        bridge._ensure_primary_tab()
        bridge._reset_inbox_to_top(strategy="scroll")

        if not bridge.open_conversation(username):
            print(json.dumps({"success": False, "error": f"Cannot find conversation with {username}"}))
            sys.exit(1)

    if bridge.send_message(message):
        _return_to_inbox(bridge)
        print(json.dumps({
            "success": True,
            "username": username,
            "message": message,
        }))
    else:
        print(json.dumps({"success": False, "error": "Failed to send message"}))
        sys.exit(1)


def _return_to_inbox(bridge: DMBridge) -> None:
    time.sleep(0.5)
    back_btn = bridge.device(resourceId=DM_SELECTORS.conversation_back_button_resource_id)
    if back_btn.exists(timeout=2):
        back_btn.click()
        logger.info("Retour a l'inbox via header_left_button")
        time.sleep(1)
        return

    for description in DM_SELECTORS.conversation_back_descriptions:
        back_btn = bridge.device(description=description)
        if back_btn.exists(timeout=2):
            back_btn.click()
            logger.info(f"Retour a l'inbox via description {description}")
            time.sleep(1)
            return

    logger.warning("Bouton back non trouve, tentative press back")
    bridge.device.press("back")
    time.sleep(1)


def run_dm_cli(args: list[str]) -> None:
    """Parse DM bridge CLI args and dispatch the selected command."""
    package_name = None
    if "--package" in args:
        idx = args.index("--package")
        if idx + 1 < len(args):
            package_name = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if not args:
        print(json.dumps({
            "success": False,
            "error": (
                "Usage: dm_bridge.py <command> [args] [--package <pkg>]\n"
                "  read <device_id> <limit>\n"
                "  send <device_id> <username> <message>"
            ),
        }))
        sys.exit(1)

    command = args[0]

    try:
        if command == "read":
            if len(args) < 3:
                print(json.dumps({"success": False, "error": "Usage: dm_bridge.py read <device_id> <limit>"}))
                sys.exit(1)
            cmd_read(args[1], int(args[2]), package_name=package_name)

        elif command == "send":
            if len(args) < 4:
                print(json.dumps({"success": False, "error": "Usage: dm_bridge.py send <device_id> <username> <message>"}))
                sys.exit(1)
            cmd_send(args[1], args[2], args[3], package_name=package_name)

        elif command not in ["read", "send"] and len(args) >= 1:
            try:
                limit = int(args[1]) if len(args) > 1 else 10
                cmd_read(command, limit, package_name=package_name)
            except ValueError:
                print(json.dumps({"success": False, "error": f"Unknown command: {command}"}))
                sys.exit(1)

        else:
            print(json.dumps({"success": False, "error": f"Unknown command: {command}"}))
            sys.exit(1)

    except Exception as e:
        import traceback

        print(json.dumps({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }))
        sys.exit(1)
