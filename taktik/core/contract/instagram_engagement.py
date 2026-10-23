"""Instagram engagement: the cold DM (`cold_dm_bridge`), the DM inbox read and reply (`dm_bridge`).

Each declaration names the reader it describes; `tests/unit/contract` holds the reader, the
launcher and the bridge to it.
"""

from __future__ import annotations

from .ai_dm import ai_dm_rules_field, ai_dm_text_refusal_field
from .schema import HOST, Bounds, Computed, Event, Field, ListOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import (
    AI_REQUEST_MESSAGES,
    ai_credential_fields,
    AI_SPEND_EVENT,
    ERROR_CODE_FIELD,
    ERROR_EVENT,
    SESSION_START_EVENT,
    device_field,
    instagram_package_field,
    network_reset_field,
)
from .stop_reasons import RUN_HALT_CODE

_WORKFLOWS = "taktik.core.social_media.instagram.workflows"

# ------------------------------------------------------------------------------------- cold DM

INSTAGRAM_COLD_DM = WorkflowContract(
    workflow_id="instagram.engagement.coldDm",
    name="InstagramColdDm",
    bridge="cold_dm_bridge",
    doc="Write to a list of accounts the acting account never wrote to.",
    launcher=f"{_WORKFLOWS}.cold_dm.agent_handler:run_instagram_cold_dm",
    ai_request=AI_REQUEST_MESSAGES,
    reader=f"{_WORKFLOWS}.cold_dm.payload:cold_dm_request_from_payload",
    reader_kwargs={"default_session_id": "<device>"},
    settings=(
        Field("recipients", ListOf("string"), "Handles to write to, resolved by the app from the page's source.",
              required=True, attr="recipients"),
        Field("messages", ListOf("string"), "Messages to pick from; in AI mode, unused.", default=(),
              attr="messages"),
        Field("delayMin", "number", "Shortest pause between two recipients, in seconds.", default=30,
              attr="delay_min", bounds=Bounds(minimum=5, maximum=600)),
        Field("delayMax", "number", "Longest pause between two recipients, in seconds.", default=60,
              attr="delay_max", bounds=Bounds(minimum=5, maximum=600)),
        Field("maxDmsPerSession", "int", "Stop after this many messages.", default=50, attr="max_dms",
              bounds=Bounds(minimum=1, maximum=100)),
        Field("messageMode", OneOf(("manual", "ai")), "The static list, or one message written per recipient.",
              default="manual", attr="message_mode"),
        Field("aiPrompt", "string", "What the AI message says (AI mode).", default="", attr="ai_prompt"),
        Field("skipPrivateAccounts", "bool", "Leave private profiles alone.", default=True, attr="skip_private"),
        Field("skipVerifiedAccounts", "bool", "Leave certified profiles alone.", default=False,
              attr="skip_verified"),
        *ai_credential_fields("aiProvider", "aiApiKey", openrouter_key_names=("openrouterApiKey",),
                              attr="ai_credential"),
        Field("sessionAccountId", "int", "The account seen on the phone: the run's session is filed under it, "
              "none without it; injected by the host.", attr="session_account_id", by=HOST),
        Field("accountId", "int", "The acting account's row, for the sent-DM markers (and the session when "
              "`sessionAccountId` is absent).", default=1, attr="account_id", app=False),
        Field("sessionId", "string", "Tags the sent-DM markers of this run.", default=Computed("the device id"),
              attr="session_id", app=False),
        ai_dm_rules_field("The account's frame for a text written by an AI. Present: `messages` were written by "
                          "an AI and are checked before the phone, the run is refused on the first one the rule "
                          "refuses. Absent: `messages` are the operator's; in AI mode the bot's own texts are "
                          "still checked, under the most prudent frame."),
        instagram_package_field(),
    ),
    bridge_fields=(
        device_field("deviceId"),
        network_reset_field(),
    ),
    refusals=(
        Refusal("recipients", doc="Nobody to write to."),
        Refusal("messages", when={"messageMode": "manual"}, doc="Manual mode without a message."),
    ),
    events=(
        AI_SPEND_EVENT,
        SESSION_START_EVENT,
        Event("progress", doc="The recipient being processed.", fields=(
            Field("current", "int", "Its rank, from 1."),
            Field("total", "int", "Recipients this run will process."),
            Field("username", "string", "Its handle."),
        )),
        Event("cold_dm_sent", doc="A message the conversation took: the text really sent to the recipient.", fields=(
            Field("current", "int", "The recipient's rank, from 1."),
            Field("username", "string", "Its handle."),
            Field("message", "string", "The text sent."),
            Field("aiWritten", "bool", "Written by an AI (the bot's AI mode, or `aiDmRules` given)."),
        )),
        Event("cold_dm_result", doc="The run's verdict: its last line.", fields=(
            Field("success", "bool", "The run went through its list."),
            Field("dmsSent", "int", "Messages sent.", optional=True),
            Field("dmsSuccess", "int", "Messages the conversation shows.", optional=True),
            Field("dmsFailed", "int", "Recipients that failed.", optional=True),
            Field("error", "string", "What went wrong, for a person.", optional=True, nullable=True),
            Field("stopReason", RUN_HALT_CODE, "Why the run stopped early (`action_blocked`...).", optional=True),
            Field("textsRefused", "int", "Texts the AI mode wrote and the rule refused: not sent.", optional=True),
            ai_dm_text_refusal_field("The text of `messages` that refused the run before the phone."),
        )),
    ),
)

# ------------------------------------------------------------------------------------- DM inbox

DM_MESSAGE = Shape(
    name="InstagramDmMessage",
    doc="One message of a conversation, oldest first.",
    fields=(
        Field("type", OneOf(("text", "reel")), "A text, or a shared reel."),
        Field("text", "string", "Its text (a reel: its author)."),
        Field("is_sent", "bool", "Sent by the acting account."),
        Field("timestamp", "string", "The time shown above it, when one is.", optional=True),
        Field("reaction", "string", "The reaction under it, when one is.", optional=True),
    ),
)

DM_CONVERSATION = Shape(
    name="InstagramDmConversation",
    doc="A conversation of the inbox (`build_*_conversation`, `workflows/dm/conversation_payload.py`).",
    fields=(
        Field("username", "string", "The other account."),
        Field("inbox_username", "string", "Its name as the inbox row shows it.", optional=True),
        Field("messages", ListOf(DM_MESSAGE), "The messages read; empty when the thread was not reopened."),
        Field("is_group", "bool", "A group conversation."),
        Field("can_reply", "bool", "A reply can be written."),
        Field("last_message_is_ours", "bool", "The acting account wrote last.", optional=True),
        Field("up_to_date", "bool", "Not reopened: its last message is already on record.", optional=True),
    ),
)

_DM_LAUNCHER = f"{_WORKFLOWS}.dm.agent_handler:run_instagram_dm"
_DM_READER = f"{_WORKFLOWS}.dm.payload:dm_command_from_payload"
_DM_BRIDGE_FIELDS = (device_field("deviceId"),)


def _dm_result(*fields: Field) -> Event:
    return Event("result", doc="The command's result, or why it failed: the last line.", fields=(
        Field("success", "bool", "The command did what it was asked."),
        *fields,
        Field("error", "string", "What went wrong, for a person.", optional=True),
        ERROR_CODE_FIELD,
        Field("traceback", "string", "Diagnostic context of a crash.", optional=True),
    ))


INSTAGRAM_DM_READ = WorkflowContract(
    workflow_id="instagram.engagement.dm_read",
    name="InstagramDmRead",
    bridge="dm_bridge",
    doc="Read the inbox, or its requests folder.",
    launcher=_DM_LAUNCHER,
    reader=_DM_READER,
    settings=(
        Field("command", OneOf(("read", "read_requests")), "The inbox, or the message requests.", required=True,
              attr="command"),
        Field("limit", "int", "Conversations to read; 0: all.", default=10, attr="limit",
              bounds=Bounds(minimum=1, maximum=50, unbounded_at=0)),
        instagram_package_field(),
    ),
    bridge_fields=_DM_BRIDGE_FIELDS,
    refusals=(Refusal("command", doc="No command."),),
    # `error`: a refusal at the network door (`send_network_refusal`), read by the app's crash capture;
    # the page reads the last line, which carries the same code.
    events=(
        ERROR_EVENT,
        Event("account_detected", doc="The account the inbox belongs to, read from its header.", fields=(
            Field("account_username", "string", "Its handle."),
        )),
        Event("conversation", doc="One conversation read.", fields=(
            Field("current", "int", "Its rank, from 1."),
            Field("total", "int", "Conversations asked for; 0: all."),
            Field("conversation", DM_CONVERSATION, "The conversation."),
        )),
        Event("conversation_skipped", doc="A thread left closed: its last message is already on record.", fields=(
            Field("reason", OneOf(("up_to_date",)), "Why."),
            Field("username", "string", "The other account."),
            Field("last_message_is_ours", "bool", "The acting account wrote last."),
            Field("current", "int", "Its rank, from 1."),
            Field("total", "int", "Conversations asked for; 0: all."),
        )),
        _dm_result(
            Field("conversations", ListOf(DM_CONVERSATION), "Every conversation read.", optional=True),
            Field("total", "int", "How many.", optional=True),
            Field("account_username", "string", "The account the inbox belongs to.", optional=True, nullable=True),
            Field("is_requests", "bool", "Read from the requests folder.", optional=True),
        ),
    ),
)

INSTAGRAM_DM_SEND = WorkflowContract(
    workflow_id="instagram.engagement.dm_send",
    name="InstagramDmSend",
    bridge="dm_bridge",
    doc="Reply in one conversation.",
    launcher=_DM_LAUNCHER,
    reader=_DM_READER,
    settings=(
        Field("command", OneOf(("send",)), "A reply.", required=True, attr="command"),
        Field("username", "string", "The conversation to reply in.", required=True, attr="username"),
        Field("message", "string", "The reply.", required=True, attr="message"),
        Field("receivedMessage", "string", "The message this reply answers. With the frame, the reply may be in its "
              "language as well as the account's; absent or too short to be recognised: the account's language "
              "only.", optional=True, attr="received_message"),
        ai_dm_rules_field("The account's frame for a reply written by an AI (the AI mode's drafts). Present: the "
                          "reply is checked before the phone and refused if the rule refuses it. Absent: the "
                          "reply is the operator's."),
        instagram_package_field(),
    ),
    bridge_fields=_DM_BRIDGE_FIELDS,
    refusals=(
        Refusal("command", doc="No command."),
        Refusal("username", doc="Nobody to reply to."),
        Refusal("message", doc="Nothing to reply."),
    ),
    events=(
        ERROR_EVENT,
        _dm_result(
            Field("username", "string", "The conversation replied in.", optional=True),
            Field("message", "string", "The reply sent.", optional=True),
            ai_dm_text_refusal_field("The rule the reply breaks: refused before the phone."),
        ),
    ),
)

CONTRACTS = (INSTAGRAM_COLD_DM, INSTAGRAM_DM_READ, INSTAGRAM_DM_SEND)

__all__ = ["CONTRACTS", "INSTAGRAM_COLD_DM", "INSTAGRAM_DM_READ", "INSTAGRAM_DM_SEND"]
