"""A « Voir les Stories » card in the For You feed of TikTok 47.0.3 is no video: a followed account's
stories, offered in place of one. Never seen on 43.1.4, so the reference names nothing; the 47.0.3
override carries its ids.

The screens are real captures, anonymized: the card (Pixel 6a, TikTok 47.0.3 in French, 2026-09-29,
the Lab auto-test) and every other 47.0.3 screen of these fixtures. Evaluated by uiautomator2's
`d.xpath()` engine, as on the phone.
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_STATE_SELECTORS

FIXTURES = Path(__file__).parent / "fixtures"
CARD = "tt4703_fr_for_you_stories_card.xml"
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


def test_the_reference_names_no_card():
    assert VIDEO_STATE_SELECTORS.stories_card == []
    assert not _card_found(CARD)


@pytest.mark.parametrize("name", SCREENS_4703)
def test_on_47_0_3_the_card_is_found_and_nothing_else(on_47_0_3, name):
    assert _card_found(name) is (name == CARD)
