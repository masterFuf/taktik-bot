"""Pieces of the contract every bridge shares: the IP rotation, the status, error, log, session and
AI lines, the step telemetry."""

from __future__ import annotations

from .schema import HOST, Event, Field, OneOf, Shape
from .stop_reasons import TIKTOK_COMPLETION_REASON

#: `enforce_pre_session_ip_rotation` (`bridges/common/network.py`), before the session.
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
    return Field("networkReset", NETWORK_RESET, "Pre-session IP rotation: a setting of the desktop app, done by "
                 "the bridge; a CLI run never rotates the IP.")


def device_field(key: str, *aliases: str) -> Field:
    return Field(key, "string", "The adb serial of the phone.", required=True, aliases=aliases, by=HOST)


def instagram_package_field(doc: str = "An Instagram clone's package, run instead of Instagram; absent: the "
                                       "installed Instagram.") -> Field:
    """The clone an Instagram run starts: read by its launcher, which hands it to the host's connection."""
    return Field("packageName", "string", doc, aliases=("package_name",),
                 reader="taktik.core.social_media.instagram.workflows.common.startup:package_name_from_payload")


#: `IPC.status`, or `send_message("status", ...)` when a run says why it ended.
STATUS_EVENT = Event(
    "status",
    doc="Where the run is.",
    fields=(
        Field("status", "string", "starting, running, completed..."),
        Field("message", "string", "The same, for a person."),
        Field(
            "completion_reason",
            TIKTOK_COMPLETION_REASON,
            "Why a run ended on its own (`action_blocked`, `feed_stuck`...); only TikTok bridges send it.",
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


#: `IPC.log` / `send_log`, a line for the run's log view.
LOG_EVENT = Event(
    "log",
    doc="A line for the run's log view.",
    fields=(
        Field("level", "string", "debug, info, warning, error..."),
        Field("message", "string", "The line."),
    ),
)


#: `IPC.session_start` (`bridges/common/ipc.py`), or the same line printed by the Instagram
#: automation (`workflow_helpers.py`): the run's `sessions` row. One field on every bridge.
SESSION_START_EVENT = Event("session_start", doc="The run's `sessions` row, as soon as it is opened.", fields=(
    Field("session_id", "int", "The row's id: the app writes the run's AI spend into it."),
))


#: `emit_step` (`taktik/core/shared/telemetry`), through the sink each bridge configures.
STEP_METRIC_EVENT = Event(
    "step_metric",
    doc="One atomic gesture or decision (`emit_step`), for the step telemetry.",
    fields=(
        Field("category", "string", "`tap`, `scroll`, `keystroke`, `follower_decision`..."),
        Field("action", "string", "A finer label.", nullable=True),
        Field("target", "string", "What it acted on.", nullable=True),
        Field("detail", "json", "Its structured payload."),
        Field("ts", "number", "When, epoch seconds."),
    ),
)


#: `IPC.ai_spend` (`bridges/common/ipc_ai.py`), one line per paid model call.
AI_SPEND_EVENT = Event(
    "ai_spend",
    doc="The cost of one paid model call, the session's only cost source.",
    fields=(
        Field("cost_usd", "number", "What the call cost."),
        Field("kind", "string", "What it was paid for: one of `AI_SPEND_KINDS` (`taktik/core/ai/spend.py`)."),
        Field("workflow_type", "string", "The family of the run."),
        Field("model", "string", "The model that served the call.", optional=True),
        Field("label", "string", "Free text for a person (a username).", optional=True),
    ),
)


#: `perform_network_reset` (`bridges/common/network.py`), when a rotation was asked for.
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

# The AI cards (`AIIpcMixin`, `bridges/common/ipc_ai.py`), whatever bridge runs the AI service.

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
    Field("duration_ms", "int", "How long the model took; absent from a copy for the base.", optional=True),
    Field("model", "string", "The model that answered; absent from a copy for the base.", nullable=True,
          optional=True),
    Field("provider", "string", "Who served it; absent from a copy for the base.", nullable=True, optional=True),
    Field("workflow_type", "string", "The family of the run."),
    Field("platform", "string", "The profile's platform, on a TikTok copy for the base (`tiktok`).",
          optional=True),
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
    "SESSION_START_EVENT",
    "STATUS_EVENT",
    "STEP_METRIC_EVENT",
    "device_field",
    "network_reset_field",
]
