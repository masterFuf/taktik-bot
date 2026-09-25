"""The desktop's Followers, Target Profiles and Post URL runs, frozen: what the bridge asks of the
phone and what it prints.

The snapshot beside this file was recorded from the bridges before the multi-target loop moved
into the Agent handler; one scenario, marked below, was re-recorded on purpose. Same device calls
(the return home between two targets, the account each run acts as), same stdout events in the
same order, same config per target, same exit code.
"""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_followers_bridge_sequence.json").read_text(encoding="utf-8")
)
AI_KEY = "sk-or-v1-" + "a" * 48

# A target whose followers list shows nobody, and one whose list cannot be opened.
NOTHING_READ = {"followers_seen": 0, "profiles_visited": 0, "posts_watched": 0, "likes": 0, "follows": 0}


def _without(payload, *keys):
    for key in keys:
        payload.pop(key, None)
    return payload


def scheduler_payload():
    """What scheduler-tiktok-runner.ts sends for a Followers node with two targets."""
    return {
        "deviceId": "emulator-5554", "language": "fr", "maxVideos": 3, "maxLikesPerSession": 50,
        "maxFollowsPerSession": 20, "minWatchTime": 3, "maxWatchTime": 15, "likeProbability": 70,
        "followProbability": 20, "favoriteProbability": 10, "minLikes": None, "maxLikes": None,
        "skipAlreadyLiked": True, "skipAds": True, "pauseAfterActions": 20, "pauseDurationMin": 60,
        "pauseDurationMax": 180, "workflowType": "followers", "searchQuery": "alpha",
        "targets": ["alpha", "beta"], "maxFollowers": 3, "maxConsecutiveKnownUsernames": 150,
        "postsPerProfile": 3, "storyLikeProbability": 50, "minDelay": 3, "maxDelay": 8,
        "includeFriends": False,
    }


def qualify_payload():
    """What QualifyProfilesDialog.tsx sends: read and classify four handles, touch nothing."""
    return {
        "deviceId": "emulator-5554", "workflowType": "target_profiles",
        "profiles": ["a", "b", "c", "d"], "maxProfiles": 4, "language": "fr", "postsPerProfile": 0,
        "likeProbability": 0, "followProbability": 0, "favoriteProbability": 0,
        "maxLikesPerSession": 50, "maxFollowsPerSession": 20, "minWatchTime": 1, "maxWatchTime": 3,
        "minDelay": 2, "maxDelay": 5, "pauseAfterActions": 20, "pauseDurationMin": 20,
        "pauseDurationMax": 60, "includeFriends": True, "ai": {"enabled": True, "profileAnalysis": True},
    }


def post_url_payload():
    """What TikTokPostUrl.tsx sends."""
    return {
        "deviceId": "emulator-5554", "allowRouterDevice": False, "workflowType": "post_url",
        "postUrl": "https://www.tiktok.com/@creator/video/1", "maxCommenters": 12, "maxProfiles": 5,
        "maxVideos": 5, "maxLikesPerSession": 30, "maxFollowsPerSession": 10, "postsPerProfile": 1,
        "minWatchTime": 2, "maxWatchTime": 6, "likeProbability": 40, "followProbability": 5,
        "favoriteProbability": 0, "pauseAfterActions": 8, "pauseDurationMin": 20,
        "pauseDurationMax": 40, "requiredHashtags": [], "excludedHashtags": [], "minLikes": None,
        "maxLikes": None, "skipAlreadyLiked": True,
    }


def scenario(name, followers_payload):
    """(payload, profile run outcomes, acting account) of one recorded run."""
    runs, account = [], "acting_account"
    if name == "followers_two_targets":
        payload = followers_payload()
    elif name == "followers_ai":
        payload = followers_payload(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
    elif name == "followers_no_followers":
        payload = followers_payload()
        runs = [{**NOTHING_READ, "completion_reason": "no_more_followers"}]
    elif name == "followers_navigation_failed":
        payload = followers_payload()
        runs = [{**NOTHING_READ, "completion_reason": "navigation_failed"}]
    elif name == "followers_budget_exhausted":
        payload = followers_payload(targets=["alpha", "beta", "gamma"], maxFollowers=6,
                                    maxLikesPerSession=1, maxFollowsPerSession=1)
    elif name == "followers_limit_reached":
        payload = followers_payload()
        runs = [{"completion_reason": "max_likes_reached"}]
    elif name == "followers_budget_below_targets":
        # Re-recorded on purpose: the budget now caps the run, so the first target only and one
        # profile, announced as one target (the old bridge visited 2 + 1).
        payload = followers_payload(maxFollowers=1)
    elif name == "followers_scheduler":
        payload = scheduler_payload()
    elif name == "followers_account_unread":
        payload = followers_payload(botUsername="from_app")
        account = None
    elif name == "followers_no_target":
        payload = followers_payload(targets=[])
    elif name == "followers_blank_targets":
        payload = followers_payload(targets=["  "])
    elif name == "followers_no_device":
        payload = _without(followers_payload(), "deviceId")
    elif name == "target_profiles_page":
        payload = followers_payload(workflowType="target_profiles", profiles=["alpha", "@beta", "", "@"])
    elif name == "target_profiles_qualify":
        payload = qualify_payload()
    elif name == "target_profiles_no_profile":
        payload = followers_payload(workflowType="target_profiles")
    elif name == "post_url_page":
        payload = post_url_payload()
    else:
        raise KeyError(name)
    return payload, runs, account


SCENARIOS = (
    "followers_two_targets", "followers_ai", "followers_no_followers", "followers_navigation_failed",
    "followers_budget_exhausted", "followers_limit_reached", "followers_budget_below_targets",
    "followers_scheduler", "followers_account_unread", "followers_no_target",
    "followers_blank_targets", "followers_no_device", "target_profiles_page",
    "target_profiles_qualify", "target_profiles_no_profile", "post_url_page",
)


def observe(rig, name, followers_payload):
    payload, runs, account = scenario(name, followers_payload)
    rig.profile_runs = list(runs)
    rig.own_username = account
    code = rig.run_bridge(payload)
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "configs": [asdict(config) for config in rig.built_configs],
        "ai_installs": rig.ai_installs,
        "ai_services": rig.ai_services,
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, followers_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, followers_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["ai_installs"] == expected["ai_installs"]
    assert observed["ai_services"] == expected["ai_services"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


@pytest.mark.parametrize("budget, expected", [(1, [("alpha", 1)]), (3, [("alpha", 2), ("beta", 1)])])
def test_the_bridge_never_visits_more_profiles_than_max_followers(rig, followers_payload, budget, expected):
    """Every target used to get at least one profile: `maxFollowers` 1 on two targets visited 3."""
    rig.run_bridge(followers_payload(maxFollowers=budget))

    assert [(config.search_query, config.max_followers) for config in rig.built_configs] == expected
    assert sum(config.max_followers for config in rig.built_configs) == budget


def test_each_target_workflow_is_the_one_a_stop_signal_reaches(rig, followers_payload):
    from bridges.common.runtime import signal_handler

    rig.run_bridge(followers_payload())
    assert len(rig.workflows) == 2
    assert signal_handler._workflow is rig.workflows[-1]
