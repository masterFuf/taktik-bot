"""How a run asks for the AI, and so needs a key, is declared once, on its workflow.

`WorkflowContract.ai_request` says it (always, or under the settings that turn the AI on), and
`asks_for_ai` (`contract/ai_request.py`) is the one rule that reads it: the CLI refuses a run that asks
for the AI without a key by it (`missing_ai_key`), and the app's launch gate can read the same
declaration instead of keeping a table of its own. A workflow that reads an AI key without declaring
how it asks, or a request that names a setting the workflow does not have, is red here.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from taktik.core.contract.ai_request import asks_for_ai
from taktik.core.contract.bounds import holds
from taktik.core.contract.registry import WORKFLOW_CONTRACTS, contracts_by_id
from taktik.core.contract.schema import AiRequest, WorkflowContract, nested_fields

#: The key a run calls the AI with, under the three names the contracts give it (`ai_credential_fields`).
AI_KEY_FIELDS = {"apiKey", "aiApiKey", "ai_api_key"}
AGENT = "instagram.engagement.taktik_agent"


@pytest.mark.parametrize("workflow_id, payload, expected", [
    # A manual run asks for nothing.
    ("instagram.automation.feed", {}, False),
    ("instagram.automation.feed", {"ai": {"enabled": False, "profileAnalysis": True}}, False),
    ("instagram.automation.feed", {"ai": {"decision": {"mode": "decide"}}}, False),
    ("instagram.engagement.coldDm", {"messageMode": "manual"}, False),
    ("instagram.engagement.coldDm", {}, False),
    # The AI switched on, in the block of the run, in any of the ids one declaration serves.
    ("instagram.automation.feed", {"ai": {"enabled": True}}, True),
    ("instagram.automation.unfollow", {"ai": {"enabled": True}}, True),
    ("instagram.scraping.target", {"ai": {"enabled": True}}, True),
    ("instagram.scraping.hashtag", {"ai": {"enabled": True}}, True),
    ("tiktok.automation.for_you", {"ai": {"enabled": True}}, True),
    ("tiktok.automation.new_followers", {"ai": {"enabled": True, "newFollowers": {"enabled": True}}}, True),
    # The messages written by an AI, under either spelling of the setting.
    ("instagram.engagement.coldDm", {"messageMode": "ai"}, True),
    ("tiktok.standalone.tiktok_dm_outreach", {"messageMode": "ai"}, True),
    ("tiktok.standalone.tiktok_dm_outreach", {"message_mode": "ai"}, True),
    # The scan of the notifications qualifies the suggestions it visits; its other commands never do.
    ("instagram.engagement.notifications", {"command": "scan", "ai": {"enabled": True}}, True),
    ("instagram.engagement.notifications", {"command": "scan"}, False),
    ("instagram.engagement.notifications", {"command": "batch", "ai": {"enabled": True}}, False),
    # A model decides each gesture of the Agent: always.
    (AGENT, {}, True),
    # A workflow that declares no request never asks, whatever the payload carries; nor does an id nobody declares.
    ("tiktok.standalone.tiktok_unfollow", {"ai": {"enabled": True}}, False),
    ("instagram.account.login", {"ai": {"enabled": True}, "messageMode": "ai"}, False),
    ("nothing.declared.here", {"ai": {"enabled": True}}, False),
])
def test_a_run_asks_for_the_ai_as_its_workflow_declares(workflow_id: str, payload: Dict[str, Any], expected: bool):
    assert asks_for_ai(workflow_id, payload) is expected


def _reads_an_ai_key(contract: WorkflowContract) -> bool:
    """The workflow's settings hold the key of an AI call, or the AI block the notifications scan reads."""
    return any(item.key in AI_KEY_FIELDS for _path, item, _when, _via in nested_fields(contract.settings)) \
        or any(item.key == "ai" for item in contract.settings)


def test_every_workflow_that_reads_an_ai_key_declares_how_it_asks_and_no_other_does():
    wrong = {
        contract.workflow_id: ("declares" if contract.ai_request else "does not declare")
        for contract in WORKFLOW_CONTRACTS
        if (contract.ai_request is not None) != _reads_an_ai_key(contract)
    }
    assert not wrong, f"a request must go with an AI key, and an AI key with a request: {wrong}"


def _turned_on(request: AiRequest) -> Dict[str, Any]:
    """A payload that sets every setting the request names to the value that turns the AI on."""
    payload: Dict[str, Any] = {}
    for dotted, wanted in request.when.items():
        value = wanted[0] if isinstance(wanted, tuple) else wanted
        *parents, last = dotted.split(".")
        node = payload
        for key in parents:
            node = node.setdefault(key, {})
        node[last] = value
    return payload


def test_what_turns_the_ai_on_is_a_setting_of_the_workflow_and_turns_it_on():
    for contract in WORKFLOW_CONTRACTS:
        request = contract.ai_request
        if request is None:
            continue
        for workflow_id in contract.serves:
            if not request.when:
                # No condition: every run of the workflow asks.
                assert asks_for_ai(workflow_id, {}), workflow_id
                continue
            # Every named setting resolves in the declaration (a typo is a KeyError here, not a run that never asks).
            assert holds(contract.settings, _turned_on(request), request.when), workflow_id
            assert asks_for_ai(workflow_id, _turned_on(request)), workflow_id
            assert not asks_for_ai(workflow_id, {}), f"{workflow_id}: asks for the AI with nothing set"


def test_the_agent_alone_asks_for_the_ai_by_nature():
    always = [contract.workflow_id for contract in WORKFLOW_CONTRACTS
              if contract.ai_request is not None and not contract.ai_request.when]

    assert always == [AGENT]


def test_every_id_a_declaration_serves_is_found_by_the_rule():
    by_id = contracts_by_id()

    assert AGENT in by_id and "instagram.automation.sync_followers_following" in by_id
    assert by_id["instagram.automation.sync_followers_following"].ai_request == by_id["instagram.automation.feed"].ai_request
