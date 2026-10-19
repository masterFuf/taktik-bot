"""A DM reply written by an AI (the AI mode's drafts) goes through the one rule before the phone.

The app says a reply was written by an AI by sending the account's frame (`aiDmRules`); a reply
the operator typed comes without it and is not held to the rule.
"""

from __future__ import annotations

import pytest

from taktik.core.ai.dm_rules import AiDmTextRefused
from taktik.core.social_media.instagram.workflows.dm.agent_handler import run_instagram_dm
from taktik.core.social_media.instagram.workflows.dm.payload import DmCommandError
from unit.ai_dm_texts import EACH_REASON, FRENCH_ACCOUNT, WITHIN_RULES


def _never_connect(package_name):
    raise AssertionError("the phone was connected")


def _reply(message, **extra):
    return {"command": "send", "username": "lea_bakery", "message": message, **extra}


@pytest.mark.parametrize("reason, text", EACH_REASON)
def test_a_reply_written_by_an_ai_is_refused_before_the_phone_for_each_reason(reason, text):
    with pytest.raises(AiDmTextRefused) as refused:
        run_instagram_dm(_reply(text, aiDmRules=FRENCH_ACCOUNT), connect=_never_connect)

    assert refused.value.refusal.reason == reason
    assert refused.value.refusal.index is None


@pytest.mark.parametrize("message, extra", [
    pytest.param(WITHIN_RULES, {"aiDmRules": FRENCH_ACCOUNT}, id="ai_within_the_rules"),
    pytest.param("Ok merci !", {}, id="the_operator_s_own"),
])
def test_a_reply_the_rule_lets_through_reaches_the_phone(message, extra):
    connected = []

    def connect(package_name):
        connected.append(package_name)
        raise RuntimeError("stop at the phone")

    with pytest.raises(RuntimeError, match="stop at the phone"):
        run_instagram_dm(_reply(message, **extra), connect=connect)

    assert connected == [None]


def test_an_unreadable_frame_is_a_refused_command():
    with pytest.raises(DmCommandError, match="aiDmRules"):
        run_instagram_dm(_reply(WITHIN_RULES, aiDmRules=["promo"]), connect=_never_connect)
