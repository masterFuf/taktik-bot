"""The Taktik Agent on Instagram (`instagram.engagement.taktik_agent`): the file `taktik_agent_bridge`
reads, and the lines it prints.

One launcher (`run_instagram_agent`), one reader (`taktik_agent_request_from_payload`), one bridge.
The app launches it from the scheduler's Agent node; the main process adds the OpenRouter key, the
vision model and the orchestration context it prepared from the account's recent sessions.
`tests/unit/app/contract` holds the reader, the launcher and the bridge to it.

The lines come from the launcher (`status`, `error`), from the bridge's own failures (`error`),
from the session (`AgentIpcMixin`: `agent_status`, `strategy_switch`, `agent_decision`; `follow`
and `comment` once done), from its AI calls (the AI cards) and from the gestures it shares with
the automation (`instagram_action` when a gesture is filed, `profile_captured` for the acting
account): those are the automation's declarations, not copies; `step_metric` is `shared`'s.
"""

from __future__ import annotations

from .instagram_automation import INSTAGRAM_AUTOMATION
from .schema import HOST, Computed, Event, Field, ListOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import (
    AI_PROFILE_DONE_EVENT,
    AI_PROFILE_START_EVENT,
    AI_SCREENSHOT_DONE_EVENT,
    AI_SCREENSHOT_START_EVENT,
    ERROR_EVENT,
    STATUS_EVENT,
    STEP_METRIC_EVENT,
    device_field,
)
from .stop_reasons import RUN_HALT_CODE

_AGENT = "taktik.core.social_media.instagram.workflows.agent"

NEXT_STEP = Shape(
    name="InstagramTaktikAgentNextStep",
    doc="A step the desktop planned, worded for the operator.",
    fields=(
        Field("tool", "string", "The step it words (`browse_feed`...)."),
        Field("message", "string", "What the Agent announces for it, instead of its own line."),
    ),
)

ORCHESTRATION = Shape(
    name="InstagramTaktikAgentOrchestration",
    doc="What the desktop prepared for the session from the account's recent sessions.",
    fields=(
        Field("timeline", ListOf("json"), "The recent episodes, kept in the session's context.", default=(),
              attr="orchestration.timeline"),
        Field("patternWarnings", ListOf("string"), "What the recent episodes repeat too much.", default=(),
              attr="orchestration.pattern_warnings"),
        Field("introMessage", "string", "The line the session opens with, when there is one.",
              attr="orchestration.intro_message"),
        Field("nextSteps", ListOf(NEXT_STEP), "The planned steps, worded.", default=(),
              attr="orchestration.next_steps"),
        Field("source", "string", "Who prepared it, echoed in the status lines.", default="desktop",
              attr="orchestration.source"),
    ),
)

#: `stats` of `agent_status`: the session's counters, or what the line is about.
STATUS_STATS = Shape(
    name="InstagramTaktikAgentStatusStats",
    doc="The session's counters, or, on an announcement, what it is about.",
    fields=(
        Field("likes", "int", "Likes given.", optional=True),
        Field("comments", "int", "Comments written.", optional=True),
        Field("follows", "int", "Follows given.", optional=True),
        Field("profile_visits", "int", "Profiles opened.", optional=True),
        Field("posts_seen", "int", "Posts scrolled past.", optional=True),
        Field("posts_stopped", "int", "Posts the model judged.", optional=True),
        Field("session_cost_usd", "number", "What the model calls cost.", optional=True),
        Field("profiles_skipped_relationship", "int", "Profiles left: a relationship already existed.",
              optional=True),
        Field("stop_reason", RUN_HALT_CODE, "Why the session stopped early (a block...), on `completed`.", optional=True),
        Field("username", "string", "The acting account (`account_detected`).", optional=True),
        Field("niche", "string", "Its niche, as on record (`account_detected`).", optional=True),
        Field("tool", "string", "The step announced (`planning`).", optional=True),
        Field("source", "string", "Who prepared the context (`orchestration_context`, `planning`).", optional=True),
        Field("timeline_count", "int", "Recent episodes in the context (`orchestration_context`).", optional=True),
        Field("pattern_warnings", ListOf("string"), "Its warnings (`orchestration_context`).", optional=True),
    ),
)

_STRATEGY = OneOf(("feed", "hashtag"))

EVENTS = (
    STATUS_EVENT,
    ERROR_EVENT,
    Event("agent_status", doc="Where the session is: its steps, its end, why it failed.", fields=(
        Field("status", "string", "account_detected, orchestration_context, planning, navigating, running, "
              "completed, error."),
        Field("message", "string", "The same, for a person: English, or already worded by the desktop."),
        Field("workflow_type", "string", "`taktik_agent`."),
        Field("stats", STATUS_STATS, "The counters, or what the line is about.", optional=True),
        Field("message_key", "string", "A key the app words a fixed line with.", optional=True),
    )),
    Event("strategy_switch", doc="The session leaves the feed for a hashtag, or comes back.", fields=(
        Field("from_strategy", _STRATEGY, "Where it was."),
        Field("to_strategy", _STRATEGY, "Where it goes."),
        Field("workflow_type", "string", "`taktik_agent`."),
        Field("hashtag", "string", "The hashtag explored.", optional=True),
    )),
    INSTAGRAM_AUTOMATION.event("agent_decision"),
    Event("follow", doc="A follow the model asked for, given.", fields=(
        Field("username", "string", "Who."),
        Field("success", "bool", "It took."),
    )),
    Event("comment", doc="A comment the model wrote, posted.", fields=(
        Field("username", "string", "The post's author."),
        Field("comment", "string", "The comment."),
        Field("success", "bool", "It was posted."),
    )),
    INSTAGRAM_AUTOMATION.event("instagram_action"),
    INSTAGRAM_AUTOMATION.event("profile_captured"),
    STEP_METRIC_EVENT,
    AI_SCREENSHOT_START_EVENT,
    AI_SCREENSHOT_DONE_EVENT,
    AI_PROFILE_START_EVENT,
    AI_PROFILE_DONE_EVENT,
)

INSTAGRAM_TAKTIK_AGENT = WorkflowContract(
    workflow_id="instagram.engagement.taktik_agent",
    name="InstagramTaktikAgent",
    bridge="taktik_agent_bridge",
    doc="An autonomous feed session: the model decides each like, comment, profile visit and follow.",
    launcher=f"{_AGENT}.agent_handler:run_instagram_agent",
    reader=f"{_AGENT}.payload:taktik_agent_request_from_payload",
    settings=(
        Field("max_likes", "int", "Likes the session may give.", default=80, attr="max_likes"),
        Field("max_comments", "int", "Comments the session may write.", default=15, attr="max_comments"),
        Field("max_follows", "int", "Follows the session may give.", default=20, attr="max_follows"),
        Field("max_profile_visits", "int", "Profiles the session may open.", default=40, attr="max_profile_visits"),
        Field("max_posts_seen", "int", "Posts after which the session ends.", default=150, attr="max_posts_seen"),
        Field("session_duration_min", "number", "Minutes after which the session ends.", default=25,
              attr="session_duration_min"),
        Field("skip_reels", "bool", "Scroll past reels, in the feed and in a hashtag.", default=True,
              attr="skip_reels"),
        Field("skip_related_profiles", "bool", "Leave a profile already in a relationship before its "
              "screenshot.", default=True, attr="skip_related_profiles", app=False),
        Field("language", "string", "The language the model words its reasons in (the app's).", default="en",
              attr="language"),
        Field("text_model", "string", "The model of the text calls (the hashtags explored).", attr="text_model",
              app=False),
        Field("agent_plan", "json", "An Agent plan, kept in the session's context (not executed).",
              aliases=("agentPlan",), attr="agent_plan", app=False),
        Field("vision_model", "string", "The model that reads the screenshots; injected by the host.",
              attr="vision_model", by=HOST),
        Field("openrouter_api_key", "string", "The key the model is called with; injected by the host.",
              default=Computed("the OPENROUTER_API_KEY environment variable"), attr="openrouter_api_key",
              by=HOST),
        Field("desktop_orchestration_context", ORCHESTRATION, "What the desktop prepared; injected by the host.",
              by=HOST),
    ),
    bridge_fields=(
        device_field("deviceId"),
        Field("packageName", "string", "An Instagram clone's package, opened instead of Instagram.", by=HOST),
    ),
    refusals=(
        Refusal("openrouter_api_key", doc="No key, in the file or in the environment: the model cannot decide."),
    ),
    events=EVENTS,
)

CONTRACTS = (INSTAGRAM_TAKTIK_AGENT,)

__all__ = ["CONTRACTS", "EVENTS", "INSTAGRAM_TAKTIK_AGENT"]
