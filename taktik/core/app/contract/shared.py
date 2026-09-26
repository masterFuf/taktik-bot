"""Pieces of the contract every bridge shares: the IP rotation option, the status and error lines."""

from __future__ import annotations

from .schema import HOST, Event, Field, OneOf, Shape

#: `enforce_pre_session_ip_rotation` (`bridges/common/device/network.py`), before the session.
NETWORK_RESET = Shape(
    name="BridgeNetworkReset",
    doc="Rotate the phone's IP before the run; a requested rotation that did not happen stops it.",
    fields=(
        Field("enabled", "bool", "Rotate before the run.", default=False),
        Field(
            "method",
            OneOf(("data", "airplane", "airplane_cell")),
            "How: mobile data off and on, airplane mode, or airplane mode for the cell radio only.",
            default="data",
        ),
    ),
)


def network_reset_field() -> Field:
    return Field("networkReset", NETWORK_RESET, "Pre-session IP rotation, read by the bridge.")


def device_field(key: str, *aliases: str) -> Field:
    return Field(key, "string", "The adb serial of the phone.", required=True, aliases=aliases, by=HOST)


#: `IPC.status`, or `send_message("status", ...)` when a run says why it ended.
STATUS_EVENT = Event(
    "status",
    doc="Where the run is.",
    fields=(
        Field("status", "string", "starting, running, completed..."),
        Field("message", "string", "The same, for a person."),
        Field(
            "completion_reason",
            "string",
            "Why a run ended on its own (`action_blocked`, `max_duration_reached`...).",
            optional=True,
        ),
    ),
)

#: `IPC.error` / `send_error`.
ERROR_EVENT = Event(
    "error",
    doc="The run failed or was refused.",
    fields=(
        Field("error", "string", "What went wrong, for a person."),
        Field("error_code", "string", "A code the app translates.", optional=True),
        Field("traceback", "string", "Diagnostic context for a crash report.", optional=True),
    ),
)


#: `IPC.ai_spend` (`bridges/common/runtime/ipc_ai.py`), one line per paid model call.
AI_SPEND_EVENT = Event(
    "ai_spend",
    doc="The cost of one paid model call, the session's only cost source.",
    fields=(
        Field("cost_usd", "number", "What the call cost."),
        Field("kind", "string", "What it was paid for: one of `AI_SPEND_KINDS` (`taktik/core/app/ai/spend.py`)."),
        Field("workflow_type", "string", "The family of the run."),
        Field("model", "string", "The model that served the call.", optional=True),
        Field("label", "string", "Free text for a person (a username).", optional=True),
    ),
)


__all__ = [
    "AI_SPEND_EVENT",
    "ERROR_EVENT",
    "NETWORK_RESET",
    "STATUS_EVENT",
    "device_field",
    "network_reset_field",
]
