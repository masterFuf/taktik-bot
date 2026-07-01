"""Unit tests for the Instagram account-switch enumeration logic (no device needed).

Covers the pure parts of `InstagramSwitchAccount`: enumerating the connected-account
rows from the raw hierarchy XML (filtering the non-account buttons, the profile stats
that leak behind the switcher sheet, and story labels; stripping the trailing
",  New notifications" suffix; de-duplicating) and username normalisation.
"""

from taktik.core.social_media.instagram.auth.switch import InstagramSwitchAccount


def _dump(*content_descs: str) -> str:
    """Build a minimal uiautomator hierarchy with one clickable node per content-desc."""
    nodes = "".join(
        f'<node index="0" class="android.view.ViewGroup" clickable="true" content-desc="{d}" />'
        for d in content_descs
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{nodes}</hierarchy>'


class _FakeDevice:
    """Device stub exposing only dump_hierarchy(), like the real uiautomator2 device."""

    def __init__(self, xml: str):
        self._xml = xml

    def dump_hierarchy(self):
        return self._xml


def _switcher(*content_descs: str) -> InstagramSwitchAccount:
    return InstagramSwitchAccount(_FakeDevice(_dump(*content_descs)), "device-1")


def test_enumerate_accounts_filters_buttons_and_strips_suffix():
    switcher = _switcher(
        "sandra.lelit",
        "erika.spahn,  New notifications",
        "Use another profile",   # picker button → excluded
        "Create new account",    # picker button → excluded
        "Add account",           # menu button → excluded
        "Some Person Name",      # has spaces → not a username
        "sandra.lelit",          # duplicate → collapsed
    )
    assert switcher._list_accounts_on_screen() == ["sandra.lelit", "erika.spahn"]


def test_enumerate_accounts_empty_when_no_rows():
    assert _switcher("Use another profile", "Log out")._list_accounts_on_screen() == []


def test_enumerate_accounts_drops_profile_stats_and_story_labels():
    # The switcher sheet overlays the profile: header stats + story buttons leak into the dump.
    switcher = _switcher(
        "sandra.lelit",
        "1posts",
        "36followers",
        "91following",
        "sandra.lelit's story, 0 of 27, Unseen",
        "erika.spahn",
    )
    assert switcher._list_accounts_on_screen() == ["sandra.lelit", "erika.spahn"]


def test_enumerate_accounts_no_dump_is_empty():
    class _NoDump:
        pass
    assert InstagramSwitchAccount(_NoDump(), "d")._list_accounts_on_screen() == []


def test_username_normalisation():
    assert InstagramSwitchAccount._norm("@Sandra.Lelit ") == "sandra.lelit"
    assert InstagramSwitchAccount._norm("  ErIkA.spahn") == "erika.spahn"
    assert InstagramSwitchAccount._norm("") == ""
    assert InstagramSwitchAccount._norm(None) == ""
