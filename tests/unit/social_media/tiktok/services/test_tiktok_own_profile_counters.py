"""The account's own TikTok profile: a counter the screen does not show is unknown (None), never 0.

`get_own_profile_info` (the start of every TikTok session, `bot_profile`) started from 0 for followers,
following and likes, read an empty value as "0", and paired the row of counters by a loop of its own,
next to `read_profile_stats` that the visited profiles already read with. `TikTokProfileInfo` took 0
as its default too. It reads through `read_profile_stats` now, and keeps None for a counter not read.

Real screens, TikTok in French and English, anonymized: our own profile with its row of counters
(`tt4703_fr_own_profile_not_recommended.xml`, 47.0.3) and a For You video of a guest
(`tt4314_en_for_you_video_guest.xml`, 43.1.4), where a handle is on screen and no row of counters.
"""

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.services.profile.profile_actions import ProfileActions, TikTokProfileInfo
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


class _DumpPhone:
    """A raw device on one real dump: `dump_hierarchy` for the screen photo, `xpath` for the rows."""

    def __init__(self, name):
        self._xml = (FIXTURES / name).read_text(encoding="utf-8")
        self._tree = parse_ui_dump(self._xml)

    def dump_hierarchy(self):
        return self._xml

    def xpath(self, selector):
        return _Query(self._tree.xpath(selector))


def _own_profile(monkeypatch, name):
    # The avatar crop takes a screenshot: none on a dump.
    from taktik.core.social_media.tiktok.actions.atomic.detection import avatar_actions

    monkeypatch.setattr(avatar_actions.AvatarActions, "capture_own_avatar", lambda self: None)
    return ProfileActions(_DumpPhone(name)).get_own_profile_info()


def test_the_counters_of_our_profile_are_read(monkeypatch):
    info = _own_profile(monkeypatch, "tt4703_fr_own_profile_not_recommended.xml")

    assert (info.following_count, info.followers_count, info.likes_count) == (59, 111, 1400)


def test_counters_not_on_screen_are_unknown_not_zero(monkeypatch):
    info = _own_profile(monkeypatch, "tt4314_en_for_you_video_guest.xml")

    assert info is not None
    assert (info.following_count, info.followers_count, info.likes_count) == (None, None, None)


def test_a_profile_built_without_its_counters_has_them_unknown():
    info = TikTokProfileInfo(username="user_1")

    assert (info.following_count, info.followers_count, info.likes_count) == (None, None, None)
    assert info.to_dict()["followers_count"] is None
