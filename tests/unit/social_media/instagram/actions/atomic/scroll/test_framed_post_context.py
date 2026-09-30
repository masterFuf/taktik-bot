"""PostReadingMixin.framed_post_context — the framed post's author/date/caption from ONE dump.

Guards the AI comment pipeline's grounding: the caption must come from the SAME post window
as the header that anchors the screenshot crop (a busy frame can show two posts — 11% of the
stored AI comments carried a neighbour's caption), and the header content-desc carries the
author + publish date the model needs to stop congratulating past events.

The screens are real home feeds of Instagram 410.0.0.53.71 in French (Pixel 3a, 1080x2220),
anonymized, read the way production reads a dump (`parse_ui_dump`). On them the neighbour whose
caption is taller is the PREVIOUS post, its caption's tail still at the top of the screen; no
capture of the corpus shows the next post's caption under a second header.
"""

from taktik.core.shared.device.ui_dump import parse_bounds, parse_ui_dump

from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


class _Host(PostReadingMixin):
    screen_height = 2220
    device = object()  # no _device attribute -> JSON-RPC re-read is skipped

    class logger:  # noqa: N801 - minimal stand-in
        @staticmethod
        def debug(_msg):
            return None


def _screen(name: str):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


def _nodes(root, short_id: str) -> list:
    """(bounds, content-desc) of each node with this id, top to bottom."""
    found = [(parse_bounds(n.get("bounds")), n.get("content-desc") or "")
             for n in root.iter() if n.get("resource-id", "").endswith("/" + short_id)]
    return sorted(found, key=lambda item: item[0][1])


def _captions(root) -> list:
    """(bounds, text) of each caption, top to bottom."""
    found = [(parse_bounds(n.get("bounds")), n.get("text"))
             for n in root.iter() if n.tag == FS.caption_layout_class and n.get("text")]
    return sorted(found, key=lambda item: item[0][1])


def _height(bounds) -> int:
    return bounds[3] - bounds[1]


def test_reads_author_date_and_caption_of_framed_post():
    root = _screen("ig410_fr_feed_previous_caption_above_header.xml")
    (header_bounds, header_desc), = _nodes(root, FS.profile_header_id)
    (buttons_bounds, _), = _nodes(root, FS.buttons_row_id)
    own_caption = _captions(root)[-1]

    ctx = _Host().framed_post_context(root)

    assert " a publié " in header_desc
    assert ctx["header_desc"] == header_desc
    assert ctx["author"] == header_desc.split(" ", 1)[0]
    assert own_caption[1].startswith(ctx["author"] + " ")
    assert ctx["caption_text"] == own_caption[1]
    assert ctx["buttons_bounds"] == buttons_bounds


def test_caption_of_a_neighbour_post_is_never_picked():
    # The previous post's caption is taller (the old "tallest on screen" trap) but sits above
    # the framed header — the framed post's window must exclude it.
    root = _screen("ig410_fr_feed_previous_caption_above_header.xml")
    neighbour, own = _captions(root)
    assert _height(neighbour[0]) > _height(own[0])

    ctx = _Host().framed_post_context(root)
    assert ctx["caption_text"] == own[1]


def test_none_when_no_header_is_visible():
    # Mid-scroll: the post's buttons and caption are on screen, its header already gone.
    root = _screen("ig410_fr_feed_post_without_header.xml")
    assert _captions(root) and not _nodes(root, FS.profile_header_id)

    assert _Host().framed_post_context(root) is None


def test_header_above_action_bar_belongs_to_previous_post():
    # A header scrolled up under the action bar is NOT the framed post's header.
    root = _screen("ig410_fr_feed_header_under_action_bar.xml")
    (bar, _), = _nodes(root, FS.action_bar_id)
    (gone, gone_desc), (framed, framed_desc) = _nodes(root, FS.profile_header_id)
    assert gone[1] < bar[3] <= framed[1]

    ctx = _Host().framed_post_context(root)
    assert ctx["author"] == framed_desc.split(" ", 1)[0]
    assert ctx["author"] != gone_desc.split(" ", 1)[0]


def test_missing_buttons_row_reported_as_none():
    # The framed header sits just above the tab bar: its buttons are below the screen, and the
    # buttons and tall caption on screen belong to the post above.
    root = _screen("ig410_fr_feed_caption_with_hashtags.xml")
    assert _nodes(root, FS.buttons_row_id) and _captions(root)

    ctx = _Host().framed_post_context(root)
    assert ctx["buttons_bounds"] is None
    assert ctx["caption_text"] == ""
