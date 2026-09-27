"""Instagram engagement, the notifications pass (`notifications_bridge`).

One id, `instagram.engagement.notifications`, one launcher and one reader for the nine commands of
the activity feed: the scan, the listing and the acceptance of follow requests, the verbs of one
row, the batch. `command` picks what runs; each other setting is read for its command only
(`when`). The CLI and the desktop bridge share the launcher; the bridge adds the device.

Kept apart from `instagram_engagement.py` (cold DM, DM inbox) for its size: the lines of this bridge
carry the scan's rows, the suggestions visit and the batch report.
"""

from __future__ import annotations

from .schema import HOST, Event, Field, ListOf, MapOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import STEP_METRIC_EVENT, device_field
from .stop_reasons import RUN_HALT_CODE

_NOTIFICATIONS = "taktik.core.social_media.instagram.workflows.management.notifications"

#: `payload.py`: the commands, and the ones that act on the row of one account.
ROW_COMMANDS = ("accept", "ignore", "like", "follow_back")
COMMANDS = ("scan", "list_requests", "accept_all", "reply", "batch", *ROW_COMMANDS)
_NEEDS_USERNAME = (*ROW_COMMANDS, "reply")

#: The families a row of the activity feed is classified in (`classifier_fragments`), and `other`.
NOTIFICATION_TYPES = OneOf((
    "comment_mention", "comment_reply", "comment_like", "post_comment", "post_like", "new_follower",
    "follow_request", "message", "shared", "other",
))

#: The verbs a batch runs (`cmd_batch`).
BATCH_VERBS = (*ROW_COMMANDS, "reply", "welcome_dm", "follow_actor")

_SCAN = {"command": "scan"}
_BATCH = {"command": "batch"}

BATCH_ACTION = Shape(
    name="InstagramNotificationBatchAction",
    doc="One step of a batch: what to do, to whom, and for a reply or a welcome DM, the text.",
    fields=(
        Field("action", OneOf(BATCH_VERBS), "The verb; `welcome_dm` and `follow_actor` leave the feed for a "
              "profile, so the bot runs them last.", required=True),
        Field("username", "string", "The account of the row.", required=True),
        Field("text", "string", "The reply, or the welcome message; ignored by the other verbs."),
        Field("notif_type", NOTIFICATION_TYPES, "The row's family. With `notif_text`, the row's identity: an "
              "action already recorded as done for it is skipped."),
        Field("notif_text", "string", "The row's text, for its identity."),
        Field("notif_time", "string", "The row's time, for its identity."),
    ),
)

# ------------------------------------------------------------------------------------ lines

NOTIFICATION_ITEM = Shape(
    name="InstagramNotificationItem",
    doc="A row of the activity feed, classified (`parse_feed_rows`).",
    fields=(
        Field("type", NOTIFICATION_TYPES, "Its family."),
        Field("username", "string", "The account the row is about; empty when unreadable."),
        Field("time", "string", "The time it shows (`2h`), or empty."),
        Field("text", "string", "Its text, 200 characters at most."),
        Field("label", "string", "Its text without the trailing buttons and time."),
        Field("has_action", "bool", "The row carries a button (confirm, follow back...)."),
        Field("is_new", "bool", "First time this row is seen for the account; absent when nothing was recorded.",
              optional=True),
    ),
)

FOLLOW_REQUEST = Shape(
    name="InstagramNotificationFollowRequest",
    doc="A pending follow request.",
    fields=(Field("username", "string", "The account asking."),),
)

SUGGESTION_PROFILE = Shape(
    name="InstagramNotificationSuggestionProfile",
    doc="One suggested account of the visit (`visit_suggestions`).",
    fields=(
        Field("label", "string", "The name the suggestion showed."),
        Field("username", "string", "The handle read on its profile.", nullable=True),
        Field("status", "string", "What happened: `already_known`, `not_opened`, `no_username`, or the "
              "pipeline's outcome."),
        Field("follows", "int", "Follows made.", optional=True),
        Field("reasons", ListOf("string"), "Why the filters left it out.", optional=True),
    ),
)

SUGGESTIONS = Shape(
    name="InstagramNotificationSuggestions",
    doc="The qualified visit of the suggested accounts at the end of a scan (`followSuggestions`).",
    fields=(
        Field("visited", "int", "Profiles that opened."),
        Field("processed", "int", "Profiles that went through the per-profile pipeline."),
        Field("follows", "int", "Follows made."),
        Field("filtered", "int", "Profiles the filters left out."),
        Field("errors", "int", "Profiles that failed."),
        Field("profiles", ListOf(SUGGESTION_PROFILE), "Each suggestion tried."),
        Field("stop_reason", "string", "Why the visit ended: `disabled`, `no_account`, `max_reached`, "
              "`list_exhausted`..."),
        Field("ai_qualification", "bool", "The AI qualified the visited profiles."),
        Field("session_id", "int", "The visit's `sessions` row.", optional=True, nullable=True),
        Field("fallback", "json", "The same visit on the people screen, when the feed offered none.",
              optional=True),
    ),
)

BATCH_ENTRY = Shape(
    name="InstagramNotificationBatchEntry",
    doc="What one step of a batch did.",
    fields=(
        Field("action", "string", "The verb."),
        Field("username", "string", "The account of the row."),
        Field("success", "bool", "Done, or skipped by a guard."),
        Field("skipped", "bool", "Nothing done: a guard, or nothing to do on screen.", optional=True),
        Field("reason", "string", "Why it was skipped: `already_done`, `daily_cap`, `already_dmed`...",
              optional=True),
        Field("message", "string", "The same, for a person.", optional=True),
        Field("error", "string", "What went wrong.", optional=True),
        Field("stop_reason", RUN_HALT_CODE, "`action_blocked`: Instagram refuses actions.", optional=True),
        Field("state", "string", "The relationship read before a follow (`follow_actor`).", optional=True),
    ),
)

NOTIFICATION_STEP_EVENT = Event("notification_step", doc="Live narration of the command, step by step.", fields=(
    Field("step", "string", "The step: `own_profile`, `open_notifications`, `scan`, `section`, `result`, "
          "`suggestions`, `suggestion_visit`, `session_end`, a row verb, `accept_all`, `batch_action`, "
          "`batch_result`..."),
    Field("step_status", OneOf(("running", "done", "failed")), "Where the step is; absent on a batch step.",
          optional=True),
    Field("message", "string", "The step, for a person."),
    Field("username", "string", "The account of the row, or of the suggestion visited.", optional=True),
    Field("section", "string", "The time bucket the scroll uncovered (`section`).", optional=True),
    Field("new_count", "int", "Rows not seen before (`result`).", optional=True),
    Field("accepted_count", "int", "Requests accepted so far (`accept_all`).", optional=True),
    Field("label", "string", "The name the suggestion showed (`suggestion_visit`).", optional=True),
    Field("outcome", "string", "What the pipeline did with it (`suggestion_visit`).", optional=True),
    Field("index", "int", "The batch step's rank, from 0.", optional=True),
    Field("total", "int", "Steps in the batch.", optional=True),
    Field("action", "string", "The batch step's verb.", optional=True),
    Field("success", "bool", "The batch step went through (`batch_result`).", optional=True),
))

RESULT_EVENT = Event("result", doc="The command's result, or why it could not run: the last line.", fields=(
    Field("command", OneOf(COMMANDS), "The command that ran; absent when it could not be read.", optional=True),
    Field("success", "bool", "The command did what it was asked."),
    Field("count", "int", "Rows read (`scan`), requests listed or accepted.", optional=True),
    Field("by_type", MapOf("int"), "Rows per family (`scan`).", optional=True),
    Field("items", ListOf(NOTIFICATION_ITEM), "The rows read (`scan`).", optional=True),
    Field("requests", ListOf(FOLLOW_REQUEST), "The pending follow requests (`scan`, `list_requests`).",
          optional=True),
    Field("has_grouped_requests", "bool", "The feed shows the follow requests entry (`scan`).", optional=True),
    Field("suggestions", SUGGESTIONS, "The visit of the suggested accounts (`scan`).", optional=True),
    Field("accepted", ListOf("string"), "Requests accepted (`accept_all`).", optional=True),
    Field("username", "string", "The account of the row (a row verb, `reply`).", optional=True),
    Field("action", "string", "The verb (`accept`, `ignore`, `reply`).", optional=True),
    Field("total", "int", "Steps in the batch.", optional=True),
    Field("done", "int", "Steps done.", optional=True),
    Field("failed", "int", "Steps that failed.", optional=True),
    Field("skipped", "int", "Steps skipped by a guard.", optional=True),
    Field("results", ListOf(BATCH_ENTRY), "Each step of the batch.", optional=True),
    Field("message", "string", "The result, for a person.", optional=True),
    Field("stop_reason", RUN_HALT_CODE, "`action_blocked`: Instagram refuses actions.", optional=True),
    Field("error", "string", "What went wrong, for a person.", optional=True),
    Field("traceback", "string", "Diagnostic context of a crash.", optional=True),
))

INSTAGRAM_NOTIFICATIONS = WorkflowContract(
    workflow_id="instagram.engagement.notifications",
    name="InstagramNotifications",
    bridge="notifications_bridge",
    doc="Read the activity feed and act on it, one command per run.",
    launcher=f"{_NOTIFICATIONS}.agent_handler:run_instagram_notifications",
    reader=f"{_NOTIFICATIONS}.payload:notifications_request_from_payload",
    selector="command",
    settings=(
        Field("command", OneOf(COMMANDS), "What runs: the scan, the follow requests, a row verb, a batch.",
              required=True, attr="command"),
        Field("accountUsername", "string", "The account on the phone: the scan is recorded and deduplicated "
              "under it, an action is recorded under it; nothing is recorded without it; filled by the host.",
              attr="account_username", by=HOST),
        Field("username", "string", "The account of the row.", attr="username",
              when={"command": _NEEDS_USERNAME}),
        Field("scroll", "int", "Screens scrolled below the first one.", default=3, attr="scroll", when=_SCAN),
        Field("followSuggestions", "int", "Suggested accounts visited and qualified at the end of the scan; 0: "
              "none.", default=0, attr="follow_suggestions", when=_SCAN),
        Field("ai", "json", "The AI block that qualifies the visited suggestions (the automation's).",
              attr="ai", when=_SCAN, app=False),
        Field("language", "string", "The wording of the AI qualification.", default="en", attr="language",
              when=_SCAN, app=False),
        Field("limit", "int", "Follow requests listed; 0 or less: 50.", default=50, attr="limit",
              when={"command": "list_requests"}),
        Field("max", "int", "Follow requests accepted; 0 or less: 50.", default=50, attr="accept_max",
              when={"command": "accept_all"}),
        Field("text", "string", "The reply; empty: the reply field is opened, nothing is sent.", default="",
              attr="text", when={"command": "reply"}),
        Field("actions", ListOf(BATCH_ACTION), "The steps of the batch, run in one session.", attr="actions",
              when=_BATCH),
        Field("source", "string", "Who asked, recorded with each action: `batch` (the operator) or "
              "`autopilot` (a policy).", default="batch", attr="source", when=_BATCH),
        Field("followBackDailyCap", "int", "Follow backs a day, counted on the bot's record; absent: uncapped.",
              attr="follow_back_daily_cap", when=_BATCH),
        Field("welcomeDmDailyCap", "int", "Welcome DMs a day; absent: uncapped.", attr="welcome_dm_daily_cap",
              when=_BATCH),
        Field("followActorDailyCap", "int", "Follows of the accounts that engaged with our comments, a day; "
              "absent: uncapped.", attr="follow_actor_daily_cap", when=_BATCH),
    ),
    bridge_fields=(
        device_field("deviceId"),
        Field("packageName", "string", "An Instagram clone's package, opened instead of Instagram.", by=HOST),
    ),
    refusals=(
        Refusal("command", doc="No command, or one the bot does not know."),
        *(Refusal("username", when={"command": command}, doc=f"`{command}` without its row.")
          for command in _NEEDS_USERNAME),
        Refusal("actions", when=_BATCH, doc="A batch without a step."),
    ),
    # `step_metric`: the step telemetry the bridge's IPC module registers (a refused write, a
    # keystroke); the app does not read it from this bridge.
    events=(NOTIFICATION_STEP_EVENT, RESULT_EVENT, STEP_METRIC_EVENT),
)

CONTRACTS = (INSTAGRAM_NOTIFICATIONS,)

__all__ = [
    "BATCH_VERBS",
    "COMMANDS",
    "CONTRACTS",
    "INSTAGRAM_NOTIFICATIONS",
    "NOTIFICATION_TYPES",
    "ROW_COMMANDS",
]
