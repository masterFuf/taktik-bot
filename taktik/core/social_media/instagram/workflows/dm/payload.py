"""The one reading of an Instagram DM command, for the desktop bridge and the CLI.

The payload is the file the app's main process writes (`{"command", "deviceId", "limit"}` or
`{"command", "deviceId", "username", "message"}`); the CLI handlers `instagram.engagement.dm_read`
and `dm_send` send the same keys. Each key is read by a plain `.get`, which the app's config
contract test can follow; what a command does not use is not read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from taktik.core.ai.dm_rules import ai_dm_rules_from_payload, refuse_ai_dm_texts
from taktik.core.contract.bounds import refuse_out_of_bounds
from taktik.core.contract.instagram_engagement import INSTAGRAM_DM_READ, INSTAGRAM_DM_SEND

DM_COMMANDS = ("read", "read_requests", "send")
READ_COMMANDS = ("read", "read_requests")


class DmCommandError(ValueError):
    """A DM command that cannot run: refused before the phone is touched."""


@dataclass
class DmCommand:
    """One DM command: a read (`limit`, <= 0 for all) or a reply (`username`, `message`)."""

    command: str
    limit: int = 10
    username: Optional[str] = None
    message: Optional[str] = None
    #: The message a reply written by an AI answers: its language is allowed besides the account's.
    received_message: Optional[str] = None


def dm_command_from_payload(config: Mapping[str, Any]) -> DmCommand:
    """The command a DM payload describes; refused (`DmCommandError`) when it cannot run, or when a
    setting is out of its declared bounds. A reply written by an AI (`aiDmRules` given) the rule
    refuses is refused here too (`AiDmTextRefused`, with its typed reason), before the phone."""
    command = config.get("command")
    if command in READ_COMMANDS:
        refuse_out_of_bounds(INSTAGRAM_DM_READ, config, DmCommandError)
        return DmCommand(command=command, limit=int(config.get("limit", 10)))
    if command == "send":
        refuse_out_of_bounds(INSTAGRAM_DM_SEND, config, DmCommandError)
        username = config.get("username")
        message = config.get("message")
        if not username or not message:
            raise DmCommandError("send needs a username and a message")
        received_message = config.get("receivedMessage")
        rules_block = config.get("aiDmRules")
        if rules_block is not None:
            try:
                rules = ai_dm_rules_from_payload(rules_block)
            except ValueError as unreadable:
                raise DmCommandError(str(unreadable)) from unreadable
            refuse_ai_dm_texts([message], rules, received_text=received_message)
        return DmCommand(command=command, username=username, message=message, received_message=received_message)
    raise DmCommandError(f"Unknown command: {command}")


__all__ = ["DM_COMMANDS", "DmCommand", "DmCommandError", "READ_COMMANDS", "dm_command_from_payload"]
