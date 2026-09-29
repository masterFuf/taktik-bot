"""TikTok workflows of the `tiktok_bridge` dispatcher, last part: the follow-graph sync, the DMs,
the four inbox flows and the notifications pass.

The items the inbox flows print (a new follower, a conversation, a request, a notification) are
built by the screen readers of `actions/atomic/messaging/dm_actions.py`; `tests/unit/contract`
holds their dict literals to the shapes below.
"""

from __future__ import annotations

from .schema import HOST, Computed, Event, Field, ListOf, MapOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import ERROR_EVENT, STATUS_EVENT, network_reset_field
from .stop_reasons import RUN_HALT_CODE, TIKTOK_COMPLETION_REASON_OR_NONE
from .tiktok import TIKTOK_DM_OUTREACH
from .tiktok_automation import AI_SETTINGS
from .tiktok_lines import AI_PROFILE_DONE_EVENT, AI_RELEVANCE_EVENT, BOT_PROFILE_EVENT

_WORKFLOWS = "taktik.core.social_media.tiktok.actions.business.workflows"
_DM = f"{_WORKFLOWS}.dm.payload"
_INBOX = f"{_WORKFLOWS}.dm.inbox_payload"
_INBOX_LAUNCHER = f"{_WORKFLOWS}.dm.inbox_agent_handler:run_tiktok_inbox"


def _dispatch(*workflow_types: str) -> tuple:
    return (
        Field("deviceId", "string", "The adb serial of the phone.", required=True, by=HOST),
        Field("workflowType", OneOf(workflow_types), "Which workflow of the dispatcher runs.", required=True),
        network_reset_field(),
    )


#: The shared inbox launcher reads `mode` for every flow; only new followers and requests act on it.
_MODE_READ_ANYWAY = Field("mode", "string", "Read by the shared inbox launcher; this flow only lists.",
                          default="scrape", reader=f"{_INBOX}:inbox_mode_from_payload", app=False)


def _max_items(flow: str, default: int) -> Field:
    return Field("maxItems", "int", "Rows to read.", default=default, aliases=("max_items",),
                 reader=f"{_INBOX}:max_items_from_payload", reader_kwargs={"flow": flow})


# ------------------------------------------------------------------------------------ sync

SYNC_RUN_STATS = Shape(
    name="TikTokSyncRunStats",
    doc="`SyncListsStats.to_dict()`: what the sync saw and wrote.",
    fields=(
        *(Field(name, "int", doc) for name, doc in (
            ("rows_seen", "Rows read."),
            ("new_count", "Accounts added to the graph."),
            ("updated_count", "Accounts updated."),
            ("unidentified", "Rows without a readable handle, not resolved."),
            ("resolved", "Rows whose handle a profile visit read."),
            ("following_seen", "Accounts of the following list."),
            ("followers_seen", "Accounts of the followers list."),
            ("reciprocal_seen", "Accounts on both."),
            ("errors", "Rows that could not be written."),
        )),
        Field("stopped_early", "bool", "The run stopped before the end of a list."),
        Field("completion_reason", TIKTOK_COMPLETION_REASON_OR_NONE, "Why the run ended."),
        Field("elapsed_seconds", "number", "Time spent."),
        Field("elapsed_formatted", "string", "The same, for a person."),
    ),
)

TIKTOK_SYNC = WorkflowContract(
    workflow_id="tiktok.automation.sync_lists",
    also=("tiktok.automation.sync_following", "tiktok.automation.sync_followers"),
    name="TikTokSync",
    bridge="tiktok_bridge",
    doc="Read the acting account's own following and/or followers list into the follow graph.",
    launcher=f"{_WORKFLOWS}.sync_lists.agent_handler:run_tiktok_sync_lists",
    reader=f"{_WORKFLOWS}.sync_lists.payload:sync_config_from_payload",
    reader_kwargs={"list_type": "following"},
    settings=(
        Field("listType", OneOf(("following", "followers", "both")), "Which list(s) to read.",
              default=Computed("the list of the workflow type, else following"), aliases=("list_type",),
              reader=f"{_WORKFLOWS}.sync_lists.payload:list_type_from_payload"),
        Field("incremental", "bool", "Stop a list at the first account already known.", default=True,
              attr="incremental"),
        Field("maxScrolls", "int", "Scrolls of a list, at most.", default=60, aliases=("max_scrolls",),
              attr="max_scrolls"),
        Field("resolveMissingHandles", "bool", "Open the profile of a row without a readable handle.",
              default=False, aliases=("resolve_missing_handles",), attr="resolve_missing_handles"),
        Field("maxResolutions", "int", "Profile visits for those rows, at most.", default=50,
              aliases=("max_resolutions",), attr="max_resolutions"),
        Field("minDelay", "number", "Shortest pause between two scrolls, in seconds.", default=0.6,
              aliases=("min_delay",), attr="min_delay"),
        Field("maxDelay", "number", "Longest pause between two scrolls, in seconds.", default=1.4,
              aliases=("max_delay",), attr="max_delay"),
        Field("botUsername", "string", "The acting account, when the phone does not show it.",
              aliases=("bot_username",), reader=f"{_WORKFLOWS}.followers.payload:bot_username_from_payload"),
    ),
    bridge_fields=_dispatch("sync_following", "sync_followers", "sync_lists"),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("workflow_start", doc="The sync starts.", fields=(
            Field("target", "string", "The acting account."),
            Field("list_type", OneOf(("following", "followers", "both")), "The list(s) read."),
        )),
        Event("sync_user_discovered", doc="One row of a list.", fields=(
            Field("list_type", OneOf(("following", "followers")), "The list it was read in."),
            Field("username", "string", "Its handle."),
            Field("display_name", "string", "Its display name.", nullable=True),
            Field("relationship", "string", "What the row's button says about the relationship.", nullable=True),
            Field("is_new", "bool", "Added to the graph by this run."),
        )),
        Event("sync_stats", doc="The run's counters, at the end.", fields=(
            Field("stats", SYNC_RUN_STATS, "The counters."),
        )),
    ),
)

# ------------------------------------------------------------------------------------- DMs

DM_RUN_STATS = Shape(
    name="TikTokDmRunStats",
    doc="`DMStats.to_dict()`.",
    fields=(
        *(Field(name, "int", doc) for name, doc in (
            ("conversations_read", "Conversations read."),
            ("messages_read", "Messages read."),
            ("messages_sent", "Messages sent."),
            ("groups_skipped", "Group conversations skipped."),
            ("notifications_skipped", "Notification rows skipped."),
            ("errors", "Errors."),
        )),
        Field("elapsed_seconds", "number", "Time spent."),
        Field("elapsed_formatted", "string", "The same, for a person."),
    ),
)

DM_MESSAGE = Shape(
    name="TikTokDmMessageRead",
    doc="One message of a conversation (`DMActions.get_messages`).",
    fields=(
        Field("sender", "string", "Who wrote it, when the screen says.", nullable=True),
        Field("text", "string", "Its text; null for a sticker.", nullable=True),
        Field("type", OneOf(("text", "sticker")), "What it is."),
        Field("is_sent", "bool", "Written by the acting account."),
    ),
)

DM_CONVERSATION = Shape(
    name="TikTokDmConversation",
    doc="`ConversationData.to_dict()`: one conversation read.",
    fields=(
        Field("name", "string", "The name the inbox shows."),
        Field("is_group", "bool", "A group conversation."),
        Field("member_count", "int", "Its members (a group).", nullable=True),
        Field("messages", ListOf(DM_MESSAGE), "Its last messages."),
        Field("last_message", "string", "The last message's preview.", nullable=True),
        Field("timestamp", "string", "When, as the inbox writes it.", nullable=True),
        Field("unread_count", "int", "Unread messages."),
        Field("can_reply", "bool", "The conversation takes a reply."),
    ),
)

DM_PROGRESS_EVENT = Event("dm_progress", doc="The conversation being processed.", fields=(
    Field("current", "int", "Its rank, from 1."),
    Field("total", "int", "Conversations of the run."),
    Field("name", "string", "Its name."),
))
DM_STATS_EVENT = Event("dm_stats", doc="The run's counters.", fields=(Field("stats", DM_RUN_STATS, "The counters."),))

TIKTOK_DM_READ = WorkflowContract(
    workflow_id="tiktok.automation.dm_read",
    name="TikTokDmRead",
    bridge="tiktok_bridge",
    doc="Read the inbox's conversations and record them.",
    launcher=f"{_WORKFLOWS}.dm.agent_handler:run_tiktok_dm_read",
    reader=f"{_DM}:dm_read_config_from_payload",
    settings=(
        Field("maxConversations", "int", "Conversations to read.", default=20, aliases=("max_conversations",),
              attr="max_conversations"),
        Field("skipNotifications", "bool", "Skip the notification rows of the inbox.", default=True,
              aliases=("skip_notifications",), attr="skip_notifications"),
        Field("skipGroups", "bool", "Skip group conversations.", default=False, aliases=("skip_groups",),
              attr="skip_groups"),
        Field("onlyUnread", "bool", "Read only the unread conversations.", default=False,
              aliases=("only_unread",), attr="only_unread"),
        Field("delayBetweenConversations", "number", "Pause between two conversations, in seconds.", default=1.0,
              aliases=("delay_between_conversations",), attr="delay_between_conversations"),
        Field("markAsRead", "bool", "Leave the conversations read.", default=True, aliases=("mark_as_read",),
              attr="mark_as_read"),
        Field("closeStickerSuggestions", "bool", "Close the sticker suggestions over the keyboard.", default=True,
              aliases=("close_sticker_suggestions",), attr="close_sticker_suggestions"),
    ),
    bridge_fields=_dispatch("dm_read"),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("dm_conversation", doc="One conversation read.", fields=(
            Field("conversation", DM_CONVERSATION, "The conversation."),
        )),
        DM_PROGRESS_EVENT,
        DM_STATS_EVENT,
    ),
)

DM_TO_SEND = Shape(
    name="TikTokDmToSend",
    doc="One message to send: the conversation's name as the inbox shows it, and the text.",
    fields=(
        Field("conversation", "string", "The conversation's name."),
        Field("message", "string", "The text, typed as written."),
    ),
)

TIKTOK_DM_SEND = WorkflowContract(
    workflow_id="tiktok.automation.dm_send",
    name="TikTokDmSend",
    bridge="tiktok_bridge",
    doc="Send messages to conversations of the inbox and record the ones that left.",
    launcher=f"{_WORKFLOWS}.dm.agent_handler:run_tiktok_dm_send",
    reader=f"{_DM}:dm_send_config_from_payload",
    settings=(
        Field("messages", ListOf(DM_TO_SEND), "The messages, in order.", required=True,
              reader=f"{_DM}:dm_messages_from_payload"),
        Field("conversation", "string", "One conversation, when no list is sent.", aliases=("username",),
              reader=f"{_DM}:dm_messages_from_payload", attr="0.conversation", app=False),
        Field("message", "string", "Its text, when no list is sent.", reader=f"{_DM}:dm_messages_from_payload",
              attr="0.message", app=False),
        Field("delayBetweenMessages", "number", "Pause between two messages, in seconds.", default=1.0,
              aliases=("delay_between_messages", "delay_between_conversations"), attr="delay_between_conversations"),
        Field("delayAfterSend", "number", "Pause after a send, in seconds.", default=0.5,
              aliases=("delay_after_send",), attr="delay_after_send"),
        Field("closeStickerSuggestions", "bool", "Close the sticker suggestions over the keyboard.", default=True,
              aliases=("close_sticker_suggestions",), attr="close_sticker_suggestions"),
    ),
    bridge_fields=_dispatch("dm_send"),
    refusals=(Refusal("messages", unless=("conversation", "message"), doc="Nothing to send."),),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("dm_sent", doc="One message sent, or not.", fields=(
            Field("conversation", "string", "The conversation's name."),
            Field("success", "bool", "The message left."),
            Field("error", "string", "Why not.", nullable=True),
        )),
        DM_PROGRESS_EVENT,
        DM_STATS_EVENT,
    ),
)

# ------------------------------------------------------------------------------------ inbox

NEW_FOLLOWER = Shape(
    name="TikTokNewFollowerRow",
    doc="One row of the new-followers page (`DMActions.get_new_followers`).",
    fields=(
        Field("username", "string", "Its name, as the page shows it."),
        Field("activity", "string", "What the row says (started following you...)."),
        Field("can_follow_back", "bool", "The row offers to follow back."),
    ),
)

UNREPLIED_CONVERSATION = Shape(
    name="TikTokInboxConversationRow",
    doc="One conversation of the inbox (`DMActions.get_inbox_conversations`).",
    fields=(
        Field("username", "string", "Its name, as the inbox shows it."),
        Field("preview", "string", "Its last message's preview."),
        Field("unreplied", "bool", "The last message is theirs."),
    ),
)

MESSAGE_REQUEST = Shape(
    name="TikTokMessageRequestRow",
    doc="One message request (`DMActions.get_message_requests`).",
    fields=(
        Field("username", "string", "Its name."),
        Field("preview", "string", "The message's preview."),
        Field("timestamp", "string", "When, as the page writes it."),
    ),
)

ACTIVITY_NOTIFICATION = Shape(
    name="TikTokActivityNotificationRow",
    doc="One section of the inbox's activity and system notifications (`DMActions.get_inbox_notifications`).",
    fields=(
        Field("title", "string", "Its title."),
        Field("preview", "string", "Its preview."),
        Field("category", "string", "Its section."),
    ),
)

REQUEST_DECISION = Shape(
    name="TikTokRequestDecisionItem",
    doc="What to do with one request.",
    fields=(
        Field("username", "string", "The request's name, without @."),
        Field("action", OneOf(("accept", "decline")), "Accept or decline."),
        Field("message", "string", "A reply after accepting.", optional=True),
    ),
)

_DEVICE_READ = Field("deviceId", "string", "The adb serial (the welcome pass reads it).", aliases=("device_id",),
                     reader=f"{_INBOX}:device_id_from_payload", by=HOST)

TIKTOK_NEW_FOLLOWERS = WorkflowContract(
    workflow_id="tiktok.automation.new_followers",
    name="TikTokNewFollowers",
    bridge="tiktok_bridge",
    doc="List the new followers, or follow back a selection; an optional AI welcome pass.",
    launcher=_INBOX_LAUNCHER,
    launcher_kwargs={"flow": "new_followers"},
    reader=f"{_INBOX}:inbox_config_from_payload",
    reader_kwargs={"flow": "new_followers"},
    settings=(
        Field("mode", OneOf(("scrape", "follow_back")), "List them, or follow back a selection.", default="scrape",
              reader=f"{_INBOX}:inbox_mode_from_payload"),
        _max_items("new_followers", 50),
        Field("delayBetweenActions", "number", "Pause between two follow-backs, in seconds.", default=1.0,
              aliases=("delay_between_actions",), attr="delay_between_conversations"),
        Field("usernames", ListOf("string"), "The followers to follow back, without @.", default=(),
              aliases=("targetUsernames", "target_usernames"), reader=f"{_INBOX}:follow_back_usernames_from_payload"),
        _DEVICE_READ,
        *AI_SETTINGS,
    ),
    bridge_fields=_dispatch("new_followers")[1:],
    refusals=(Refusal("usernames", when={"mode": "follow_back"}, doc="A follow-back without a name."),),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("new_follower", doc="One new follower listed.", fields=(Field("follower", NEW_FOLLOWER, "The row."),)),
        Event("follow_back_result", doc="One follow-back done, or not.", fields=(
            Field("result", Shape(name="TikTokFollowBackResult", doc="One follow-back.", fields=(
                Field("username", "string", "The follower."),
                Field("success", "bool", "Followed back."),
                Field("error", "string", "Why not (`page_unavailable`).", optional=True),
            )), "The result."),
        )),
        # The welcome pass prints the cold DM's lines through the same notifier, and the AI's
        # verdict on each follower it qualifies.
        TIKTOK_DM_OUTREACH.event("dm_result"),
        TIKTOK_DM_OUTREACH.event("stats"),
        AI_PROFILE_DONE_EVENT,
        AI_RELEVANCE_EVENT,
    ),
)

TIKTOK_UNREPLIED = WorkflowContract(
    workflow_id="tiktok.automation.dm_unreplied",
    name="TikTokUnreplied",
    bridge="tiktok_bridge",
    doc="List the conversations, flagging the ones whose last message is theirs.",
    launcher=_INBOX_LAUNCHER,
    launcher_kwargs={"flow": "dm_unreplied"},
    reader=f"{_INBOX}:inbox_config_from_payload",
    reader_kwargs={"flow": "dm_unreplied"},
    settings=(
        _MODE_READ_ANYWAY,
        _max_items("dm_unreplied", 30),
        Field("onlyUnreplied", "bool", "List only the unanswered ones.", default=True, aliases=("only_unreplied",),
              reader=f"{_INBOX}:only_unreplied_from_payload"),
    ),
    bridge_fields=_dispatch("dm_unreplied"),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("unreplied_conversation", doc="One conversation listed.", fields=(
            Field("conversation", UNREPLIED_CONVERSATION, "The row."),
        )),
    ),
)

TIKTOK_REQUESTS = WorkflowContract(
    workflow_id="tiktok.automation.dm_requests",
    name="TikTokMessageRequests",
    bridge="tiktok_bridge",
    doc="List the message requests, or accept and decline a selection.",
    launcher=_INBOX_LAUNCHER,
    launcher_kwargs={"flow": "dm_requests"},
    reader=f"{_INBOX}:inbox_config_from_payload",
    reader_kwargs={"flow": "dm_requests"},
    settings=(
        Field("mode", OneOf(("scrape", "execute")), "List them, or apply decisions.", default="scrape",
              reader=f"{_INBOX}:inbox_mode_from_payload"),
        _max_items("dm_requests", 30),
        Field("delayBetweenActions", "number", "Pause between two decisions, in seconds.", default=1.0,
              aliases=("delay_between_actions",), attr="delay_between_conversations"),
        Field("decisions", ListOf(REQUEST_DECISION), "The decisions to apply.", default=(),
              reader=f"{_INBOX}:request_decisions_from_payload"),
    ),
    bridge_fields=_dispatch("dm_requests"),
    refusals=(Refusal("decisions", when={"mode": "execute"}, doc="Decisions to apply, and none sent."),),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("message_request", doc="One request listed.", fields=(Field("request", MESSAGE_REQUEST, "The row."),)),
        Event("request_result", doc="One decision applied, or not.", fields=(
            Field("result", Shape(name="TikTokRequestResult", doc="One decision.", fields=(
                Field("username", "string", "The request."),
                Field("action", OneOf(("accept", "decline")), "What was asked."),
                Field("success", "bool", "Done."),
                Field("replied", "bool", "The reply left (accept with a message)."),
            )), "The result."),
        )),
    ),
)

TIKTOK_ACTIVITY = WorkflowContract(
    workflow_id="tiktok.automation.dm_activity",
    name="TikTokActivity",
    bridge="tiktok_bridge",
    doc="Read the inbox's activity and system-notification sections.",
    launcher=_INBOX_LAUNCHER,
    launcher_kwargs={"flow": "dm_activity"},
    reader=f"{_INBOX}:inbox_config_from_payload",
    reader_kwargs={"flow": "dm_activity"},
    settings=(_MODE_READ_ANYWAY, _max_items("dm_activity", 20)),
    bridge_fields=_dispatch("dm_activity"),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("activity_notification", doc="One section read.", fields=(
            Field("notification", ACTIVITY_NOTIFICATION, "The row."),
        )),
    ),
)

# ---------------------------------------------------------------------------- notifications

NOTIFICATIONS_STATS = Shape(
    name="TikTokNotificationsStats",
    doc="What one pass did (`new_pass_stats`).",
    fields=(
        Field("new_followers_listed", "int", "New followers listed."),
        Field("new_followers_recorded", "int", "New followers recorded for the attribution."),
        Field("activity_read", "int", "Activity rows read."),
        Field("activity_by_kind", MapOf("int"), "Activity rows by kind."),
        Field("hello_sent", "int", "Hellos sent."),
        Field("suggested_followed", "int", "Suggestions followed."),
    ),
)

TIKTOK_NOTIFICATIONS = WorkflowContract(
    workflow_id="tiktok.automation.notifications",
    name="TikTokNotifications",
    bridge="tiktok_bridge",
    doc="One notifications pass: new followers, activity, hellos, suggested follows.",
    launcher=f"{_WORKFLOWS}.notifications.agent_handler:run_tiktok_notifications",
    reader=f"{_WORKFLOWS}.notifications.payload:notifications_settings_from_payload",
    settings=(
        Field("scanNewFollowers", "bool", "Record the new followers.", default=True,
              aliases=("scan_new_followers",), attr="scan_new_followers"),
        Field("maxFollowerResolutions", "int", "Display names to resolve into handles, one profile open each.",
              default=10, aliases=("max_follower_resolutions",), attr="max_follower_resolutions"),
        Field("readActivity", "bool", "Read the activity page.", default=True, aliases=("read_activity",),
              attr="read_activity"),
        Field("maxActivityRows", "int", "Activity rows to read.", default=30, aliases=("max_activity_rows",),
              attr="max_activity_rows"),
        Field("maxHellos", "int", "Hellos on threads never opened; 0: none.", default=0, aliases=("max_hellos",),
              attr="max_hellos"),
        Field("maxSuggestedFollows", "int", "Follows from the suggestions; 0: none.", default=0,
              aliases=("max_suggested_follows",), attr="max_suggested_follows"),
    ),
    bridge_fields=(
        Field("deviceId", "string", "The adb serial of the phone.", required=True, aliases=("device_id",), by=HOST),
        *_dispatch("notifications")[1:],
    ),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BOT_PROFILE_EVENT,
        Event("notifications_result", doc="The pass is over.", fields=(
            Field("success", "bool", "Every step it was asked for ran."),
            Field("stats", NOTIFICATIONS_STATS, "What it did."),
            Field("error", "string", "Why it failed.", optional=True),
            Field("stop_reason", RUN_HALT_CODE, "Why the stop latch stopped it (a block).", optional=True),
        )),
    ),
)

CONTRACTS = (
    TIKTOK_SYNC,
    TIKTOK_DM_READ,
    TIKTOK_DM_SEND,
    TIKTOK_NEW_FOLLOWERS,
    TIKTOK_UNREPLIED,
    TIKTOK_REQUESTS,
    TIKTOK_ACTIVITY,
    TIKTOK_NOTIFICATIONS,
)

__all__ = ["CONTRACTS"]
