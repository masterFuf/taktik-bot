"""A « Voir les Stories » card in the For You feed of TikTok is no video: a followed account's stories,
offered in place of one. The feed serves it on 43.1.4 (the button `cei`, in `cej`: the reference)
and on 47.0.3 (the button `d3j`, the card `duq`: the override, which carries the reference's entries
along).

The screens are real captures, anonymized: the card on 43.1.4 (Pixel 3a, French) and on 47.0.3
(Pixel 6a, French), both of the Lab auto-test of 2026-09-29, and every other screen of that version
in these fixtures. Evaluated by uiautomator2's `d.xpath()` engine, as on the phone.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_STATE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
CARD_4314 = "tt4314_fr_for_you_stories_card.xml"
CARD_4703 = "tt4703_fr_for_you_stories_card.xml"
SCREENS_4314 = sorted(path.name for path in FIXTURES.glob("tt4314_*.xml"))
SCREENS_4703 = sorted(path.name for path in FIXTURES.glob("tt4703_*.xml"))


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


@pytest.fixture
def on_47_0_3():
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


def _card_found(name):
    device = _Device((FIXTURES / name).read_text(encoding="utf-8"))
    return any(device.xpath(sel).exists for sel in VIDEO_STATE_SELECTORS.stories_card)


@pytest.mark.parametrize("name", SCREENS_4314)
def test_on_the_reference_the_card_is_found_and_nothing_else(name):
    assert _card_found(name) is (name == CARD_4314)


@pytest.mark.parametrize("name", SCREENS_4703)
def test_on_47_0_3_the_card_is_found_and_nothing_else(on_47_0_3, name):
    assert _card_found(name) is (name == CARD_4703)
