"""The feed's suggestions carousel is framed whole before its cards are read.

Measured on a Pixel 3a (Instagram 410.0.0.53.71, in English): the Lab's
`suggestions.find_carousel` stopped after one scroll, as soon as the carousel's header showed,
and `suggestions.detect_carousel` then answered "0 card(s)". The dump held both cards and their
names, but their Follow buttons sat below the tab bar, so outside the dump.

The screens are real dumps, anonymized (every text and content-desc emptied except the app's
interface labels, the card names invented, the Android system bars removed):
- `ig410_en_feed_carousel_cut_by_tab_bar.xml`: that very screen, the cards cut by the tab bar;
- `ig410_en_feed_carousel_framed.xml`: a Lab corpus screen of the same phone with the whole
  carousel in view, buttons included; it stands for the screen after the framing scroll;
- `ig410_en_feed_carousel_cut_under_ad.xml`: another phone (576x1280), the carousel cut at the
  bottom under a sponsored post whose header carries a Follow button.

The other cases are BUILT from the framed screen by moving the feed's content and clipping it
the way a dump clips it (`_feed_moved`): the carousel's header under the top edge, a Follow
button half under the tab bar, the "See all" link as a sliver above it.
"""

from pathlib import Path
from types import SimpleNamespace
import logging

import pytest
from lxml import etree

from bridges.compat.diagnostics.actions.instagram.suggestions import (
    detect_carousel,
    find_carousel,
)
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.shared.device.ui_dump import parse_bounds, parse_ui_dump
from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions import (
    FeedSuggestionsMixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions_parsing import (
    parse_feed_suggestions_carousel,
)
from taktik.core.social_media.instagram.ui.selectors import FEED_SUGGESTIONS_SELECTORS

FIXTURES = Path(__file__).parent / "fixtures"
CUT_BY_TAB_BAR = (FIXTURES / "ig410_en_feed_carousel_cut_by_tab_bar.xml").read_text(encoding="utf-8")
FRAMED = (FIXTURES / "ig410_en_feed_carousel_framed.xml").read_text(encoding="utf-8")
CUT_UNDER_AD = (FIXTURES / "ig410_en_feed_carousel_cut_under_ad.xml").read_text(encoding="utf-8")

# The Pixel 3a's feed band: under the status bar, above the tab bar.
BAND = (77, 1967)
PIXEL_3A_HEIGHT = 2220


def _feed_moved(xml: str, dy: int) -> str:
    """The same screen once the feed moved its content ``dy`` px up (down when negative).

    Every node inside the feed list moves, then is clipped to the list's visible band as the dump
    clips it; a node left with no visible pixel is dropped with its subtree, as the dump drops
    what is off screen. Only hiding is faithful: a dump holds nothing of what it did not show.
    """
    root = etree.fromstring(xml.encode("utf-8"))
    feed = next(node for node in root.iter("node")
                if node.get("resource-id") == "android:id/list")
    _, top, _, bottom = parse_bounds(feed.get("bounds"))
    for node in list(feed.iterdescendants("node")):
        left, node_top, right, node_bottom = parse_bounds(node.get("bounds"))
        node_top, node_bottom = max(node_top - dy, top), min(node_bottom - dy, bottom)
        if node_bottom <= node_top:
            node.getparent().remove(node)
            continue
        node.set("bounds", f"[{left},{node_top}][{right},{node_bottom}]")
    return etree.tostring(root, encoding="unicode")


def _carousel(xml):
    return parse_feed_suggestions_carousel(parse_ui_dump(xml), FEED_SUGGESTIONS_SELECTORS)


# --- reading one screen --------------------------------------------------------------------


def test_the_cards_under_the_tab_bar_are_present_but_not_framed():
    carousel = _carousel(CUT_BY_TAB_BAR)

    assert carousel["present"] is True
    assert carousel["cta_bounds"] == (880, 1365, 1036, 1415)
    assert carousel["cards"] == []
    # Not "no card": two cards are there, their buttons under the tab bar.
    assert carousel["cards_status"] == "not_framed"
    framing = carousel["framing"]
    assert framing["framed"] is False
    assert framing["cut"] == "bottom"
    assert framing["cards_hidden"] == 2
    assert tuple(framing["band"]) == BAND
    # Header brought under the top edge with a tenth of the band to spare.
    assert framing["shift_px"] == 1343 - (77 + 189)


def test_the_whole_carousel_is_read_with_its_cards():
    carousel = _carousel(FRAMED)

    assert carousel["framing"]["framed"] is True
    assert carousel["framing"]["shift_px"] == 0
    assert carousel["cards_status"] == "readable"
    assert [card["name"] for card in carousel["cards"]] == ["Mara Quill", "Teo Varnish"]
    assert [card["follow_bounds"] for card in carousel["cards"]] == [
        (72, 1502, 624, 1590), (723, 1502, 1080, 1590),
    ]


def test_an_ad_follow_button_is_never_taken_for_a_card():
    """Cut carousel under a sponsored post: its header's Follow button is no suggestion."""
    carousel = _carousel(CUT_UNDER_AD)

    assert carousel["cards"] == []
    assert carousel["cards_status"] == "not_framed"
    assert carousel["framing"]["cut"] == "bottom"
    assert carousel["framing"]["cards_hidden"] == 2


def test_a_follow_button_clipped_by_the_tab_bar_is_not_a_card():
    # The corpus shows it on the same phone: buttons at [72,1905][624,1967], 62 px of 88.
    clipped = _feed_moved(FRAMED, -(1905 - 1502))

    carousel = _carousel(clipped)

    assert carousel["cards"] == []
    assert carousel["cards_status"] == "not_framed"
    assert carousel["framing"]["cards_clipped"] == 2
    assert carousel["framing"]["cut"] == "bottom"


def test_a_header_above_the_top_edge_asks_to_move_the_feed_down():
    cut_top = _feed_moved(FRAMED, 750)

    framing = _carousel(cut_top)["framing"]

    assert framing["cut"] == "top"
    assert framing["fits"] is True
    assert framing["shift_px"] < 0


def test_a_carousel_without_a_visible_band_is_not_assessed():
    """No feed list and no tab bar in the dump: no proof of where the screen ends."""
    xml = ("<hierarchy><node resource-id='com.instagram.android:id/netego_carousel_container_view'"
           " bounds='[0,1150][1080,1967]'/></hierarchy>")

    assert _carousel(xml)["framing"] is None


# --- the production search, on a phone that answers the gestures ---------------------------


class _Feed:
    """A phone showing ``screens``; each scroll moves on to the next one, the last one stays."""

    def __init__(self, screens):
        self.screens = list(screens)
        self.scrolls = []
        self.taps = []

    @property
    def screen(self):
        return self.screens[0]

    def snapshot(self):
        return ScreenSnapshot(self.screen)

    def dump_hierarchy(self, compressed=False):
        return self.screen

    def get_screen_size(self):
        return 1080, PIXEL_3A_HEIGHT

    def xpath(self, selector):
        return SimpleNamespace(exists=bool(parse_ui_dump(self.screen).xpath(selector)))

    def human_scroll(self, direction="down", distance_ratio=None):
        self.scrolls.append((direction, distance_ratio))
        if len(self.screens) > 1:
            self.screens.pop(0)
        return True

    def human_tap(self, bounds):
        self.taps.append(tuple(bounds))
        return bounds[0], bounds[1]


class _Harness(FeedSuggestionsMixin):
    """The production mixin plus the primitives its host normally provides."""

    def __init__(self, device):
        self.device = device
        self.logger = logging.getLogger("test-carousel-framing")
        self.session_manager = None

    def _human_like_delay(self, action_type="general"):
        return None


def test_the_search_frames_the_carousel_then_reads_its_cards():
    feed = _Feed([CUT_BY_TAB_BAR, FRAMED])
    harness = _Harness(feed)

    search = harness.find_feed_suggestions_carousel(max_scrolls=12)

    assert search["found"] is True
    assert search["scrolls"] == 0
    # One framing scroll, forward, by about the measured shift (the gesture varies it).
    assert len(feed.scrolls) == 1
    direction, ratio = feed.scrolls[0]
    assert direction == "down"
    assert 0.9 * 1077 / PIXEL_3A_HEIGHT <= ratio <= 1.1 * 1077 / PIXEL_3A_HEIGHT
    assert search["framed"] is True
    assert search["framing_scrolls"] == 1
    assert [card["name"] for card in harness.detect_feed_suggestions_carousel()["cards"]] == [
        "Mara Quill", "Teo Varnish",
    ]
    assert feed.taps == []


def test_a_carousel_already_whole_costs_no_gesture():
    feed = _Feed([FRAMED])

    search = _Harness(feed).find_feed_suggestions_carousel(max_scrolls=12)

    assert search["framed"] is True
    assert search["framing_scrolls"] == 0
    assert feed.scrolls == []


def test_the_framing_is_bounded_and_says_it_failed():
    """A screen that does not move: two tries, then the result says why, not "0 card"."""
    feed = _Feed([CUT_BY_TAB_BAR])

    search = _Harness(feed).find_feed_suggestions_carousel(max_scrolls=12)

    assert search["found"] is True
    assert search["framed"] is False
    assert search["framing_scrolls"] == 2
    assert len(feed.scrolls) == 2
    assert search["framing"]["cut"] == "bottom"


def test_a_see_all_sliver_above_the_tab_bar_is_never_tapped():
    sliver = _feed_moved(FRAMED, -(1950 - 787))
    feed = _Feed([sliver])
    harness = _Harness(feed)

    result = harness.run_feed_suggestions_pass({"max_suggestion_follows": 1})

    assert feed.taps == []
    assert result["entered"] is False
    assert result["stop_reason"] == "carousel_not_framed"


def test_a_suggestions_only_run_frames_once_and_says_why_it_stopped():
    """The search frames the carousel; the pass that follows does not spend a second budget."""
    sliver = _feed_moved(FRAMED, -(1950 - 787))
    feed = _Feed([sliver])

    result = _Harness(feed).run_suggestions_only({"max_suggestion_passes": 1,
                                                 "max_carousel_scrolls": 3})

    assert len(feed.scrolls) == 2
    assert result["framing_scrolls"] == 2
    assert result["carousel_framed"] is False
    assert result["stop_reason"] == "carousel_not_framed"
    assert feed.taps == []


# --- the Lab actions call the production and say what they saw -----------------------------


def test_the_lab_tells_cards_not_framed_from_no_card():
    result = detect_carousel(SimpleNamespace(feed=_Harness(_Feed([CUT_BY_TAB_BAR]))), {})

    assert result["found"] is True
    assert result["details"]["cards_status"] == "not_framed"
    assert "NON CADRE" in result["message"]


def test_the_lab_search_reports_a_failed_framing():
    result = find_carousel(SimpleNamespace(feed=_Harness(_Feed([CUT_BY_TAB_BAR]))),
                           {"max_scrolls": 12})

    assert result["success"] is False
    assert result["found"] is True
    assert "NON CADRE" in result["message"]


def test_the_lab_search_reports_the_framing_scroll():
    result = find_carousel(SimpleNamespace(feed=_Harness(_Feed([CUT_BY_TAB_BAR, FRAMED]))),
                           {"max_scrolls": 12})

    assert result["success"] is True
    assert "cadre apres 1 rattrapage" in result["message"]


@pytest.mark.parametrize("xml", [CUT_BY_TAB_BAR, FRAMED, CUT_UNDER_AD],
                         ids=["cut_by_tab_bar", "framed", "cut_under_ad"])
def test_no_card_button_lies_outside_the_carousel(xml):
    carousel = _carousel(xml)
    container = parse_ui_dump(xml).xpath(FEED_SUGGESTIONS_SELECTORS.carousel_container[0])
    left, top, right, bottom = parse_bounds(container[0].get("bounds"))
    for card in carousel["cards"]:
        card_left, card_top, card_right, card_bottom = card["follow_bounds"]
        assert top <= card_top and card_bottom <= bottom
