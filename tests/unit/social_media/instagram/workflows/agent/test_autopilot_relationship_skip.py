"""The Taktik Agent autopilot is a GROWTH path: a profile already in a relationship (we follow
them, they follow us, pending request) is not an acquisition target. `_handle_profile_visit` must
skip it BEFORE the screenshot + the vision call (no wasted AI cost) and never reach `_do_follow`
(tapping "Following" would unfollow). Fail-open on 'unknown'/'follow' (proceed to the AI).
"""

import pytest

from taktik.core.social_media.instagram.workflows.agent.autopilot import TaktikAgentWorkflow


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("taktik.core.social_media.instagram.workflows.agent.autopilot.time.sleep", lambda *_a, **_k: None)


class _FakeAI:
    def __init__(self):
        self.calls = 0

    def decide_profile_follow(self, **_kwargs):
        self.calls += 1
        return {"follow": False, "extra_likes": 0, "cost_usd": 0.0, "reason": "test"}


def _make_agent(state: str, skip: bool = True):
    """Minimal instance (bypasses the heavy __init__) with the visit dependencies stubbed."""
    agent = object.__new__(TaktikAgentWorkflow)
    # No warmup budget handed by a launcher: the session's own quotas only.
    agent._warmup = None
    agent._warmup_stop = ""
    agent.stats = {
        "profile_visits": 0,
        "profiles_skipped_relationship": 0,
        "follows": 0,
        "likes": 0,
        "session_cost_usd": 0.0,
    }
    agent.quotas = {"max_follows": 20, "max_likes": 80}
    agent._skip_related_profiles = skip
    agent._persona_block = ""
    agent._ai = _FakeAI()

    counters = {"screenshot": 0, "feed": 0, "do_follow": 0}
    agent._navigate_to_profile = lambda _u: True
    agent._read_follow_state = lambda: state

    def _feed():
        counters["feed"] += 1
        return True

    def _shot(_name):
        counters["screenshot"] += 1
        return "/tmp/shot.png"

    def _follow(_u):
        counters["do_follow"] += 1

    agent._navigate_to_feed = _feed
    agent._take_screenshot = _shot
    agent._do_follow = _follow
    return agent, counters


@pytest.mark.parametrize("state", ["following", "requested", "follow_back", "message"])
def test_skips_related_profile_before_the_ai_call(state):
    agent, counters = _make_agent(state)
    agent._handle_profile_visit("someone")

    assert agent.stats["profiles_skipped_relationship"] == 1
    assert counters["screenshot"] == 0, "no vision cost on a skipped profile"
    assert agent._ai.calls == 0, "AI must not be called on a skipped profile"
    assert counters["do_follow"] == 0, "never reach _do_follow on an existing relationship"
    assert counters["feed"] == 1, "returned to the feed"


@pytest.mark.parametrize("state", ["follow", "unknown"])
def test_proceeds_when_no_relationship(state):
    agent, counters = _make_agent(state)
    agent._handle_profile_visit("someone")

    assert agent.stats["profiles_skipped_relationship"] == 0
    assert counters["screenshot"] == 1
    assert agent._ai.calls == 1, "a real target reaches the AI decision"


def test_disabled_flag_never_skips():
    agent, counters = _make_agent("following", skip=False)
    agent._handle_profile_visit("someone")

    assert agent.stats["profiles_skipped_relationship"] == 0
    assert counters["screenshot"] == 1
    assert agent._ai.calls == 1
