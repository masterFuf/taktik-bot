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


def test_a_lock_already_set_answers_without_a_dump():
    """Set inside a like loop, by a comment, during a navigation: no second dump."""
    phone = _CountingPhone(_FEED_SCREEN)
    agent = _agent(phone)
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    assert agent._block_seen("like") is True
    assert phone.dumps == 0


def test_no_profile_visit_after_a_block():
    """A block seen in the hashtag burst: the loop still reached the profile visit of the post's
    decision -- navigation, a paid AI call, then a follow, with no look at the lock."""
    agent = _agent()
    calls = []
    agent._navigate_to_profile = lambda username: calls.append(username) or True
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    agent._handle_profile_visit("alice")

    assert calls == []


class _CountingPhone(_Phone):
    def __init__(self, xml):
        super().__init__(xml)
        self.dumps = 0

    def dump_hierarchy(self, *a, **k):
        self.dumps += 1
        return super().dump_hierarchy(*a, **k)


class _FeedAI:
    def decide_feed_action(self, **_kwargs):
        return {"action": "like_comment", "comment": "Superbe", "visit_profile": False,
                "cost_usd": 0.0, "reason": "test"}


def test_the_feed_loop_stops_between_a_refused_like_and_its_comment(monkeypatch):
    import time as _time

    import taktik.core.agent.scenarios.instagram_feed_autopilot as autopilot
    import taktik.core.social_media.instagram.actions.business.workflows.feed as feed_package

    gestures = []

    class _Feed:
        def __init__(self, *_a, **_k):
            pass

        def _scroll_to_next_post(self):
            gestures.append("scroll")

        def _is_sponsored_post(self):
            return False

        def _is_reel_post(self):
            return False

        def _get_current_post_author(self):
            return "bob"

        def _like_current_post(self):
            gestures.append("like")
            return True

        def _comment_current_post(self, _config):
            gestures.append("comment")
            return True

    monkeypatch.setattr(feed_package, "FeedBusiness", _Feed)
    monkeypatch.setattr(autopilot.random, "randint", lambda *_a: 1)

    class _Screen(_Phone):
        def dump_hierarchy(self, *a, **k):
            return _BLOCK_DIALOG if "like" in gestures else _FEED_SCREEN

    agent = _agent(_Screen(_FEED_SCREEN))
    agent.config = {"skip_reels": True}
    agent.ipc = None
    agent.device_manager = None
    agent._consecutive_skips = 0
    agent._hashtag_pool = []
    agent._ai = _FeedAI()
    agent._take_screenshot = lambda _label: "/tmp/shot.png"
    agent._session_start = _time.time()
    agent.stats["posts_stopped"] = 0
    agent._persona_block = ""
    agent._stop_requested = False
    agent.quotas.update({"max_profile_visits": 10, "session_duration_min": 5})

    agent._run_feed_loop()

    assert gestures == ["like"]
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED
