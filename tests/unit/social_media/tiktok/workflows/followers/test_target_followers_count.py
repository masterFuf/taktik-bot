"""The Followers workflow reads the target's followers count before opening the list.

The smart scroll sizes its patience on it (`calculate_legacy_followers_scroll_attempts`). The count
was never read: its parser imported `tiktok/core/utils`, a module that does not exist, and the error
went to a debug line; behind it, the reader took the text of the clickable counter, which carries
none (the number is in a child). It now goes through the profile's stats reader, the one the
profile extraction uses on the same screen.

The screen is a real capture: a visited profile, TikTok 43.1.4 in French (Pixel 3a), anonymized,
read by uiautomator2's own `XPathEntry`.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from loguru import logger
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.business.workflows.followers.navigation import NavigationMixin
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS

PROFILE = (Path(__file__).parents[2] / "fixtures" / "tt4314_fr_profile.xml").read_text(encoding="utf-8")


class _Phone:
    """Shows the capture; the xpath queries are uiautomator2's."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def window_size(self):
        return 1080, 2400


class _FollowersRun(NavigationMixin):
    """The mixin as the workflow holds it: its device, its selectors, the tap it delegates."""

    def __init__(self, phone):
        self.device = phone
        self.followers_selectors = FOLLOWERS_SELECTORS
        self.logger = logger
        self.config = SimpleNamespace(search_query="target")
        self._account_id = None
        self._target_followers_count = 0
        self._followers_repository = SimpleNamespace(count_recent_target_interactions=lambda **_: 0)
        self.taps = []
        self.click = SimpleNamespace(_find_and_click=lambda selectors, timeout: self.taps.append(selectors) or True)


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def test_the_followers_count_of_the_target_is_read_before_the_list_opens():
    # What the screen says, read without the production readers: "3,8 M" (a no-break space before
    # the M, as TikTok writes it in French) under the "Followers" label.
    root = etree.fromstring(PROFILE.encode("utf-8"))
    values = [node.get("text") for node in root.iter() if (node.get("resource-id") or "").endswith(":id/qfw")]
    labels = [node.get("text") for node in root.iter() if (node.get("resource-id") or "").endswith(":id/qfv")]
    assert dict(zip(labels, values))["Followers"] == "3,8\u00a0M"

    run = _FollowersRun(_Phone(PROFILE))
    assert run._click_followers_counter() is True

    assert run._target_followers_count == 3_800_000
    assert run.taps == [FOLLOWERS_SELECTORS.followers_counter]
