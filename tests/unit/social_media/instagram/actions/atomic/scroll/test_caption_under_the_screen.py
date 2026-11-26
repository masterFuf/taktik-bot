"""A caption under the bottom of the screen is looked for before its post is judged.

On a small phone a tall video fills the list: its button row and its caption sit under the bottom.
The reading used to conclude "no caption read" without a gesture, and an account with post terms
then left every such post out (a run on a Pixel 3a: 87 videos drawn for a like, 87 left out).

The screens are the same post of a profile's posts on Instagram 410.0.0.53.71 in English (Pixel 3a,
1080x2220), anonymized, at three heights: framed with its row under the screen, lifted until its
row shows (its caption cut by the bottom), and lifted until the next post is framed (its header
gone, the tail of its caption above the next header). No capture of the corpus shows this caption
once expanded: the reading of the expanded text waits for the phone proof of the lot.
"""

import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as pr
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.shared.filtering.excluded_terms import ExcludedTerms
from taktik.core.contract.shared import POST_CAPTION_UNREAD
from taktik.core.social_media.instagram.actions.base.base_business.term_exclusion import post_verdict
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"

FRAMED = "ig410_en_profile_posts_video_row_below_screen.xml"      # header at 380, nothing under the video
ROW_SHOWN = "ig410_en_profile_posts_video_row_shown.xml"          # header at the top, caption cut by the bottom
NEXT_FRAMED = "ig410_en_profile_posts_next_photo_framed.xml"      # header gone, caption tail above the next post

HEADER_TOP = 380
# Where the header of ROW_SHOWN really is from FRAMED, and a lift that carried it off the screen.
LIFT_TO_ROW = 150
LIFT_PAST_HEADER = 900


def _screen(name: str):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


class _Phone(pr.PostReadingMixin):
    """The three captures as one list: a reading drag lifts the post to the next capture, the way
    back shows the first one again."""

    screen_width = 1080
    screen_height = 2220
    device = None

    def __init__(self):
        self.screens = [_screen(FRAMED), _screen(ROW_SHOWN), _screen(NEXT_FRAMED)]
        self.shown = 0
        self.gestures = []
        self.taps = []
        self.said = []
        phone = self

        class _Device:
            def click_coordinates(self, x, y):
                phone.taps.append((x, y))

        class _Log:
            def debug(self, message, *_a, **_k): phone.said.append(message)
            def warning(self, message, *_a, **_k): phone.said.append(message)

        self.device = _Device()
        self.logger = _Log()

    def _dump_root(self):
        return self.screens[self.shown]

    def _long_drag(self, direction="up", distance_px=None, vel_range=None, guard_start=False,
                   velocity_scale=1.0):
        self.gestures.append(("drag", direction))
        self.shown = min(self.shown + 1, len(self.screens) - 1)
        return True

    def _human_swipe(self, direction="up", distance_px=None, start_band=None, controlled=False,
                     guard_start=False):
        self.gestures.append(("swipe", direction))
        self.shown = 0
        return True


def _identity() -> str:
    return _Phone().framed_post_identity(_screen(FRAMED))


def test_the_framed_video_shows_no_caption_and_its_caption_is_looked_for():
    phone = _Phone()
    context = phone.framed_post_context(_screen(FRAMED))

    assert context["caption_text"] == "" and context["post_ends_on_screen"] is False
    assert context["header_bounds"][1] == HEADER_TOP
    assert phone._caption_is_under_the_screen(context) is True


def test_a_post_seen_whole_or_mostly_under_the_screen_is_not_lifted():
    phone = _Phone()
    context = phone.framed_post_context(_screen(FRAMED))

    assert phone._caption_is_under_the_screen({**context, "post_ends_on_screen": True}) is False
    assert phone._caption_is_under_the_screen({**context, "header_desc": ""}) is False
    low_header = (0, 1500, 1080, 1643)
    assert phone._caption_is_under_the_screen({**context, "header_bounds": low_header}) is False


def test_the_lifted_post_keeps_its_window_while_its_header_shows():
    zone = _Phone()._lifted_post_zone(_screen(ROW_SHOWN), _identity(), HEADER_TOP, LIFT_TO_ROW)

    assert zone["top"] == 231 and zone["closed"] is False
    assert [bounds for bounds, _text in zone["captions"]] == [(33, 2061, 1080, 2088)]


def test_once_its_header_is_gone_the_post_is_what_shows_above_the_next_header():
    zone = _Phone()._lifted_post_zone(_screen(NEXT_FRAMED), _identity(), HEADER_TOP, LIFT_PAST_HEADER)

    # Its caption's tail at the top of the list, never the framed neighbour's caption under it.
    assert (zone["top"], zone["bottom"], zone["closed"]) == (231, 372, True)
    assert [bounds for bounds, _text in zone["captions"]] == [(33, 231, 1080, 276)]


def test_a_header_with_the_posts_description_somewhere_else_is_not_trusted():
    neighbour = _Phone().framed_post_identity(_screen(NEXT_FRAMED))

    # The header at 372 carries the description looked for, but a lift of 900 px from 380 carried
    # the read post's header off the screen: this one is the next post's.
    zone = _Phone()._lifted_post_zone(_screen(NEXT_FRAMED), neighbour, HEADER_TOP, LIFT_PAST_HEADER)

    assert zone is None


def test_the_caption_under_the_screen_is_lifted_expanded_and_the_post_brought_back(monkeypatch):
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    phone = _Phone()

    context = phone.read_framed_caption()

    # Two reading drags: the caption cut by the bottom after the first, its expander on screen
    # after the second, tapped inside the read post's zone (above the next header at 372).
    assert phone.gestures[:2] == [("drag", "up"), ("drag", "up")]
    assert len(phone.taps) == 1
    tap_x, tap_y = phone.taps[0]
    assert 802 <= tap_x <= 893 and 224 <= tap_y <= 270
    # Then the way back, checked on the post's header: the same post, where it sat.
    assert ("swipe", "down") in phone.gestures
    assert phone.shown == 0
    assert context["reframed"] is True
    assert context["header_desc"] == _identity() and context["header_bounds"][1] == HEADER_TOP
    # The text read is the read post's, not the neighbour's.
    assert context["caption_text"].startswith("name_10 ")


def test_a_caption_left_truncated_by_the_reading_still_leaves_the_post_out(monkeypatch):
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)

    # The corpus has no capture of this caption expanded: the tap changes nothing here.
    context = _Phone().read_framed_caption()

    assert post_verdict(context, ExcludedTerms(post_terms=("zorvak",))).reason == POST_CAPTION_UNREAD


def test_a_post_seen_down_to_its_end_without_a_caption_is_a_post_without_caption():
    phone = _Phone()
    context = phone.framed_post_context(_screen(FRAMED))
    terms = ExcludedTerms(post_terms=("zorvak",))

    assert post_verdict({**context, "reframed": True}, terms).reason == POST_CAPTION_UNREAD
    assert post_verdict({**context, "reframed": True, "post_end_seen": True}, terms).reason is None
