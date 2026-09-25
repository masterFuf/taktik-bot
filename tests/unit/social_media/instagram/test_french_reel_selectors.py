"""Two French entries measured on the 410 corpus: the play control of a paused reel, and the
reel media label the hashtag workflow reads its author from.

On the home feed the same "Reel de" label names the author's DISPLAY name, not the handle; the
hashtag entry must not read it there. The screens below reproduce the structure of the Lab dumps
with invented names.
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.extractors import username_from_media_label
from taktik.core.social_media.instagram.ui.language import filter_selectors
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.ui.selectors.surfaces.hashtag import HASHTAG_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_REELS_SELECTORS,
    POST_SELECTORS,
)

ID = "com.instagram.android:id/"
MEDIA_LABEL = "Reel de demo_author. Appuyez deux fois pour lire ou mettre en pause."


def _reel_viewer(extra=""):
    return f"""<hierarchy>
<node class="android.widget.FrameLayout" resource-id="{ID}clips_viewer_container" bounds="[0,0][1080,2220]">
  <node class="android.view.ViewGroup" resource-id="{ID}clips_media_component"
        content-desc="{MEDIA_LABEL}" bounds="[0,0][1080,2088]">
    <node class="android.widget.FrameLayout" resource-id="{ID}clips_video_container"
          content-desc="{MEDIA_LABEL}" bounds="[0,0][1080,2088]"/>
  </node>
  {extra}
</node>
</hierarchy>"""


PAUSED_REEL = _reel_viewer(
    f'<node class="android.widget.Button" resource-id="{ID}clips_pause_button"'
    ' content-desc="Jouer" bounds="[452,978][628,1154]"/>'
)
PLAYING_REEL = _reel_viewer()


def _list_screen(selected_tab, label):
    return f"""<hierarchy>
<node class="android.widget.FrameLayout" resource-id="{ID}layout_container_main_panel" bounds="[0,0][1080,2220]">
  <node class="android.widget.FrameLayout" resource-id="{ID}row_feed_photo_imageview"
        content-desc="{label}" bounds="[0,400][1080,1500]"/>
  <node class="android.widget.LinearLayout" resource-id="{ID}tab_bar" bounds="[0,1967][1080,2088]">
    <node class="android.widget.FrameLayout" resource-id="{ID}feed_tab" content-desc="Accueil"
          selected="{str(selected_tab == 'feed_tab').lower()}" bounds="[0,1967][216,2088]"/>
    <node class="android.widget.FrameLayout" resource-id="{ID}search_tab" content-desc="Rechercher et explorer"
          selected="{str(selected_tab == 'search_tab').lower()}" bounds="[648,1967][864,2088]"/>
  </node>
</node>
</hierarchy>"""


HOME_FEED = _list_screen("feed_tab", "Reel de Jeanne, 12 J’aime, 3 commentaires, 2 mai")
LIST_FROM_SEARCH = _list_screen("search_tab", "Reel de demo_author, 96 J’aime, 9 commentaires, 9 août")


@pytest.fixture
def french():
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)


def _hits(xml, selectors):
    root = parse_ui_dump(xml)
    return [node for selector in selectors for node in root.xpath(selector)]


# ─────────────────────────────────────────────────── play control

def test_the_play_control_of_a_paused_reel_is_found_in_french(french):
    assert _hits(PAUSED_REEL, POST_SELECTORS.video_controls)
    assert not _hits(PLAYING_REEL, POST_SELECTORS.video_controls)


def test_the_reels_catalogue_keeps_a_french_play_control_once_filtered():
    """`POST_REELS_SELECTORS.video_controls` is a field: the language filter, not `L()`,
    decides what production keeps."""
    kept = filter_selectors(list(POST_REELS_SELECTORS.video_controls), "fr")
    assert _hits(PAUSED_REEL, kept)


# ─────────────────────────────────────────────────── reel author label

def _author(xml):
    nodes = _hits(xml, HASHTAG_SELECTORS.reel_author_container[-1:])
    return username_from_media_label(nodes[0].get("content-desc")) if nodes else None


def test_the_reel_viewer_gives_its_author(french):
    assert _author(PLAYING_REEL) == "demo_author"


def test_the_home_feed_label_is_not_read_as_a_reel_author(french):
    """A one-word display name reads like a handle: "jeanne" would be filed as the author."""
    assert not _hits(HOME_FEED, HASHTAG_SELECTORS.reel_author_container[-1:])
    assert _author(HOME_FEED) is None


def test_the_same_label_outside_the_home_tab_is_still_read(french):
    assert _author(LIST_FROM_SEARCH) == "demo_author"
