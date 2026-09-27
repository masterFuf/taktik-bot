"""PostReadingMixin.current_caption_text — the author's caption read from the UI.

Feeds the reading dwell and the AI smart-comment hook (the caption text is sent to the
model alongside the vision description, since the screenshot crop stops at the button row).

The screens are real dumps of Instagram 410.0.0.53.71 in French (Pixel 3a, 1080x2220),
anonymized: a home feed showing the end of one post's caption at the top and the next post's
caption lower down, a feed post whose expanded caption ends with hashtags, and the reel editor,
which shows no caption. They are read the way production reads a dump (`parse_ui_dump`).
"""

from pathlib import Path

from taktik.core.shared.device.ui_dump import parse_bounds, parse_ui_dump

from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS

FIXTURES = Path(__file__).parent / "fixtures"


class _Host(PostReadingMixin):
    screen_height = 2220


def _screen(name: str):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


def _captions(root) -> dict:
    """Each caption of the screen, by its height."""
    captions = {}
    for node in root.iter():
        if node.tag == FS.caption_layout_class and node.get("text"):
            _, top, _, bottom = parse_bounds(node.get("bounds"))
            captions[bottom - top] = node.get("text")
    return captions


def test_returns_dominant_caption_text():
    root = _screen("ig410_fr_feed_two_captions.xml")
    captions = _captions(root)

    assert len(captions) == 2
    assert _Host().current_caption_text(root) == captions[max(captions)]


def test_empty_when_no_caption():
    assert _Host().current_caption_text(_screen("ig410_en_reel_editor.xml")) == ""


def test_offscreen_caption_excluded():
    # uiautomator clips its dump to the screen: no capture of the corpus holds a caption below
    # it. The guard is pure geometry, tested on one node.
    root = parse_ui_dump(
        f'<hierarchy><node class="{FS.caption_layout_class}" text="below the screen" '
        f'bounds="[0,2300][1080,2500]" /></hierarchy>'
    )
    assert _Host().current_caption_text(root) == ""


def test_prose_length_delegates_and_strips():
    # Username token + hashtags are not prose; only the sentence counts.
    root = _screen("ig410_fr_feed_caption_with_hashtags.xml")
    host = _Host()
    text = host.current_caption_text(root)
    sentence, hashtags = text.split(" ", 1)[1].split("\n", 1)

    assert hashtags.startswith("#")
    assert host._caption_prose_length(root) == len(sentence)
