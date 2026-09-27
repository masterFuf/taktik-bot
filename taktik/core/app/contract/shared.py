"""Pieces of the contract every bridge shares: the IP rotation, the status, error, log and AI lines."""

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


#: `IPC.log`, a line for the desktop's debug console.
LOG_EVENT = Event(
    "log",
    doc="A line for the debug console.",
    fields=(
        Field("level", "string", "debug, info, warning, error."),
        Field("message", "string", "The line."),
    ),
)

#: `perform_network_reset` (`bridges/common/device/network.py`), when a rotation was asked for.
NETWORK_RESET_COMPLETE_EVENT = Event(
    "network_reset_complete",
    doc="The pre-session IP rotation, verified.",
    fields=(
        Field("old_ip", "string", "The IP before, or `unknown`."),
        Field("new_ip", "string", "The IP after, or `unknown`."),
        Field("method", OneOf(("data", "airplane", "airplane_cell")), "How it rotated."),
        Field("success", "bool", "The IP did not stay the same and the commands took effect."),
        Field("ip_changed", "bool", "Both IPs were read and differ."),
        Field("verdict", OneOf(("verified", "unchanged", "unverifiable")), "What the rotation proved."),
        Field("attempts", "int", "Rotations tried."),
        Field("reason", "string", "The same, for a person."),
    ),
)

# The AI cards (`AIIpcMixin`, `bridges/common/runtime/ipc_ai.py`), whatever bridge runs the AI service.

AI_PROFILE_START_EVENT = Event("ai_profile_start", doc="The AI starts qualifying a profile.", fields=(
    Field("username", "string", "The profile."),
    Field("target_username", "string", "The same."),
    Field("prompt", "string", "What is asked, in English.", nullable=True),
    Field("model", "string", "The model asked.", nullable=True),
    Field("workflow_type", "string", "The family of the run."),
    Field("image", "string", "The picture sent to the model.", optional=True),
    Field("avatar_url", "string", "The profile's picture.", optional=True),
    Field("prompt_key", "string", "A key the app translates the prompt with.", optional=True),
))

AI_PROFILE_DONE_EVENT = Event("ai_profile_done", doc="The AI qualified a profile.", fields=(
    Field("username", "string", "The profile."),
    Field("target_username", "string", "The same."),
    Field("result", "string", "The verdict, for a person."),
    Field("duration_ms", "int", "How long the model took."),
    Field("model", "string", "The model that answered.", nullable=True),
    Field("provider", "string", "Who served it.", nullable=True),
    Field("workflow_type", "string", "The family of the run."),
    Field("event_id", "string", "Pairs it with its start.", optional=True),
    Field("cost_usd", "number", "What the call cost.", optional=True),
    Field("classification", "json", "The qualification, as the model gave it.", optional=True),
    Field("screenshot", "string", "The picture the model read.", optional=True),
    Field("persist_only", "bool", "A copy for the base only: not counted again.", optional=True),
))

AI_SCREENSHOT_START_EVENT = Event("ai_screenshot_start", doc="The AI starts reading a post.", fields=(
    Field("target_username", "string", "The post's author, if known.", nullable=True),
    Field("prompt", "string", "What is asked, in English.", nullable=True),
    Field("model", "string", "The model asked.", nullable=True),
    Field("workflow_type", "string", "The family of the run."),
    Field("image", "string", "The picture sent to the model.", optional=True),
    Field("prompt_key", "string", "A key the app translates the prompt with.", optional=True),
))

AI_SCREENSHOT_DONE_EVENT = Event("ai_screenshot_done", doc="The AI described a post.", fields=(
    Field("target_username", "string", "The post's author, if known.", nullable=True),
    Field("result", "string", "The description."),
    Field("duration_ms", "int", "How long the model took."),
    Field("model", "string", "The model that answered.", nullable=True),
    Field("provider", "string", "Who served it.", nullable=True),
    Field("workflow_type", "string", "The family of the run."),
    Field("cost_usd", "number", "What the call cost.", optional=True),
    Field("screenshot", "string", "The picture the model read.", optional=True),
))

AI_COMMENT_START_EVENT = Event("ai_comment_start", doc="The AI starts writing a comment.", fields=(
    Field("target_username", "string", "The post's author."),
    Field("prompt", "string", "What is asked, in English.", nullable=True),
    Field("model", "string", "The model asked.", nullable=True),
    Field("workflow_type", "string", "The family of the run."),
    Field("prompt_key", "string", "A key the app translates the prompt with.", optional=True),
))

AI_COMMENT_DONE_EVENT = Event("ai_comment_done", doc="The AI wrote a comment.", fields=(
    Field("target_username", "string", "The post's author."),
    Field("comment", "string", "The comment."),
    Field("result", "string", "The same."),
    Field("duration_ms", "int", "How long the model took."),
    Field("model", "string", "The model that answered.", nullable=True),
    Field("provider", "string", "Who served it.", nullable=True),
    Field("workflow_type", "string", "The family of the run."),
    Field("cost_usd", "number", "What the call cost.", optional=True),
    Field("reasoning", "string", "Why this comment.", optional=True),
    Field("post_description", "string", "What the AI saw in the post.", optional=True),
    Field("post_caption", "string", "The author's caption.", optional=True),
    Field("screenshot", "string", "The post sent to the model.", optional=True),
))

AI_ERROR_EVENT = Event("ai_error", doc="An AI call failed.", fields=(
    Field("error", "string", "What went wrong."),
    Field("target_username", "string", "The profile, if one.", nullable=True),
    Field("workflow_type", "string", "The family of the run."),
))

#: Every line of the AI service, in the order a card goes through them.
AI_EVENTS = (
    AI_PROFILE_START_EVENT,
    AI_PROFILE_DONE_EVENT,
    AI_SCREENSHOT_START_EVENT,
    AI_SCREENSHOT_DONE_EVENT,
    AI_COMMENT_START_EVENT,
    AI_COMMENT_DONE_EVENT,
    AI_ERROR_EVENT,
    AI_SPEND_EVENT,
)


__all__ = [
    "AI_COMMENT_DONE_EVENT",
    "AI_COMMENT_START_EVENT",
    "AI_ERROR_EVENT",
    "AI_EVENTS",
    "AI_PROFILE_DONE_EVENT",
    "AI_PROFILE_START_EVENT",
    "AI_SCREENSHOT_DONE_EVENT",
    "AI_SCREENSHOT_START_EVENT",
    "AI_SPEND_EVENT",
    "ERROR_EVENT",
    "LOG_EVENT",
    "NETWORK_RESET",
    "NETWORK_RESET_COMPLETE_EVENT",
    "STATUS_EVENT",
    "device_field",
    "network_reset_field",
]
