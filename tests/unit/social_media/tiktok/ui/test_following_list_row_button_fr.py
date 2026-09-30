"""T4: the French row button of TikTok's following list is the row's own Button.

The French entry had been framed on a profile header and found none of the 6 to 9 buttons of the
list, so the TikTok unfollow unfollowed nobody on a French phone. A row is avatar, names, then a
clickable Button "Suivis" or, for a mutual, "Ami(e)s" (43.1.4) / "Amis" (47.0.3); the tab titles
("Suivis 6", "Ami(e)s 1") are TextViews.

The screens are captures, anonymized, evaluated by uiautomator2's own `d.xpath()` engine: the own
following list of TikTok 43.1.4 (Pixel 3a) and of 47.0.3 (Pixel 6a), both in French and with a
mutual row (2026-09-27), and the profile of a followed account (47.0.3, 2026-09-26), whose header
holds "Suivis " (trailing space) beside the profile's Button.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.ui.labels import is_friends_button
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from unit.paths import CORE


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


FOLLOWING_LIST = _capture("tt4314_fr_following_list.xml")
FOLLOWING_LIST_47 = _capture("tt4703_fr_following_list.xml")
# The trap the first entry fell into: a FOLLOWED profile's header.
FOLLOWED_PROFILE = _capture("tt4703_fr_profile_followed.xml")


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


def _found(xml):
    device = _Device(xml)
    return [el for sel in FOLLOWERS_SELECTORS.following_or_friends_button for el in device.xpath(sel).all()]


def test_every_row_button_of_the_following_list_is_found():
    labels = [el.attrib.get("text") for el in _found(FOLLOWING_LIST)]
    assert sorted(labels) == ["Ami(e)s", "Suivis", "Suivis", "Suivis", "Suivis"]


def test_a_followed_profile_header_is_not_a_row_button():
    assert 'text="Suivis "' in FOLLOWED_PROFILE
    assert _found(FOLLOWED_PROFILE) == []


def test_the_friends_option_recognises_what_the_selector_finds():
    """`include_friends=False` skips mutual rows by their label: it can only work on the
    Button's own text (the old match returned a container whose text is empty)."""
    labels = [el.attrib.get("text") for el in _found(FOLLOWING_LIST)]
    assert [label for label in labels if is_friends_button(label)] == ["Ami(e)s"]


def test_the_lab_counts_the_row_buttons_the_unfollow_taps():
    """Cartography Lab coverage: `tt.followers.count_anchors` reads the same catalogue field."""
    import types

    from bridges.tools.lab.actions.tiktok import ACTION_REGISTRY, register_actions

    register_actions()
    bundle = types.SimpleNamespace(device=_Device(FOLLOWING_LIST))
    result = ACTION_REGISTRY["tt.followers.count_anchors"](bundle, {})
    assert result["details"]["following_or_friends_button"] == 5


def test_the_mutual_row_of_47_is_found_and_read_as_friends():
    """TikTok 46.9.3 and later write the mutual button « Amis » (43.1.4 and 46.6.3: « Ami(e)s »);
    the tab title « Amis 7 » stays a TextView."""
    labels = [el.attrib.get("text") for el in _found(FOLLOWING_LIST_47)]
    assert sorted(set(labels)) == ["Amis", "Suivis"]
    assert "Amis 7" not in labels
    assert [label for label in labels if is_friends_button(label)] == ["Amis", "Amis"]
