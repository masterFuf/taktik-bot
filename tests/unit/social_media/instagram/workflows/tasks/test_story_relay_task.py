"""Re-sharing a source account's stories — the first TASK, and what must never drift.

A task is a one-shot: no target list, no live panel, a few seconds of device. The tests
here are mostly about the two things the screen sequence must not decide for itself — the
dedup signature, and what a refusal from Instagram means.

The important one is `unavailable`. Instagram only offers "add to my story" for a story that
mentions us; a missing cell is the product answering no, not a broken selector. If that ever
collapses into a generic failure, the relay silently retries forever and the operator never
learns why nothing is being re-shared.
"""

import pytest

from taktik.core.social_media.instagram.workflows.tasks import story_relay
from taktik.core.social_media.instagram.workflows.tasks.story_relay import (
    _signature,
    relay_source_stories,
)


# ─────────────────────────────────────────────────────────────── signature


def test_the_same_story_read_twice_yields_the_same_signature():
    """Two passes twenty minutes apart see one story: the header has not moved."""
    assert _signature("cindy.dermo", "5 h", 0) == _signature("cindy.dermo", "5 h", 0)


def test_a_later_story_from_the_same_author_is_a_new_signature():
    assert _signature("cindy.dermo", "5 h", 0) != _signature("cindy.dermo", "2 h", 0)


def test_slides_posted_in_the_same_hour_stay_distinct():
    """Three slides posted in one sitting share author AND label. Without the slide index the
    relay would treat slides two and three as already handled and never re-share them."""
    signatures = {_signature("cindy.dermo", "1 h", rank) for rank in (1, 2, 3)}
    assert len(signatures) == 3


def test_an_unreadable_header_produces_no_signature():
    """A signature built on a missing author would collide with every other unreadable
    story, and the journal would mark them all handled after the first one."""
    assert _signature(None, "5 h", 0) is None


# ──────────────────────────────────────────────────────── the relay pass


class _Relay:
    """Stand-in for the screen sequence: records gestures, replays scripted verdicts."""

    def __init__(self, identities, outcomes, opened=True):
        self._identities = list(identities)
        self._outcomes = list(outcomes)
        self._opened = opened
        self.pushes = 0
        self.left_viewer = False

    def open_source_story(self, username):
        return {"opened": self._opened, "reason": None if self._opened else "no_story"}

    def current_story_identity(self):
        return self._identities.pop(0) if self._identities else {"is_open": False}

    def push_current_story_to_mine(self):
        self.pushes += 1
        return self._outcomes.pop(0) if self._outcomes else {"status": "failed", "reason": None}

    def advance_to_next_story(self):
        return bool(self._identities)

    def leave_story_viewer(self):
        self.left_viewer = True
        return True


def _identity(author="cindy.dermo", timestamp="5 h", *, is_ad=False, position=1, total=1):
    return {
        "is_open": True,
        "is_ad": is_ad,
        "author": author,
        "timestamp": timestamp,
        "current_story": position,
        "total_stories": total,
    }


@pytest.fixture
def wired(monkeypatch):
    """Wire the task onto a fake screen and an in-memory journal."""
    handled: set = set()
    recorded: list = []

    def install(relay):
        monkeypatch.setattr(story_relay, "StoryRelayBusiness", lambda *a, **k: relay)
        monkeypatch.setattr(story_relay, "detect_and_optimize", lambda device: "fr")
        monkeypatch.setattr(
            story_relay.ContentRelayService, "already_handled",
            staticmethod(lambda **kw: kw["media_signature"] in handled),
        )
        monkeypatch.setattr(
            story_relay.ContentRelayService, "record",
            staticmethod(lambda **kw: (recorded.append(kw), handled.add(kw["media_signature"]))[0] is None),
        )
        return relay

    install.handled = handled
    install.recorded = recorded
    return install


def test_a_refused_reshare_is_reported_as_unavailable_not_as_a_failure(wired):
    """Instagram withholding the cell is a product answer. Reporting it as a failure would
    hide the one thing the operator needs to know: the source must mention this account."""
    relay = wired(_Relay(
        [_identity()],
        [{"status": "unavailable", "reason": "add_to_story_not_offered"}],
    ))
    report = relay_source_stories(device=object(), source_username="cindy.dermo")

    assert report["unavailable"] == 1
    assert report["failed"] == 0
    assert wired.recorded[0]["status"] == "unavailable"


def test_a_story_already_in_the_journal_is_never_pushed_again(wired):
    """The failure everyone sees: the same story re-shared on every tick."""
    relay = wired(_Relay([_identity()], [{"status": "relayed", "reason": None}]))
    first = relay_source_stories(device=object(), source_username="cindy.dermo")
    assert first["relayed"] == 1

    relay2 = wired(_Relay([_identity()], []))
    second = relay_source_stories(device=object(), source_username="cindy.dermo")
    assert second["already_handled"] == 1
    assert relay2.pushes == 0


def test_a_sponsored_story_is_skipped_without_being_touched(wired):
    """Re-sharing an ad from our own account, and signalling interest to the ranking while
    doing it, is the worst possible outcome of an unattended relay."""
    relay = wired(_Relay(
        [_identity(is_ad=True, position=1, total=2), _identity(position=2, total=2)],
        [{"status": "relayed", "reason": None}],
    ))
    report = relay_source_stories(device=object(), source_username="cindy.dermo")

    assert report["skipped_ads"] == 1
    assert relay.pushes == 1


def test_the_language_is_detected_before_any_localized_selector(monkeypatch):
    """"Add to my story" has no resource-id — only its wording reaches it. Reading a
    localized selector before detection matches nothing, silently."""
    order = []
    monkeypatch.setattr(story_relay, "detect_and_optimize",
                        lambda device: order.append("detect"))

    class _Tracking(_Relay):
        def open_source_story(self, username):
            order.append("open")
            return {"opened": False, "reason": "no_story"}

    monkeypatch.setattr(story_relay, "StoryRelayBusiness", lambda *a, **k: _Tracking([], []))
    relay_source_stories(device=object(), source_username="cindy.dermo")

    assert order == ["detect", "open"]


def test_the_viewer_is_left_even_when_the_pass_blows_up(monkeypatch):
    """A phone abandoned in a fullscreen viewer breaks whatever task runs next."""
    relay = _Relay([], [])

    def _explode(_username):
        raise RuntimeError("device went away")

    relay.open_source_story = _explode
    monkeypatch.setattr(story_relay, "StoryRelayBusiness", lambda *a, **k: relay)
    monkeypatch.setattr(story_relay, "detect_and_optimize", lambda device: "fr")

    report = relay_source_stories(device=object(), source_username="cindy.dermo")

    assert report["success"] is False
    assert "device went away" in report["reason"]
    assert relay.left_viewer is True


def test_a_missing_source_account_is_refused_before_touching_the_phone():
    report = relay_source_stories(device=object(), source_username="")
    assert report["success"] is False
    assert report["reason"] == "no_source_username"
