"""The Taktik Agent autopilot stops at the first "Try again later" (secours 2, 2026-09-24).

Its loops only read `_stop_requested`, the deadline and the quotas: a block seen anywhere, or a
lost phone, never stopped them. Now `_should_stop` reads the run's lock, and `_block_seen` -- the
real detector, after each like, comment or follow of the autopilot -- is what sets it.
"""

import pytest

from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow
from taktik.core.shared.diagnostics import run_halt


_BLOCK_DIALOG = (
    '<hierarchy rotation="0"><node class="android.widget.FrameLayout" package="com.instagram.android">'
    '<node text="Try Again Later" resource-id="com.instagram.android:id/igds_alert_dialog_headline"/>'
    '<node text="We limit how often you can do certain things on Instagram to protect our community."'
    ' resource-id="com.instagram.android:id/igds_alert_dialog_subtext"/>'
    '<node text="OK" resource-id="com.instagram.android:id/igds_alert_dialog_primary_button"/>'
    '</node></hierarchy>'
)
_FEED_SCREEN = (
    '<hierarchy rotation="0"><node class="android.widget.FrameLayout" package="com.instagram.android">'
    '<node text="bob" resource-id="com.instagram.android:id/row_feed_photo_profile_name"/>'
    '</node></hierarchy>'
)


@pytest.fixture(autouse=True)
def _lock_lifted(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.agent.scenarios.instagram_feed_autopilot.time.sleep", lambda *_a, **_k: None
    )
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


class _Phone:
    def __init__(self, xml):
        self._xml = xml

    def dump_hierarchy(self, *a, **k):
        return self._xml


def _agent(phone=None):
    agent = object.__new__(TaktikAgentWorkflow)
    agent._stop_requested = False
    agent.device = phone
    agent.stats = {
        "posts_seen": 0, "likes": 0, "follows": 0, "comments": 0,
        "profile_visits": 0, "profiles_skipped_relationship": 0, "session_cost_usd": 0.0,
    }
    agent.quotas = {
        "max_posts_seen": 100, "max_likes": 80, "max_follows": 20, "max_comments": 10,
    }
    return agent


def test_the_lock_stops_the_autopilot():
    agent = _agent()
    far = 10 ** 12

    assert agent._should_stop(far) is False
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "le telephone ne repond plus")
    assert agent._should_stop(far) is True


def test_seeing_the_dialog_after_a_write_sets_the_lock():
    agent = _agent(_Phone(_BLOCK_DIALOG))

    assert agent._block_seen("like") is True
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED
    assert agent._should_stop(10 ** 12) is True


def test_an_ordinary_screen_lets_it_go_on():
    agent = _agent(_Phone(_FEED_SCREEN))

    assert agent._block_seen("like") is False
    assert run_halt.arret_demande() is None


def test_a_check_that_cannot_read_the_screen_is_not_a_block():
    agent = _agent(phone=None)

    assert agent._block_seen("follow") is False


class _FakeAI:
    def decide_profile_follow(self, **_kwargs):
        return {"follow": True, "extra_likes": 2, "cost_usd": 0.0, "reason": "test"}


def test_a_refused_follow_skips_the_extra_likes():
    agent = _agent()
    agent._skip_related_profiles = True
    agent._persona_block = ""
    agent._ai = _FakeAI()
    calls = {"follow": 0, "likes": 0, "feed": 0}
    agent._navigate_to_profile = lambda _u: True
    agent._read_follow_state = lambda: "follow"
    agent._take_screenshot = lambda _n: "/tmp/shot.png"
    agent._do_follow = lambda _u: calls.__setitem__("follow", calls["follow"] + 1)
    agent._like_profile_posts = lambda _u, _n: calls.__setitem__("likes", calls["likes"] + 1)
    agent._navigate_to_feed = lambda: calls.__setitem__("feed", calls["feed"] + 1) or True
    agent._block_seen = lambda _action: True

    agent._handle_profile_visit("alice")

    assert calls["follow"] == 1
    assert calls["likes"] == 0
    assert calls["feed"] >= 1
