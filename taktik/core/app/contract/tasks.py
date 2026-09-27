"""Instagram tasks of the `task_bridge` (`instagram.task.*`): one-shots against no target list.

The bridge reads the device, the task and the Instagram package at the root of its file; the
task's own settings travel under `params`, handed to the task's launcher as its payload.
"""

from __future__ import annotations

from .schema import HOST, Event, Field, ListOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import ERROR_EVENT, LOG_EVENT, STATUS_EVENT

_TASKS = "taktik.core.social_media.instagram.workflows.tasks"

STORY_RELAY_OUTCOME = Shape(
    name="InstagramStoryRelayOutcome",
    doc="What happened to one slide.",
    fields=(
        Field("index", "int", "The slide's rank in the viewer, from 1."),
        Field("status", "string", "relayed, unavailable (the story does not mention us), failed..."),
        Field("reason", "string", "Why, when the relay says.", nullable=True, optional=True),
        Field("signature", "string", "The dedup key of the slide, when its header was read.", optional=True),
    ),
)

STORY_RELAY_REPORT = Shape(
    name="InstagramStoryRelayReport",
    doc="The report of one relay pass (`relay_source_stories`).",
    fields=(
        Field("success", "bool", "The pass ran to its end."),
        Field("source_username", "string", "The account whose stories were read."),
        Field("considered", "int", "Slides looked at."),
        Field("relayed", "int", "Slides re-shared."),
        Field("already_handled", "int", "Slides a previous pass handled."),
        Field("unavailable", "int", "Slides Instagram does not offer to re-share."),
        Field("failed", "int", "Slides that failed."),
        Field("skipped_ads", "int", "Sponsored slides passed."),
        Field("reason", "string", "Why the pass stopped early.", nullable=True),
        Field("outcomes", ListOf(STORY_RELAY_OUTCOME), "Each slide handled."),
    ),
)

INSTAGRAM_STORY_RELAY = WorkflowContract(
    workflow_id="instagram.task.story_relay",
    name="InstagramStoryRelay",
    bridge="task_bridge",
    doc="Re-share a source account's stories from the account on the phone, in one pass.",
    launcher=f"{_TASKS}.agent_handler:run_instagram_story_relay",
    reader=f"{_TASKS}.agent_handler:story_relay_request_from_payload",
    nest="params",
    settings=(
        Field("source_username", "string", "The account whose stories to relay, with or without @.",
              required=True, aliases=("sourceUsername",), attr="source_username"),
        Field("max_stories", "int", "Slides of that account to consider in one pass.", default=5,
              aliases=("maxStories",), attr="max_stories"),
        Field("account_id", "int", "The acting account's row, for the journal of relayed stories.",
              aliases=("accountId",), attr="account_id", app=False),
    ),
    bridge_fields=(
        Field("deviceId", "string", "The adb serial of the phone.", required=True, by=HOST),
        Field("taskId", OneOf(("story_relay", "instagram.task.story_relay")), "The task: its short name or its id.",
              required=True),
        Field("packageName", "string", "The Instagram to restart, for a clone; the official app when absent."),
    ),
    refusals=(Refusal("source_username", doc="No source account."),),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        LOG_EVENT,
        Event("task_result", doc="The task is over.", fields=(
            Field("success", "bool", "It succeeded."),
            Field("taskId", "string", "The task's full id."),
            Field("report", STORY_RELAY_REPORT, "What the task reports."),
        )),
    ),
)

CONTRACTS = (INSTAGRAM_STORY_RELAY,)

__all__ = ["CONTRACTS", "INSTAGRAM_STORY_RELAY"]
