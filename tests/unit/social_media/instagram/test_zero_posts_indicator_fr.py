"""A profile with no post says "0publications"; one with 60 says "60publications", which
CONTAINS the first. The French entry must answer on the first only."""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors import locales


@pytest.fixture(autouse=True)
def french():
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)


def _profile(stat):
    return (f'<hierarchy><node class="android.widget.LinearLayout" content-desc="{stat}" '
            f'bounds="[0,0][10,10]"/></hierarchy>')


def _hits(xml):
    root = parse_ui_dump(xml)
    return [n for sel in locales.L("profile.zero_posts_indicators") for n in root.xpath(sel)]


@pytest.mark.parametrize("stat", ["0publications", "0 publications"])
def test_a_profile_without_posts_is_found(stat):
    assert _hits(_profile(stat))


@pytest.mark.parametrize("stat", ["60publications", "250 publications", "1 760publications"])
def test_a_count_ending_in_zero_is_not_zero_posts(stat):
    assert not _hits(_profile(stat))
