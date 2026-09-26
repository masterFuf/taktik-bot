"""The desktop's Post URL run, frozen: what the bridge asks of the phone and what it prints.

The snapshot beside this file was recorded from the bridge while it still read its payload itself,
before the run moved into the Agent handler. Same device calls, same stdout events in the same
order, same config, same exit code.

The fixed `posts_per_profile` became a range in every recording, on purpose: the page sends
`minPostsPerProfile`/`maxPostsPerProfile`, the config carries `min_`/`max_posts_per_profile`.
"""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_post_url_bridge_sequence.json").read_text(encoding="utf-8")
)
AI_KEY = "sk-or-v1-" + "a" * 48
NOBODY_COMMENTED = {"followers_seen": 0, "profiles_visited": 0, "posts_watched": 0, "likes": 0,
                    "follows": 0, "completion_reason": "no_targets"}


def scheduler_payload():
    """What scheduler-tiktok-runner.ts would send for a node naming `post_url`: the feed payload,
    no link (the node form has no field for one)."""
    return {
        "deviceId": "emulator-5554", "language": "fr", "maxVideos": 50, "maxLikesPerSession": 50,
        "maxFollowsPerSession": 20, "minWatchTime": 3, "maxWatchTime": 15, "likeProbability": 70,
        "followProbability": 20, "favoriteProbability": 10, "minLikes": None, "maxLikes": None,
        "skipAlreadyLiked": True, "skipAds": True, "pauseAfterActions": 20, "pauseDurationMin": 60,
        "pauseDurationMax": 180, "workflowType": "post_url", "requiredHashtags": [],
        "excludedHashtags": [], "followBackSuggestions": False,
    }


def _without(payload, *keys):
    for key in keys:
        payload.pop(key, None)
    return payload


def scenario(name, post_url_payload):
    """(payload, profile run outcomes, acting account) of one recorded run."""
    runs, account = [], "acting_account"
    if name == "post_url_page":
        payload = post_url_payload()
    elif name == "post_url_ai":
        payload = post_url_payload(language="fr",
                                   ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
    elif name == "post_url_likers_alias":
        payload = _without(post_url_payload(workflowType="post_likers",
                                            videoUrl="https://www.tiktok.com/@creator/video/2"), "postUrl")
    elif name == "post_url_budget_as_max_videos":
        payload = _without(post_url_payload(maxVideos=7, maxCommenters=20), "maxProfiles")
    elif name == "post_url_no_budget":
        payload = _without(post_url_payload(), "maxProfiles", "maxVideos")
    elif name == "post_url_comment_scrolls":
        payload = post_url_payload(maxCommentScrolls=3, commentProbability=20, commentTexts=["Top"])
    elif name == "post_url_nobody_commented":
        payload = post_url_payload()
        runs = [NOBODY_COMMENTED]
    elif name == "post_url_account_unread":
        payload = post_url_payload(botUsername="from_app")
        account = None
    elif name == "post_url_no_link":
        payload = _without(post_url_payload(), "postUrl")
    elif name == "post_url_blank_link":
        payload = post_url_payload(postUrl="   ")
    elif name == "post_url_no_device":
        payload = _without(post_url_payload(), "deviceId")
    elif name == "post_url_scheduler_node":
        payload = scheduler_payload()
    else:
        raise KeyError(name)
    return payload, runs, account


SCENARIOS = (
    "post_url_page", "post_url_ai", "post_url_likers_alias", "post_url_budget_as_max_videos",
    "post_url_no_budget", "post_url_comment_scrolls", "post_url_nobody_commented",
    "post_url_account_unread", "post_url_no_link", "post_url_blank_link", "post_url_no_device",
    "post_url_scheduler_node",
)


def observe(rig, name, post_url_payload):
    payload, runs, account = scenario(name, post_url_payload)
    rig.profile_runs = list(runs)
    rig.own_username = account
    code = rig.run_bridge(payload)
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "configs": [asdict(config) for config in rig.built_configs],
        "device_ids": [workflow.device_id for workflow in rig.workflows],
        "ai_installs": rig.ai_installs,
        "ai_services": rig.ai_services,
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, post_url_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, post_url_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["device_ids"] == expected["device_ids"]
    assert observed["ai_installs"] == expected["ai_installs"]
    assert observed["ai_services"] == expected["ai_services"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


def test_the_workflow_is_the_one_a_stop_signal_reaches(rig, post_url_payload):
    from bridges.common.runtime import signal_handler

    rig.run_bridge(post_url_payload())
    assert signal_handler._workflow is rig.workflows[-1]
