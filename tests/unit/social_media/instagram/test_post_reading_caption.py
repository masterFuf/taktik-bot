"""PostReadingMixin.current_caption_text — the author's caption read from the UI.

Feeds the reading dwell and the AI smart-comment hook (the caption text is sent to the
model alongside the vision description, since the screenshot crop stops at the button row).
"""

from lxml import etree

from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS


class _Host(PostReadingMixin):
    screen_height = 1920


def _root(nodes: str):
    return etree.fromstring(f"<hierarchy>{nodes}</hierarchy>".encode("utf-8"))


def _caption(text: str, top: int, bottom: int) -> str:
    return (f'<node class="{FS.caption_layout_class}" text="{text}" '
            f'bounds="[0,{top}][1080,{bottom}]" />')


def test_returns_dominant_caption_text():
    root = _root(
        _caption("small one", 100, 160)
        + _caption("author_x The real caption with the announcement", 800, 1100)
    )
    assert _Host().current_caption_text(root) == "author_x The real caption with the announcement"


def test_empty_when_no_caption():
    root = _root('<node class="android.widget.Button" text="Like" bounds="[0,0][100,50]" />')
    assert _Host().current_caption_text(root) == ""


def test_offscreen_caption_excluded():
    root = _root(_caption("below the screen", 2000, 2300))
    assert _Host().current_caption_text(root) == ""


def test_prose_length_delegates_and_strips():
    # Username token + hashtags/mentions are not prose; only the sentence counts.
    root = _root(_caption("author_x Nouvelle collection en ligne #mode @brand", 800, 1100))
    host = _Host()
    text = host.current_caption_text(root)
    assert "Nouvelle collection" in text
    assert host._caption_prose_length(root) == len("Nouvelle collection en ligne")
