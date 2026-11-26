"""A caption under the bottom of the screen is looked for before its post is judged.

On a small phone a tall video fills the list: its button row and its caption sit under the bottom.
The reading used to conclude "no caption read" without a gesture, and an account with post terms
then left every such post out (a run on a Pixel 3a: 87 videos drawn for a like, 87 left out).

The screens are real, anonymized, read the way production reads a dump (`parse_ui_dump`):

- the reading of one tall video of a profile's posts, Instagram 410.0.0.53.71 in French on a Pixel
  3a (1080x2220), as the phone showed it at each step: framed, lifted (its truncated caption above
  the next post's header), its caption expanded, read on, read, on the way back, back;
- the same post one moment earlier, its header without its description: on the phone a header's
  description comes and goes (there on three dumps, gone on the next four, back after);
- another video of the same kind in English, at three heights (framed, lifted, the next post
  framed), for the zone a lifted post is read in.
"""

import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as pr
from taktik.core.contract.shared import POST_CAPTION_UNREAD, POST_EXCLUDED_TERM
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.shared.filtering.excluded_terms import ExcludedTerms
from taktik.core.social_media.instagram.actions.base.base_business.term_exclusion import post_verdict
from taktik.core.social_media.instagram.ui.caption_hygiene import clean_post_caption
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"

READING = "ig410_fr_profile_posts_tall_video_"
FRAMED = READING + "a_framed.xml"                # header at 341, a sliver of its row at the bottom
LIFTED = READING + "b_lifted.xml"                # row at 1542, truncated caption, the next header at 1859
EXPANDED = READING + "c_expanded.xml"            # the caption expanded, running under the bottom
READING_ON = READING + "d_reading.xml"
READ = READING + "e_read.xml"
WAY_BACK = READING + "f_way_back.xml"
BACK = READING + "g_back.xml"                    # header at 442: 101 px lower than it sat
NO_DESCRIPTION = READING + "header_without_description.xml"   # the framed post, header at 343

EN_FRAMED = "ig410_en_profile_posts_video_row_below_screen.xml"   # header at 380
EN_ROW_SHOWN = "ig410_en_profile_posts_video_row_shown.xml"       # header at the top of the list
EN_NEXT_FRAMED = "ig410_en_profile_posts_next_photo_framed.xml"   # header gone, the next one at 372

HEADER_TOP = 341
EN_HEADER_TOP = 380


def _screen(name: str):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


class _Phone(pr.PostReadingMixin):
    """The reading replayed: each gesture and each tap shows the next capture of the phone."""

    screen_width = 1080
    screen_height = 2220
    device = None

    def __init__(self, names=()):
        self.screens = [_screen(name) for name in names]
        self.shown = 0
        self.gestures = []
        self.taps = []
        self.said = []
        phone = self

        class _Device:
            def click_coordinates(self, x, y):
                phone.taps.append((x, y))
                phone._next()

        class _Log:
            def debug(self, message, *_a, **_k): phone.said.append(message)
            def warning(self, message, *_a, **_k): phone.said.append(message)

        self.device = _Device()
        self.logger = _Log()

    def _next(self):
        self.shown = min(self.shown + 1, len(self.screens) - 1)

    def _dump_root(self):
        return self.screens[self.shown]

    def _long_drag(self, direction="up", distance_px=None, vel_range=None, guard_start=False,
                   velocity_scale=1.0):
        self.gestures.append(("drag", direction))
        self._next()
        return True

    def _human_swipe(self, direction="up", distance_px=None, start_band=None, controlled=False,
                     guard_start=False):
        self.gestures.append(("swipe", direction))
        self._next()
        return True


def _identity(name: str) -> str:
    return _Phone().framed_post_identity(_screen(name))


# --- which post is lifted


def test_the_framed_video_shows_no_caption_and_its_caption_is_looked_for():
    phone = _Phone()
    context = phone.framed_post_context(_screen(FRAMED))

    assert context["caption_text"] == "" and context["post_ends_on_screen"] is False
    assert context["header_bounds"][1] == HEADER_TOP
    assert phone._caption_is_under_the_screen(context) is True


def test_a_header_whose_description_is_gone_does_not_stop_the_reading():
    phone = _Phone()
    context = phone.framed_post_context(_screen(NO_DESCRIPTION))

    assert context["header_desc"] == "" and context["author"]
    assert phone._caption_is_under_the_screen(context) is True


def test_a_post_seen_whole_or_mostly_under_the_screen_is_not_lifted():
    phone = _Phone()
    context = phone.framed_post_context(_screen(FRAMED))

    assert phone._caption_is_under_the_screen({**context, "post_ends_on_screen": True}) is False
    low_header = (0, 1500, 1080, 1643)
    assert phone._caption_is_under_the_screen({**context, "header_bounds": low_header}) is False


# --- where the lifted post shows


def test_the_lifted_post_keeps_its_window_while_its_header_shows():
    zone = _Phone()._lifted_post_zone(_screen(EN_ROW_SHOWN), _identity(EN_FRAMED), EN_HEADER_TOP, 150)

    assert zone["top"] == 231 and zone["closed"] is False and zone["has_row"] is True
    assert [bounds for bounds, _text in zone["captions"]] == [(33, 2061, 1080, 2088)]


def test_once_its_header_is_gone_the_post_is_what_shows_above_the_next_header():
    zone = _Phone()._lifted_post_zone(_screen(EN_NEXT_FRAMED), _identity(EN_FRAMED), EN_HEADER_TOP, 900)

    # Its caption's tail at the top of the list, never the framed neighbour's caption under it.
    assert (zone["top"], zone["bottom"], zone["closed"]) == (231, 372, True)
    assert [bounds for bounds, _text in zone["captions"]] == [(33, 231, 1080, 276)]
    # Its button row left the screen: this zone alone does not say the post has no caption.
    assert zone["has_row"] is False


def test_a_header_where_the_post_should_be_is_its_own_even_without_its_description():
    zone = _Phone()._lifted_post_zone(_screen(NO_DESCRIPTION), _identity(FRAMED), HEADER_TOP, 0)

    assert zone["top"] == 343


def test_a_header_there_that_says_another_post_is_not_read():
    # The next post's header (at 372) sits where a lift of 8 px would have left the read post's.
    zone = _Phone()._lifted_post_zone(_screen(EN_NEXT_FRAMED), _identity(EN_FRAMED), EN_HEADER_TOP, 8)

    assert zone is None


def test_the_posts_description_on_a_header_somewhere_else_is_not_read():
    # Same author, kind and day: the next post carries the description looked for, but a lift of
    # 900 px from 380 carried the read post's header off the screen.
    neighbour = _identity(EN_NEXT_FRAMED)

    zone = _Phone()._lifted_post_zone(_screen(EN_NEXT_FRAMED), neighbour, EN_HEADER_TOP, 900)

    assert zone is None


# --- the reading, as the phone played it


def _read_the_tall_video(monkeypatch):
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    phone = _Phone([FRAMED, LIFTED, EXPANDED, READING_ON, READ, WAY_BACK, BACK])
    return phone, phone.read_framed_caption()


def test_the_caption_under_the_screen_is_lifted_expanded_read_and_the_post_brought_back(monkeypatch):
    phone, context = _read_the_tall_video(monkeypatch)

    # One lift shows the truncated caption, its expander is tapped inside the read post's zone,
    # two reading drags follow the expanded text, two swipes bring the post back.
    assert phone.gestures == [("drag", "up"), ("drag", "up"), ("drag", "up"),
                              ("swipe", "down"), ("swipe", "down")]
    assert len(phone.taps) == 1
    _tap_x, tap_y = phone.taps[0]
    assert 1669 <= tap_y <= 1773, "the tap left the caption of the read post"
    # Back, 101 px lower than it sat: under what a gesture travels, no correction is asked.
    assert context["reframed"] is True
    assert context["header_bounds"][1] == HEADER_TOP + 101
    assert context["header_desc"] == _identity(FRAMED)
    # The caption read is the post's own, whole.
    assert context["post_end_seen"] is True
    assert clean_post_caption(context["caption_text"]).truncated is False
    assert "toutes les cartes" in context["caption_text"]


def test_the_caption_read_under_the_screen_is_what_the_terms_are_checked_on(monkeypatch):
    _phone, context = _read_the_tall_video(monkeypatch)

    found = post_verdict(context, ExcludedTerms(post_terms=("zorvak", "cartes")))
    assert (found.reason, found.term) == (POST_EXCLUDED_TERM, "cartes")
    assert post_verdict(context, ExcludedTerms(post_terms=("zorvak",))).reason is None


def test_a_post_that_does_not_come_back_is_left_out(monkeypatch):
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    # The screen does not follow the way back: the expanded caption stays on it.
    phone = _Phone([FRAMED, LIFTED, EXPANDED, READING_ON, READ])

    context = phone.read_framed_caption()

    assert context["reframed"] is False
    assert post_verdict(context, ExcludedTerms(post_terms=("zorvak",))).reason == POST_CAPTION_UNREAD


# --- the verdict


def test_a_post_seen_down_to_its_end_without_a_caption_is_a_post_without_caption():
    context = _Phone().framed_post_context(_screen(FRAMED))
    terms = ExcludedTerms(post_terms=("zorvak",))

    assert post_verdict({**context, "reframed": True}, terms).reason == POST_CAPTION_UNREAD
    assert post_verdict({**context, "reframed": True, "post_end_seen": True}, terms).reason is None
