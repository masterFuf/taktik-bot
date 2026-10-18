"""A cold DM written by an AI goes through the one rule before the phone, and the text sent is emitted.

Two moments: a list of messages an AI wrote (`aiDmRules` given: the assistant, an MCP client) is
checked when the payload is read, so the run is refused before the phone is connected; a text the
AI mode writes for one recipient is checked once written, before it is typed. Each text that the
conversation took is announced (`cold_dm_sent`) with what was really sent.
"""

from __future__ import annotations

import pytest

from taktik.core.ai.dm_rules import AiDmRules, AiDmTextRefused
from taktik.core.social_media.instagram.workflows.cold_dm import agent_handler
from taktik.core.social_media.instagram.workflows.cold_dm import workflow as module
from unit.ai_dm_texts import EACH_REASON, FRENCH_ACCOUNT, WITHIN_RULES


def _payload(**extra):
    return {"recipients": ["demo_recipient"], "messages": [WITHIN_RULES], "deviceId": "emulator-5554", **extra}


def _never_connect(package_name):
    raise AssertionError("the phone was connected")


@pytest.mark.parametrize("reason, text", EACH_REASON)
def test_a_list_written_by_an_ai_is_refused_before_the_phone_for_each_reason(reason, text):
    with pytest.raises(AiDmTextRefused) as refused:
        agent_handler.run_instagram_cold_dm(_payload(messages=[WITHIN_RULES, text], aiDmRules=FRENCH_ACCOUNT),
                                            connect=_never_connect)

    assert refused.value.refusal.reason == reason
    assert refused.value.refusal.index == 2


def test_the_operator_s_own_list_is_not_held_to_the_rule():
    """Without `aiDmRules` the texts are the operator's: a short one leaves as it always did."""
    connected = []

    def connect(package_name):
        connected.append(package_name)
        raise RuntimeError("stop after the reading")

    with pytest.raises(RuntimeError, match="stop after the reading"):
        agent_handler.run_instagram_cold_dm(_payload(messages=["Salut !"]), connect=connect)

    assert connected == [None]


class _Phone:
    """What `reach_and_send` asks of the phone, recorded; the search and the profile always answer."""

    def __init__(self):
        self.typed = []


def _workflow(monkeypatch, *, sent=None):
    monkeypatch.setattr(module, "look_for_action_block", lambda *args, **kwargs: False)
    monkeypatch.setattr(module, "ProblematicPageDetector", lambda device: None)
    phone = _Phone()
    workflow = module.ColdDMWorkflow(object(), object(), keyboard=object(), sent=sent)
    workflow.navigate_to_search = lambda: True
    workflow.search_user = lambda recipient: True
    workflow.open_dm_from_profile = lambda policy=None: True
    workflow.send_message = lambda message: phone.typed.append(message) or True
    workflow.go_home = lambda: None
    workflow.filter_pending_recipients = lambda recipients, account_id: list(recipients)
    workflow._detect_app_language = lambda: None
    return workflow, phone


@pytest.mark.parametrize("reason, text", EACH_REASON)
def test_a_text_the_ai_mode_wrote_is_refused_before_it_is_typed_for_each_reason(monkeypatch, reason, text):
    workflow, phone = _workflow(monkeypatch)
    rules = AiDmRules(base_language="fr", forbidden_terms=("gratuit",))

    reached = workflow.reach_and_send("demo_recipient", lambda: text, rules=rules)

    assert reached["outcome"] == module.TEXT_REFUSED and reached["refusal"].reason == reason
    assert phone.typed == []


def test_a_text_the_ai_mode_wrote_within_the_rules_is_typed(monkeypatch):
    workflow, phone = _workflow(monkeypatch)

    reached = workflow.reach_and_send("demo_recipient", lambda: WITHIN_RULES, rules=AiDmRules(base_language="fr"))

    assert reached["outcome"] == module.SENT and phone.typed == [WITHIN_RULES]


def _ai_run(monkeypatch, written, rules):
    announced = []
    workflow, phone = _workflow(monkeypatch, sent=lambda **line: announced.append(line))
    monkeypatch.setattr("taktik.core.social_media.instagram.workflows.cold_dm.messages.generate_ai_message",
                        lambda username, *args, **kwargs: written[username])
    monkeypatch.setattr(module, "apply_cold_dm_send_result",
                        lambda *, workflow, **kwargs: setattr(workflow, "dms_sent", workflow.dms_sent + 1))
    monkeypatch.setattr(module, "wait_before_next_cold_dm", lambda **kwargs: None)
    result = workflow.run(list(written), [], ai_prompt="Parle de sa boutique", openrouter_api_key="sk-test",
                          ai_dm_rules=rules)
    return result, phone, announced


def test_an_ai_run_sends_the_texts_within_the_rules_and_announces_each_one(monkeypatch):
    written = {"lea_bakery": WITHIN_RULES, "marc_shop": "Salut !"}

    result, phone, announced = _ai_run(monkeypatch, written, AiDmRules(base_language="fr"))

    assert phone.typed == [WITHIN_RULES]
    assert announced == [{"current": 1, "username": "lea_bakery", "message": WITHIN_RULES, "ai_written": True}]
    assert result["texts_refused"] == 1 and result["dms_failed"] == 0


def test_the_launcher_holds_the_ai_mode_to_the_most_prudent_frame_without_a_block(monkeypatch):
    """No `aiDmRules`: the bot's own AI texts are still checked (no link, French or English)."""
    seen = {}

    class _Recording:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args, ai_dm_rules=None, **kwargs):
            seen["rules"] = ai_dm_rules
            return {"success": True}

    monkeypatch.setattr(agent_handler, "open_cold_dm_session", lambda *args, **kwargs: None)
    agent_handler.run_instagram_cold_dm(
        _payload(messages=[], messageMode="ai", aiPrompt="Parle de sa boutique", openrouterApiKey="sk-test"),
        connect=lambda package_name: agent_handler.ColdDmRuntime(object(), object(), object()),
        workflow_factory=_Recording,
    )

    assert seen["rules"] == AiDmRules()
