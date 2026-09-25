"""The desktop's Search and Hashtag runs, frozen: what the bridge asks of the phone and prints.

The snapshot beside this file was recorded from the bridge before its launcher moved into the
Agent handler. Same device calls (including the return home between two queries), same stdout
events in the same order, same config per query, same exit code.
"""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_search_bridge_sequence.json").read_text(encoding="utf-8")
)
AI_KEY = "sk-or-v1-" + "a" * 48


def hashtag_payload(page_payload, **overrides):
    """What TikTokHashtag.tsx sends: the For You page keys minus the feed-only ones."""
    payload = page_payload(workflowType="hashtag", searchQuery="run", hashtags=["run", "#trail", "run"])
    for key in ("commentTexts", "trainingKeywords", "trainingRejectOffNiche", "maxRejectionsPerSession",
                "followBackSuggestions"):
        payload.pop(key, None)
    payload.update(overrides)
    return payload


def scenario_payload(name, page_payload):
    if name == "hashtag_two":
        return hashtag_payload(page_payload)
    if name == "search_ai":
        payload = hashtag_payload(page_payload, workflowType="search", searchQuery="street food",
                                  searchQueries=["street food"], language="fr",
                                  ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
        payload.pop("hashtags")
        return payload
    if name == "budget_exhausted":
        return hashtag_payload(page_payload, hashtags=["run", "trail", "gym"],
                               maxLikesPerSession=1, maxFollowsPerSession=1)
    if name == "no_query":
        return hashtag_payload(page_payload, searchQuery="", hashtags=[])
    if name == "no_device":
        payload = hashtag_payload(page_payload)
        payload.pop("deviceId")
        return payload
    raise KeyError(name)


@pytest.mark.parametrize("name", sorted(SNAPSHOT))
def test_the_bridge_runs_exactly_as_recorded(rig, page_payload, name):
    code = rig.run_bridge(scenario_payload(name, page_payload))
    observed = json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, payload] for kind, payload in rig.events],
        "configs": [asdict(config) for config in rig.built_configs],
        "ai_installs": rig.ai_installs,
        "ai_services": rig.ai_services,
    }))
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["ai_installs"] == expected["ai_installs"]
    assert observed["ai_services"] == expected["ai_services"]
    assert observed["exit"] == expected["exit"]


def test_each_query_workflow_is_the_one_a_stop_signal_reaches(rig, page_payload):
    from bridges.common.runtime import signal_handler

    rig.run_bridge(scenario_payload("hashtag_two", page_payload))
    assert signal_handler._workflow is rig.workflows[-1]
