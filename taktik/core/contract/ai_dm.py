"""What a DM written by an AI may hold, declared once for every workflow that sends one.

A DM is written by an AI when a model wrote it: the bot's own (the cold DM's AI mode), the app's
(the DM replies and the welcome DM of its AI mode), or the model of an MCP client or of the app's
assistant (the texts of a cold DM). The operator's own texts are not held to these rules.

The rule itself lives in `taktik/core/ai/dm_rules.py`; this module holds what the app and the bot
share of it: the payload block that carries the account's frame, the reasons a text is refused,
the line that says so, and the tool bridge the app asks before it keeps a text in a proposal
(`ai_dm_check_bridge`: the rule run on texts, no phone).
"""

from __future__ import annotations

from .instagram_automation import ACCOUNT_PERSONA
from .schema import HOST, Event, Field, ListOf, OneOf, Shape, ToolContract
from .shared import ERROR_EVENT

#: Characters a DM written by an AI holds, both included (decision of 18/10, q. 33).
AI_DM_MIN_CHARS = 20
AI_DM_MAX_CHARS = 500

#: The reasons a text is refused, one constant each, so the rule and the catalogue say the same thing.
TOO_SHORT = "too_short"
TOO_LONG = "too_long"
LANGUAGE = "language"
LINK = "link"
EMAIL = "email"
PHONE = "phone"
FORBIDDEN_TERM = "forbidden_term"

AI_DM_REFUSAL_REASON = OneOf(
    (TOO_SHORT, TOO_LONG, LANGUAGE, LINK, EMAIL, PHONE, FORBIDDEN_TERM),
    name="AiDmRefusalReason",
    doc="Why a DM written by an AI is not sent (`taktik/core/ai/dm_rules.py`).",
)

AI_DM_RULES = Shape(
    name="AiDmRules",
    doc="The account's frame for a DM written by an AI: its presence says the texts were written by an AI. "
        f"Each text holds {AI_DM_MIN_CHARS} to {AI_DM_MAX_CHARS} characters, is in the account's language, "
        "carries no link, e-mail address nor phone number unless the frame allows them, and none of its "
        "forbidden terms.",
    fields=(
        Field("linksAllowed", "bool", "A link, an e-mail address or a phone number may be written.", default=False),
        Field("forbiddenTerms", ListOf("string"), "Terms never written, case and accents aside; a term also "
              "catches the words it starts (gratuit: gratuits, gratuitement).", default=()),
        Field("accountProfile", ACCOUNT_PERSONA, "The account's persona: its language, or the language it is "
              "written in. Absent: French or English only."),
    ),
)

AI_DM_TEXT_REFUSAL = Shape(
    name="AiDmTextRefusal",
    doc="A DM written by an AI the bot refused to send, and why, for the model to write it again.",
    fields=(
        Field("reason", AI_DM_REFUSAL_REASON, "The rule it breaks."),
        Field("detail", "string", "The same, measured (`612 characters, 500 at most`)."),
        Field("index", "int", "Its rank in the list it came in, from 1.", optional=True),
    ),
)

_RULES_READER = "taktik.core.ai.dm_rules:ai_dm_rules_from_payload"

AI_DM_CHECK = ToolContract(
    name="AiDmCheck",
    bridge="ai_dm_check_bridge",
    doc="The DM rule run on texts before they are kept in a proposal (`{texts, aiDmRules}` in its file): the "
        "same rule the bot applies before the phone, never a copy of it in the app.",
    events=(
        ERROR_EVENT,
        Event("ai_dm_check", doc="The verdict on the texts: its last line.", fields=(
            Field("checked", "int", "Texts checked."),
            Field("refusals", ListOf(AI_DM_TEXT_REFUSAL), "The texts the rule refuses, in order, each with its "
                  "rank (`index`, from 1); empty: every text may be sent."),
        )),
    ),
)

TOOLS = (AI_DM_CHECK,)


def ai_dm_rules_field(doc: str, **kwargs) -> Field:
    """The `aiDmRules` setting of a workflow that sends a DM, filled by the host from the account's frame."""
    return Field("aiDmRules", AI_DM_RULES, doc, by=HOST, via=_RULES_READER, **kwargs)


def ai_dm_text_refusal_field(doc: str) -> Field:
    """The `textRefusal` key of a line that reports a refused text."""
    return Field("textRefusal", AI_DM_TEXT_REFUSAL, doc, optional=True)


__all__ = [
    "EMAIL",
    "FORBIDDEN_TERM",
    "LANGUAGE",
    "LINK",
    "PHONE",
    "TOO_LONG",
    "TOO_SHORT",
    "AI_DM_CHECK",
    "AI_DM_MAX_CHARS",
    "AI_DM_MIN_CHARS",
    "AI_DM_REFUSAL_REASON",
    "AI_DM_RULES",
    "AI_DM_TEXT_REFUSAL",
    "TOOLS",
    "ai_dm_rules_field",
    "ai_dm_text_refusal_field",
]
