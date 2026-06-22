"""Unit tests for the DM inbox triage (skip conversations we already answered).

The inbox row content-desc reveals who sent last: "username, Sent <time>" /
"username, Envoyé il y a <time>" when WE replied, vs the interlocutor's message text
when they wrote last. We skip re-opening the former.
"""

from bridges.instagram.engagement.runtime.dm.conversation_payload import (
    is_outgoing_last_message,
    build_answered_conversation,
)

PREFIXES = ["Sent", "Envoyé"]


def test_outgoing_detected_en_and_fr():
    assert is_outgoing_last_message("dsnutrition._, Sent 49m ago", "dsnutrition._", PREFIXES) is True
    assert is_outgoing_last_message("Fabrice ...., Envoyé il y a 49 min", "Fabrice ....", PREFIXES) is True


def test_incoming_message_is_not_outgoing():
    cd = "blissand_glow, Merci de t être abonnée à ma page et bienvenue !! ·, 2w"
    assert is_outgoing_last_message(cd, "blissand_glow", PREFIXES) is False


def test_empty_or_plain_message_is_not_outgoing():
    assert is_outgoing_last_message("", "x", PREFIXES) is False
    assert is_outgoing_last_message("user, hello there, 2w", "user", PREFIXES) is False
    # No prefixes configured → never treat as outgoing.
    assert is_outgoing_last_message("user, Sent 1m ago", "user", []) is False


def test_answered_conversation_shape():
    conv = build_answered_conversation(real_username="bob", inbox_username="bob")
    assert conv["last_message_is_ours"] is True
    assert conv["can_reply"] is False
    assert conv["messages"] == []
