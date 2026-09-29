"""TikTok 47.0.3: the back arrow of a video opened from a profile's grid is `:id/bs4`.

Seen on a run of target profiles (Pixel 6a, TikTok 47.0.3 in French, three profiles): after the
videos of each profile, `followers.back_button` found nothing on the player, where an `ImageView`
`:id/bs4` described « Retour » sits at the top left; the system back did the job each time, after
the probe, a miss capture and 3.7 to 7 s. The five baseline entries name `b9b` (43.1.4), `bqo`
(46.6.3), `b9c` and a route framed by the tabs of a list, that the player does not have.

In the 47.0.3 captures of the corpus, `bs4` is the back arrow of every screen that has one (a
profile, a list) and the close cross of the comment sheet: tapping it always does what back does.

The screen is the capture of that run, anonymized (`tt4703_fr_video_from_profile_grid.xml`),
evaluated by the `d.xpath()` engine of uiautomator2, as on the phone.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from unit.paths import CORE

FIXTURE = CORE / "tests/unit/social_media/tiktok/fixtures/tt4703_fr_video_from_profile_grid.xml"
BACK_ARROW = (15, 132, 151, 268)


class _Screen:
    wait_timeout = 0.0

    def __init__(self, xml):
        self._xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self._xml


def _tapped(screen, selectors):
    """What `_find_and_click` would tap: the first selector that exists, its first node."""
    for selector in selectors:
        found = screen.xpath(selector)
        if found.exists:
            return found.get(timeout=0)
    return None


@pytest.fixture
def screen():
    return _Screen(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def on_47_0_3():
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


def test_on_47_0_3_the_back_arrow_of_the_player_is_found(screen, on_47_0_3):
    arrow = _tapped(screen, FOLLOWERS_SELECTORS.back_button)

    assert arrow is not None
    assert arrow.attrib["resource-id"].endswith(":id/bs4")
    assert tuple(arrow.bounds) == BACK_ARROW


def test_the_baseline_entries_find_nothing_on_the_47_0_3_player(screen):
    """Why the entry is needed: without it, the system back takes over after the probe."""
    assert _tapped(screen, FOLLOWERS_SELECTORS.back_button) is None


def test_the_baseline_entries_are_carried_along(on_47_0_3):
    """The override replaces the list: the ids of the other versions stay behind the new one."""
    apply_version_overrides("tiktok", "43.1.4")
    baseline = list(FOLLOWERS_SELECTORS.back_button)
    apply_version_overrides("tiktok", "47.0.3")

    assert FOLLOWERS_SELECTORS.back_button[1:] == baseline
