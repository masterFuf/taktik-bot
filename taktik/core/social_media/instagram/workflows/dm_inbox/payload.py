"""The one reading of an Instagram DM command, for the desktop bridge and the CLI.

The payload is the file the app's main process writes (`{"command", "deviceId", "limit"}` or
`{"command", "deviceId", "username", "message"}`); the CLI handlers `instagram.engagement.dm_read`
and `dm_send` send the same keys. Each key is read by a plain `.get`, which the app's config
contract test can follow; what a command does not use is not read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

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


def dm_command_from_payload(config: Mapping[str, Any]) -> DmCommand:
    """The command a DM payload describes; refused (`DmCommandError`) when it cannot run."""
    command = config.get("command")
    if command in READ_COMMANDS:
        return DmCommand(command=command, limit=int(config.get("limit", 10)))
    if command == "send":
        username = config.get("username")
        message = config.get("message")
        if not username or not message:
            raise DmCommandError("send needs a username and a message")
        return DmCommand(command=command, username=username, message=message)
    raise DmCommandError(f"Unknown command: {command}")


__all__ = ["DM_COMMANDS", "DmCommand", "DmCommandError", "READ_COMMANDS", "dm_command_from_payload"]
