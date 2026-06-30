"""Unit tests for the Instagram account-switch enumeration logic (no device needed).

Covers the pure parts of `InstagramSwitchAccount`: enumerating the connected-account
rows from the picker (filtering the non-account buttons, stripping the trailing
",  New notifications" suffix, de-duplicating) and username normalisation.
"""

from taktik.core.social_media.instagram.auth.switch import InstagramSwitchAccount


class _FakeElement:
    def __init__(self, content_desc):
        self.attrib = {"content-desc": content_desc}


class _FakeXpath:
    def __init__(self, elements):
        self._elements = elements

    def all(self):
        return self._elements


class _FakeDevice:
    """Returns the same fake elements for any xpath query."""

    def __init__(self, elements):
        self._elements = elements

    def xpath(self, _selector):
        return _FakeXpath(self._elements)


def _switcher(elements):
    return InstagramSwitchAccount(_FakeDevice(elements), "device-1")


def test_enumerate_accounts_filters_buttons_and_strips_suffix():
    elements = [
        _FakeElement("sandra.lelit"),
        _FakeElement("erika.spahn,  Nouvelles notifications"),
        _FakeElement("Use another profile"),      # picker button → excluded
        _FakeElement("Créer un compte"),           # picker button → excluded
        _FakeElement("Add account"),               # menu button → excluded
        _FakeElement(""),                          # empty → ignored
        _FakeElement("Some Person Name"),          # has spaces → not a username
        _FakeElement("sandra.lelit"),              # duplicate → collapsed
    ]
    accounts = _switcher(elements)._list_accounts_on_screen()
    assert accounts == ["sandra.lelit", "erika.spahn"]


def test_enumerate_accounts_empty_when_no_rows():
    elements = [_FakeElement("Use another profile"), _FakeElement("Log out")]
    assert _switcher(elements)._list_accounts_on_screen() == []


def test_username_normalisation():
    assert InstagramSwitchAccount._norm("@Sandra.Lelit ") == "sandra.lelit"
    assert InstagramSwitchAccount._norm("  ErIkA.spahn") == "erika.spahn"
    assert InstagramSwitchAccount._norm("") == ""
    assert InstagramSwitchAccount._norm(None) == ""
