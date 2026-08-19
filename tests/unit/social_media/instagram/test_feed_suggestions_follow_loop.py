"""Bulk follow loop from the people discovery screen.

The parsing is locked elsewhere. What is locked here is the GESTURE: which bounds
the finger actually starts from, and what accounting is written. The business rule
— neither follow-back nor follow request from this mode — must hold at tap level,
not only at filter level.

The mixin runs on a minimal harness: a fake device serving canned dumps and
recording the taps, plus the few primitives the mixin expects
de `BaseBusinessAction`.
"""

import logging

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions import (
    FeedSuggestionsMixin,
)


IG = "com.instagram.android:id"


def _row(top, name, button_text):
    bottom = top + 220
    return f"""
      <node resource-id="{IG}/recommended_user_row_content_identifier" bounds="[0,{top}][1080,{bottom}]">
        <node resource-id="{IG}/row_recommended_user_username" text="{name}"
              bounds="[231,{top + 52}][620,{top + 102}]"/>
        <node resource-id="{IG}/row_recommended_social_context" text="1 mutual"
              bounds="[297,{top + 119}][425,{top + 161}]"/>
        <node resource-id="{IG}/row_recommended_user_follow_button" text="{button_text}"
              content-desc="{button_text}" bounds="[653,{top + 66}][959,{top + 154}]"/>
      </node>"""


def _screen(rows):
    body = "".join(_row(top, name, state) for top, name, state in rows)
    return f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>{body}</hierarchy>"


# Screen 1: one follow-back row, one followable row, one already followed.
SCREEN_MIXED = _screen([
    (400, "Known Follower", "Follow back"),
    (620, "Fresh Account", "Follow"),
    (840, "Already Followed", "Following"),
])
# Screen 2: the same, once the followable one was followed and its button flipped.
SCREEN_AFTER_FOLLOW = _screen([
    (400, "Known Follower", "Follow back"),
    (620, "Fresh Account", "Following"),
    (840, "Already Followed", "Following"),
])
EMPTY_SCREEN = "<?xml version='1.0' encoding='UTF-8'?><hierarchy></hierarchy>"


class _FakeDevice:
    """Minimal device: serves the dumps in order, records taps and scrolls."""

    def __init__(self, dumps):
        self._dumps = list(dumps)
        self.taps = []
        self.scrolls = 0

    def dump_hierarchy(self, compressed=False):
        return self._dumps.pop(0) if len(self._dumps) > 1 else self._dumps[0]

    def human_tap(self, bounds):
        self.taps.append(tuple(bounds))
        return (bounds[0], bounds[1])

    def human_scroll(self, direction="down", distance_ratio=None):
        self.scrolls += 1
        return True


class _Harness(FeedSuggestionsMixin):
    """The production mixin plus the primitives its host normally provides."""

    def __init__(self, device):
        self.device = device
        self.logger = logging.getLogger("test-suggestions")
        self.session_manager = None
        self.recorded = []
        self.live_counts = []

    def _human_like_delay(self, action_type="general"):
        return None

    def _human_tap_element(self, element):
        """As in production: false when the bounds are unreadable, and the caller then
        falls back on a centre tap."""
        try:
            element.get(timeout=0.5)
        except Exception:
            return False
        return True

    def _count_live(self, stat_name, value=1):
        self.live_counts.append((stat_name, value))

    def _record_action(self, username, action_type, count=1, timestamps=None, content=None):
        self.recorded.append({"username": username, "action": action_type, "content": content})
        return True


@pytest.fixture
def no_pacing(monkeypatch):
    """Neutralise the human pacing, so the test stays instant."""
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions.time.sleep",
        lambda _s: None,
    )


def test_only_the_plain_follow_row_is_tapped(no_pacing):
    device = _FakeDevice([SCREEN_MIXED, SCREEN_AFTER_FOLLOW])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=1)

    # One single tap, on the bounds of the followable row button.
    assert device.taps == [(653, 686, 959, 774)]
    assert result["follows"] == 1
    # The follow-back row was seen and counted, never tapped.
    assert result["skipped_follow_back"] == 1


def test_a_follow_is_booked_like_the_interaction_engine(no_pacing):
    device = _FakeDevice([SCREEN_MIXED, SCREEN_AFTER_FOLLOW])
    harness = _Harness(device)

    harness.follow_discover_suggestions(max_follows=1, delay_range=(0, 0), max_scrolls=1)

    assert harness.live_counts == [("follows", 1)]
    assert len(harness.recorded) == 1
    entry = harness.recorded[0]
    assert entry["username"] == "Fresh Account"
    assert entry["action"] == "FOLLOW"
    # The provenance is written: without it the row reads as an anonymous follow.
    assert "Suggestion" in (entry["content"] or "")


def test_an_unchanged_button_is_not_counted_as_a_follow(no_pacing):
    """The tap did not take: the row is still offered, so nothing is counted."""
    device = _FakeDevice([SCREEN_MIXED, SCREEN_MIXED])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=1, delay_range=(0, 0), max_scrolls=0)

    assert device.taps, "le bouton a bien ete tape"
    assert result["follows"] == 0
    assert harness.recorded == []
    assert harness.live_counts == []


def test_an_empty_list_stops_instead_of_scrolling_forever(no_pacing):
    device = _FakeDevice([EMPTY_SCREEN])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=30)

    assert result["follows"] == 0
    assert result["stop_reason"] == "list_exhausted"
    # The stop comes from the end of the list, not from the scroll cap.
    assert device.scrolls < 30


def test_a_screen_full_of_follow_backs_keeps_scrolling(no_pacing):
    """A list can stack whole screens of non-followable rows before the next section:
    finding no candidate must not read as the end of the list."""
    only_follow_backs = _screen([(400, "A", "Follow back"), (620, "B", "Follow back")])
    device = _FakeDevice([only_follow_backs])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=4)

    assert result["stop_reason"] == "max_scrolls"
    assert device.scrolls == 4
    assert device.taps == []


FEED_WITH_CAROUSEL = (
    f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
    f"<node resource-id='{IG}/netego_carousel_container_view' bounds='[0,1150][1080,1967]'>"
    f"<node resource-id='{IG}/netego_carousel_cta' text='See all' bounds='[880,1172][1036,1222]'/>"
    f"</node></hierarchy>"
)
FEED_PLAIN = (
    f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
    f"<node resource-id='{IG}/row_feed_button_like' bounds='[33,875][99,1002]'/>"
    f"</hierarchy>"
)


class _XPathDevice(_FakeDevice):
    """Adds the existence check the light carousel probe uses.

    Each scroll advances the current screen, as on a real feed, so the probe only
    sees the carousel after the right number of gestures.
    """

    def human_scroll(self, direction="down", distance_ratio=None):
        if len(self._dumps) > 1:
            self._dumps.pop(0)
        return super().human_scroll(direction, distance_ratio)

    def xpath(self, selector):
        current = self._dumps[0] if self._dumps else ""
        present = "netego_carousel_cta" in selector and "netego_carousel_cta" in current
        return type("_El", (), {"exists": present})()


def test_the_carousel_search_scrolls_without_engaging(no_pacing):
    """Suggestions-only mode: scroll to REACH the block, liking nothing."""
    device = _XPathDevice([FEED_PLAIN, FEED_PLAIN, FEED_WITH_CAROUSEL])
    harness = _Harness(device)

    res = harness.find_feed_suggestions_carousel(max_scrolls=6)

    assert res["found"] is True
    assert res["scrolls"] == 2
    # No tap at all: looking for the carousel engages nothing.
    assert device.taps == []


def test_the_carousel_search_gives_up_on_its_scroll_budget(no_pacing):
    device = _XPathDevice([FEED_PLAIN])
    harness = _Harness(device)

    res = harness.find_feed_suggestions_carousel(max_scrolls=4)

    assert res["found"] is False
    assert res["scrolls"] == 4
    assert device.scrolls == 4


def test_suggestions_only_stops_when_no_carousel_shows_up(no_pacing):
    device = _XPathDevice([FEED_PLAIN])
    harness = _Harness(device)

    res = harness.run_suggestions_only({"max_suggestion_passes": 1, "max_carousel_scrolls": 3})

    assert res["follows"] == 0
    assert res["passes"] == 0
    assert res["stop_reason"] == "carousel_not_found"
    assert device.taps == []


DISCOVER_WITH_BACK_ARROW = (
    f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
    f"<node resource-id='{IG}/action_bar_button_back' content-desc='Back' clickable='true'"
    f" bounds='[0,77][154,231]'/>"
    f"{_row(400, 'Someone', 'Follow back')}"
    f"</hierarchy>"
)


class _BackDevice(_FakeDevice):
    """A discovery screen that IGNORES the back key, like the real one.

    The current screen only changes on a real action: reading the dump does not
    consume it, only a tap on the arrow moves it on.
    """

    def __init__(self, screens, arrow_works=True):
        super().__init__(screens)
        self.arrow_works = arrow_works
        self.back_keys = 0
        self.arrow_taps = 0

    @property
    def screen(self):
        return self._dumps[0]

    def dump_hierarchy(self, compressed=False):
        return self.screen

    def press(self, key):
        self.back_keys += 1  # no effect: the screen does not move
        return True

    def xpath(self, selector):
        device = self

        class _El:
            exists = ("action_bar_button_back" in selector
                      and "action_bar_button_back" in device.screen)

            @staticmethod
            def get(timeout=0.5):
                raise RuntimeError("bounds unreadable")  # forces the centre-tap fallback

            @staticmethod
            def click():
                device.arrow_taps += 1
                if device.arrow_works and len(device._dumps) > 1:
                    device._dumps.pop(0)

        return _El()


class _NavActions:
    def __init__(self):
        self.calls = 0

    def navigate_to_home(self):
        self.calls += 1
        return True


def test_leaving_the_suggestions_screen_uses_the_action_bar_arrow(no_pacing):
    """This screen has no tab bar and ignores the hardware back key.
    The return must go through the action-bar arrow, not the key."""
    device = _BackDevice([DISCOVER_WITH_BACK_ARROW, FEED_PLAIN])
    harness = _Harness(device)
    harness.nav_actions = _NavActions()

    assert harness._return_to_feed() is True
    assert device.arrow_taps == 1
    assert device.back_keys == 0, "la touche back ne doit pas etre le premier essai"
    assert harness.nav_actions.calls == 1


def test_a_stuck_suggestions_screen_is_reported_not_swallowed(no_pacing):
    """When the screen does not close, the run must SAY so rather than believe it came back."""
    device = _BackDevice([DISCOVER_WITH_BACK_ARROW, FEED_PLAIN], arrow_works=False)
    harness = _Harness(device)
    harness.nav_actions = _NavActions()

    assert harness._return_to_feed() is False
    assert harness.nav_actions.calls == 0, "on ne cherche pas l'accueil si on n'a pas quitte l'ecran"


def test_the_session_limit_stops_the_loop(no_pacing):
    class _Session:
        def should_continue(self):
            return False, "Follows limit reached (10/10)"

    device = _FakeDevice([SCREEN_MIXED])
    harness = _Harness(device)
    harness.session_manager = _Session()

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=2)

    assert result["stop_reason"] == "session_limit"
    assert device.taps == []


def test_the_daily_follow_quota_stops_the_loop(no_pacing):
    """Ramp-up guard: the daily follow quota is NOT a session-stop reason, it disables
    its own intent. The interaction engine reads it per profile — a path this mode does
    not walk, so it must read the quota itself."""
    class _Session:
        def should_continue(self):
            return True, ""

        def exhausted_intents(self):
            return {'follow'}

    device = _FakeDevice([SCREEN_MIXED])
    harness = _Harness(device)
    harness.session_manager = _Session()

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=2)

    assert result["stop_reason"] == "session_limit"
    assert device.taps == [], "aucun follow ne part quand le budget du jour est consomme"


def test_a_spent_comment_quota_does_not_block_follows(no_pacing):
    """Only the FOLLOW quota matters here: a spent comment quota must not stop a
    suggestions pass."""
    class _Session:
        def should_continue(self):
            return True, ""

        def exhausted_intents(self):
            return {'comment'}

    device = _FakeDevice([SCREEN_MIXED, SCREEN_AFTER_FOLLOW])
    harness = _Harness(device)
    harness.session_manager = _Session()

    result = harness.follow_discover_suggestions(max_follows=1, delay_range=(0, 0), max_scrolls=1)

    assert result["follows"] == 1
