"""The first "Try again later" ends the run, wherever it is seen (secours 2, 2026-09-24).

Before: the detector SAW Instagram's rate-limit dialog, closed it, and the run acted again
right after -- the gesture that turns a temporary limit into a lasting restriction. Only the
followers workflow, when its list was out of reach, called it a block and stopped.

Now the detector sets the run's stop lock (`run_halt.ACTION_BLOCKED`) as soon as it sees the
dialog, `should_continue` turns it into the `action_blocked` stop reason, the interaction engine
looks for the dialog after each phase that wrote, and the feed loop reads the lock it ignored.
The detector used here is the real one; only the phone is fake.
"""

import random
import types

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager
from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
    InteractionEngineMixin,
)
from taktik.core.social_media.instagram.actions.core.base_business.config_parsing import (
    ConfigParsingMixin,
)
import taktik.core.social_media.instagram.actions.business.workflows.feed.workflow as feed_module
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import FEED_DEFAULTS


_BLOCK_DIALOG = (
    '<hierarchy rotation="0">'
    '<node class="android.widget.FrameLayout" package="com.instagram.android" bounds="[0,0][1080,2400]">'
    '<node class="android.widget.TextView" text="Try Again Later" '
    'resource-id="com.instagram.android:id/igds_alert_dialog_headline" bounds="[100,900][980,980]"/>'
    '<node class="android.widget.TextView" text="We limit how often you can do certain things on '
    'Instagram to protect our community. Tell us if you think we made a mistake." '
    'resource-id="com.instagram.android:id/igds_alert_dialog_subtext" bounds="[100,1000][980,1200]"/>'
    '<node class="android.widget.Button" text="OK" '
    'resource-id="com.instagram.android:id/igds_alert_dialog_primary_button" bounds="[100,1250][980,1350]"/>'
    '</node></hierarchy>'
)

_PROFILE_SCREEN = (
    '<hierarchy rotation="0">'
    '<node class="android.widget.FrameLayout" package="com.instagram.android" bounds="[0,0][1080,2400]">'
    '<node class="android.widget.TextView" text="alice" '
    'resource-id="com.instagram.android:id/action_bar_title" bounds="[100,100][500,160]"/>'
    '<node class="android.widget.Button" text="Follow" '
    'resource-id="com.instagram.android:id/profile_header_follow_button" bounds="[40,700][520,780]"/>'
    '</node></hierarchy>'
)


@pytest.fixture(autouse=True)
def _lock_lifted():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


class _Phone:
    """What the detector reads: `blocked()` decides whether the dialog is on screen."""

    def __init__(self, blocked=lambda: False):
        self._blocked = blocked
        self.dumps = 0

    def dump_hierarchy(self, *a, **k):
        self.dumps += 1
        return _BLOCK_DIALOG if self._blocked() else _PROFILE_SCREEN


# ─────────────────────────────────────────────────────────────── the detector sets the lock

def test_seeing_the_dialog_sets_the_lock():
    detector = ProblematicPageDetector(_Phone(blocked=lambda: True))

    assert detector.is_action_blocked() is True
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_an_ordinary_screen_sets_nothing():
    detector = ProblematicPageDetector(_Phone(blocked=lambda: False))

    assert detector.is_action_blocked() is False
    assert run_halt.arret_demande() is None


def test_closing_the_dialog_no_longer_lets_the_run_act_again(monkeypatch):
    """The popup handler closes the dialog, as before -- but the lock is set BEFORE the close,
    so the run stops at its next `should_continue` instead of liking again."""
    detector = ProblematicPageDetector(_Phone(blocked=lambda: True))
    lock_at_close = []

    def _close(page_type, close_methods):
        lock_at_close.append(run_halt.arret_demande())
        return True

    monkeypatch.setattr(detector, "_close_problematic_page", _close)

    result = detector.detect_and_handle_problematic_pages()

    assert result["soft_ban"] is True
    assert lock_at_close and lock_at_close[0]["code"] == run_halt.ACTION_BLOCKED


# ─────────────────────────────────────────────────────────── the session reads it

def test_the_session_names_the_stop_action_blocked():
    session = SessionManager({"session_settings": {"session_duration_minutes": 60}})
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    keep_going, reason = session.should_continue()

    assert keep_going is False
    assert reason.code == "action_blocked"


# ─────────────────────────────────────────────────── the engine stops after a refused write

class _Logger:
    def __init__(self):
        self.lines = []

    def _log(self, *a, **k):
        self.lines.append(str(a[0]) if a else "")

    debug = info = warning = error = _log


class _LikeBusiness:
    def __init__(self, on_like=None):
        self.calls = 0
        self._on_like = on_like

    def like_profile_posts(self, *a, **k):
        self.calls += 1
        if self._on_like:
            self._on_like()
        return {"posts_liked": 1, "posts_commented": 0}


class _ClickActions:
    def __init__(self):
        self.follow_calls = 0

    def follow_user(self, username):
        self.follow_calls += 1
        return True

    def get_follow_button_state(self):
        return "follow"


class _ScrollActions:
    def scroll_to_top(self, *a, **k):
        stop_condition = k.get("stop_condition")
        return bool(stop_condition()) if stop_condition else True


class _DetectionActions:
    def has_unseen_profile_story(self, *a, **k):
        return False


class _Engine(InteractionEngineMixin, ConfigParsingMixin):
    """Real engine and real detector; the phone, the like loop and the follow tap are fakes."""

    def __init__(self, phone, like_business, click_actions):
        self.logger = _Logger()
        self.like_business = like_business
        self.click_actions = click_actions
        self.scroll_actions = _ScrollActions()
        self.detection_actions = _DetectionActions()
        self.nav_actions = types.SimpleNamespace(problematic_page_detector=ProblematicPageDetector(phone))

    def _emit_like_event(self, *a, **k):
        pass

    def _emit_follow_event(self, *a, **k):
        pass

    def _record_action(self, *a, **k):
        pass

    def _handle_follow_suggestions_popup(self):
        pass

    def _recover_from_blocking_modal(self, *a, **k):
        return None


def _cfg():
    return {
        "like_probability": 1.0,
        "follow_probability": 1.0,
        "comment_probability": 0.0,
        "story_probability": 0.0,
        "story_like_probability": 0.0,
        "min_likes_per_profile": 1,
    }


def _follow_first(monkeypatch):
    # The engine draws the follow phase: below 0.35 it runs first, on arrival.
    monkeypatch.setattr(random, "random", lambda: 0.0)


def _follow_last(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.99)


def test_a_refused_follow_ends_the_profile_before_the_likes(monkeypatch):
    _follow_first(monkeypatch)
    clicks = _ClickActions()
    likes = _LikeBusiness()
    engine = _Engine(_Phone(blocked=lambda: clicks.follow_calls > 0), likes, clicks)

    engine._perform_interactions_on_profile("alice", _cfg(), profile_data=None)

    assert clicks.follow_calls == 1
    assert likes.calls == 0
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_a_refused_like_ends_the_profile_before_the_follow(monkeypatch):
    _follow_last(monkeypatch)
    clicks = _ClickActions()
    likes = _LikeBusiness()
    engine = _Engine(_Phone(blocked=lambda: likes.calls > 0), likes, clicks)

    engine._perform_interactions_on_profile("alice", _cfg(), profile_data=None)

    assert likes.calls == 1
    assert clicks.follow_calls == 0
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_without_the_dialog_the_profile_runs_as_before(monkeypatch):
    _follow_last(monkeypatch)
    clicks = _ClickActions()
    likes = _LikeBusiness()
    engine = _Engine(_Phone(blocked=lambda: False), likes, clicks)

    result = engine._perform_interactions_on_profile("alice", _cfg(), profile_data=None)

    assert likes.calls == 1
    assert clicks.follow_calls == 1
    assert result["follows"] == 1
    assert run_halt.arret_demande() is None


def test_the_check_costs_nothing_when_no_follow_was_tapped():
    """`_do_follow` says whether it tapped: an already-followed profile costs no extra dump."""
    clicks = _ClickActions()
    engine = _Engine(_Phone(), _LikeBusiness(), clicks)
    plan = types.SimpleNamespace(do_follow=True)

    tapped = engine._do_follow("alice", plan, {"follow_button_state": "following"}, {"follows": 0})

    assert tapped is False
    assert clicks.follow_calls == 0


# ────────────────────────────────────────────────────────── the feed loop reads the lock

class _Stats:
    def increment(self, *a, **k):
        pass


def _feed(phone, liked):
    feed = object.__new__(FeedBusiness)
    feed.logger = _Logger()
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = None
    feed.automation = None
    feed.stats_manager = _Stats()
    feed.nav_actions = types.SimpleNamespace(
        navigate_to_home=lambda: True,
        problematic_page_detector=ProblematicPageDetector(phone),
    )
    feed.scroll_actions = types.SimpleNamespace(
        human_reading_pause=lambda **k: None,
        scroll_feed_to_next_post=lambda **k: {"on_feed": True},
    )
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: "bob"
    feed.has_feed_suggestions_carousel = lambda: False

    def _like():
        liked.append(1)
        return True

    feed._like_current_post = _like
    return feed


_FEED_RUN = {
    "max_interactions": 5,
    "max_posts_to_check": 5,
    "like_percentage": 100,
    "comment_percentage": 0,
    "view_feed_stories": False,
    "follow_suggestions": False,
    "min_post_likes": 0,
    "max_post_likes": 0,
    "capture_ads": False,
    "interact_with_post_author": False,
    "interact_with_post_likers": False,
}


@pytest.fixture
def _quiet_feed(monkeypatch):
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision", lambda *a, **k: None)


def test_the_feed_stops_on_the_first_refused_like(_quiet_feed):
    liked = []
    feed = _feed(_Phone(blocked=lambda: len(liked) > 0), liked)

    feed.interact_with_feed(dict(_FEED_RUN))

    assert len(liked) == 1
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_the_feed_reads_a_lock_set_elsewhere(_quiet_feed):
    """A lost phone or a block seen during navigation: the feed loop never read the lock."""
    liked = []
    feed = _feed(_Phone(), liked)
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "le telephone ne repond plus")

    feed.interact_with_feed(dict(_FEED_RUN))

    assert liked == []


def test_the_feed_without_the_dialog_likes_as_before(_quiet_feed):
    liked = []
    feed = _feed(_Phone(), liked)

    feed.interact_with_feed(dict(_FEED_RUN))

    assert len(liked) == 5
    assert run_halt.arret_demande() is None
