"""A TikTok counter the screen does not show is unknown (None), never 0.

`extract_profile_from_screen` started from 0 for followers, following and likes and kept it when the
row of counters was not there: the filters then took « 0 followers » for a measure. The screens are
real, TikTok 47.0.3 in French, anonymized: a profile with its row of counters
(`tt4703_fr_profile_followed.xml`) and the home feed between two profiles of a direct run
(`tt4703_fr_direct_home_between_profiles.xml`), where no counter is on screen. They are read the way
`d.xpath()` reads them (`parse_ui_dump`).
"""

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.workflows.common.profile_extractor import extract_profile_from_screen
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


class _Node:
    def __init__(self, node):
        self.text = node.get("text")


class _Query:
    def __init__(self, nodes):
        self._nodes = nodes

    def all(self):
        return [_Node(node) for node in self._nodes]


class _Nothing:
    """The kwargs probes (bio fallback, website): nothing found, as the test does not decide them."""

    exists = False
    count = 0


class _DumpPhone:
    def __init__(self, name):
        self._tree = parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))

    def xpath(self, selector):
        return _Query(self._tree.xpath(selector))

    def __call__(self, **_kwargs):
        return _Nothing()


def test_counters_not_on_screen_are_unknown_not_zero():
    data = extract_profile_from_screen(_DumpPhone("tt4703_fr_direct_home_between_profiles.xml"), "user_1")

    assert (data["followers_count"], data["following_count"], data["likes_count"]) == (None, None, None)


def test_counters_on_screen_are_read():
    data = extract_profile_from_screen(_DumpPhone("tt4703_fr_profile_followed.xml"), "user_1")

    assert all(isinstance(data[key], int) for key in ("followers_count", "following_count", "likes_count")), data
