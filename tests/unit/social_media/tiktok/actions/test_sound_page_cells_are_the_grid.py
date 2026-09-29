"""The cells a sound harvest opens are the videos of the sound page, never the sound's own cover.

`SoundActions.collect_sound_users` taps the cells `sound_video_cell` finds, one by one. On TikTok
43.1.4 the page header carries the sound's artwork under the same `:id/cover` id as the grid cells,
first in the tree and not clickable: the harvest tapped it, stayed on the page, took the sound title
(`:id/title`) for the author of a video, and its two Back presses left the sound page. Nobody was
collected, on every sound (Lab auto-test, Pixel 3a, 28/09).

The screen is a real dump of TikTok 43.1.4 in French (Pixel 3a), anonymized
(`scripts/lab/anonymize_dump.py`), read by uiautomator2's own `XPathEntry`, the engine `first_matching`
drives on the phone.
"""

from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_SOUND_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
#: The page of an original sound (61 posts), as `tt.sound.open_page` left it.
SOUND_PAGE = (FIXTURES / "tt4314_fr_sound_page.xml").read_text(encoding="utf-8")

#: The sound's artwork in the page header.
SOUND_COVER = (44, 264, 264, 484)
#: The grid on screen: first row whole, the start of the second.
GRID = [(0, 704, 358, 1181), (361, 704, 719, 1181), (722, 704, 1080, 1181), (0, 1184, 358, 1661)]


class _Phone:
    wait_timeout = 0.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml


def _cells():
    return first_matching(_Phone(SOUND_PAGE), VIDEO_SOUND_SELECTORS.sound_video_cell)


def test_the_first_cell_opened_is_the_first_video_of_the_grid():
    assert _cells()[0].bounds == GRID[0]


def test_the_cells_are_the_grid_and_nothing_else():
    cells = _cells()
    assert [cell.bounds for cell in cells] == GRID
    assert SOUND_COVER not in [cell.bounds for cell in cells]
    # What the app writes on a grid cell, a video or a photo post.
    assert {cell.attrib.get("content-desc") for cell in cells} == {"Vidéo", "Photo"}
