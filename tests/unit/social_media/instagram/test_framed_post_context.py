"""PostReadingMixin.framed_post_context — the framed post's author/date/caption from ONE dump.

Guards the AI comment pipeline's grounding: the caption must come from the SAME post window
as the header that anchors the screenshot crop (a busy frame can show two posts — 11% of the
stored AI comments carried a neighbour's caption), and the header content-desc carries the
author + publish date the model needs to stop congratulating past events.
"""

from lxml import etree

from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS

RID = "com.instagram.android:id/"


class _Host(PostReadingMixin):
    screen_height = 1920
    device = object()  # no _device attribute -> JSON-RPC re-read is skipped

    class logger:  # noqa: N801 - minimal stand-in
        @staticmethod
        def debug(_msg):
            return None


def _root(nodes: str):
    return etree.fromstring(f"<hierarchy>{nodes}</hierarchy>".encode("utf-8"))


def _header(desc: str, top: int, bottom: int) -> str:
    return (f'<node resource-id="{RID}row_feed_profile_header" content-desc="{desc}" '
            f'bounds="[0,{top}][1080,{bottom}]" />')


def _buttons(top: int, bottom: int) -> str:
    return (f'<node resource-id="{RID}row_feed_view_group_buttons" '
            f'bounds="[0,{top}][1080,{bottom}]" />')


def _caption(text: str, top: int, bottom: int) -> str:
    return (f'<node class="{FS.caption_layout_class}" text="{text}" '
            f'bounds="[0,{top}][1080,{bottom}]" />')


def test_reads_author_date_and_caption_of_framed_post():
    root = _root(
        _header("ink.beauty.institut a publié un(e) photo le 16 juillet", 136, 190)
        + _caption("ink.beauty.institut Portes ouvertes samedi", 1400, 1500)
        + _buttons(1550, 1620)
    )
    ctx = _Host().framed_post_context(root)
    assert ctx["author"] == "ink.beauty.institut"
    assert "16 juillet" in ctx["header_desc"]
    assert ctx["caption_text"] == "ink.beauty.institut Portes ouvertes samedi"
    assert ctx["buttons_bounds"] == (0, 1550, 1080, 1620)


def test_caption_of_next_post_is_never_picked():
    # The NEXT post's caption is taller (the old "tallest on screen" trap) but sits below
    # the next header — the framed post's window must exclude it.
    root = _root(
        _header("author_one a publié un(e) photo le 3 mai", 136, 190)
        + _caption("author_one court", 400, 460)
        + _buttons(500, 560)
        + _header("author_two a publié un(e) photo le il y a 2 h", 900, 950)
        + _caption("author_two une très longue légende du post suivant", 1000, 1600)
    )
    ctx = _Host().framed_post_context(root)
    assert ctx["author"] == "author_one"
    assert ctx["caption_text"] == "author_one court"


def test_none_when_no_header_is_visible():
    root = _root(_caption("orphan caption", 400, 800))
    assert _Host().framed_post_context(root) is None


def test_header_above_action_bar_belongs_to_previous_post():
    # A header scrolled up under the action bar is NOT the framed post's header.
    root = _root(
        f'<node resource-id="{RID}main_feed_action_bar" bounds="[0,0][1080,130]" />'
        + _header("gone_author a publié un(e) photo le 1 mai", 40, 90)
        + _header("framed_author a publié un(e) photo le 2 mai", 200, 260)
        + _caption("framed_author la bonne légende", 400, 500)
    )
    ctx = _Host().framed_post_context(root)
    assert ctx["author"] == "framed_author"


def test_missing_buttons_row_reported_as_none():
    root = _root(
        _header("someone a publié un(e) photo le hier", 136, 190)
        + _caption("someone texte", 300, 380)
    )
    ctx = _Host().framed_post_context(root)
    assert ctx["buttons_bounds"] is None
