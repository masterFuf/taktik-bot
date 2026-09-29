"""Unit tests for the Instagram account-switch enumeration logic (no device needed).

Covers the pure parts of `InstagramSwitchAccount`: enumerating the connected-account
rows from the raw hierarchy XML (filtering the non-account buttons, the profile stats
that leak behind the switcher sheet, and story labels; stripping the trailing
",  New notifications" suffix; de-duplicating) and username normalisation.

Real screens, anonymized, where a phone shows them: the account sheet opened from the own profile
(Instagram 410 in English, Pixel 3a, 2026-09-27: its grab handle "Cancel", one account, then "Add
Instagram account" and "Go to Accounts Center"; the same sheet in French, Pixel 3a, Lab corpus of
June: "Annuler", "Ajouter un compte Instagram", "Accéder à l’Espace Comptes"), the own profiles
it opens from, and the home feed. The sheet carries no "Use another profile": that button is the
logged-out picker's. The logged-out picker and a sheet of several accounts are still written by
hand: no phone of the bench holds several accounts, and the picker needs a log out. The phone that
opens the sheet is uiautomator2's own xpath engine on those screens.
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.instagram.auth.switch import InstagramSwitchAccount
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale

FIXTURES = Path(__file__).parent / "social_media" / "instagram" / "fixtures"
ACCOUNT_SHEET = (FIXTURES / "ig410_en_account_switcher.xml").read_text(encoding="utf-8")
ACCOUNT_SHEET_FR = (FIXTURES / "ig410_fr_account_switcher.xml").read_text(encoding="utf-8")
OWN_PROFILE = (FIXTURES / "ig410_en_own_profile_professional.xml").read_text(encoding="utf-8")
OWN_PROFILE_FR = (FIXTURES / "ig410_fr_own_profile.xml").read_text(encoding="utf-8")
HOME_FEED = (FIXTURES / "ig410_en_home_feed_carousel_post.xml").read_text(encoding="utf-8")

# (own profile, the sheet its @username opens, the language of both)
SHEETS = {
    "410-en": (OWN_PROFILE, ACCOUNT_SHEET, "en"),
    "410-fr": (OWN_PROFILE_FR, ACCOUNT_SHEET_FR, "fr"),
}


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
        "account.one",
        "account.two,  New notifications",
        "Use another profile",   # picker button → excluded
        "Create new account",    # picker button → excluded
        "Add account",           # menu button → excluded
        "Some Person Name",      # has spaces → not a username
        "account.one",          # duplicate → collapsed
    )
    assert switcher._list_accounts_on_screen() == ["account.one", "account.two"]


def test_enumerate_accounts_empty_when_no_rows():
    assert _switcher("Use another profile", "Log out")._list_accounts_on_screen() == []


def test_enumerate_accounts_drops_profile_stats_and_story_labels():
    # The switcher sheet overlays the profile: header stats + story buttons leak into the dump.
    assert "295followers" in OWN_PROFILE and "'s story" in HOME_FEED
    for screen in (OWN_PROFILE, HOME_FEED):
        accounts = InstagramSwitchAccount(_FakeDevice(screen), "device-1")._list_accounts_on_screen()
        assert not [name for name in accounts if name[0].isdigit() or "story" in name.lower()]


def test_enumerate_accounts_no_dump_is_empty():
    class _NoDump:
        pass
    assert InstagramSwitchAccount(_NoDump(), "d")._list_accounts_on_screen() == []


def test_enumerate_accounts_drops_android_navbar_buttons():
    # The status/nav bar (com.android.systemui) leaks "Back"/"Home" ("Retour"/"Accueil") into the
    # dump — they must never count as accounts (device-side: "Accueil" was listed as an account).
    assert 'content-desc="Retour"' in ACCOUNT_SHEET and 'content-desc="Accueil"' in ACCOUNT_SHEET
    accounts = InstagramSwitchAccount(_FakeDevice(ACCOUNT_SHEET), "device-1")._list_accounts_on_screen()
    assert "user_1" in accounts
    assert "Retour" not in accounts and "Accueil" not in accounts


@pytest.mark.parametrize("sheet", [s for _, s, _ in SHEETS.values()], ids=SHEETS.keys())
def test_the_real_account_sheet_lists_its_one_account(sheet):
    """The grab handle of the sheet ("Cancel", "Annuler") is clickable and has no space: not an
    account."""
    accounts = InstagramSwitchAccount(_FakeDevice(sheet), "device-1")._list_accounts_on_screen()
    assert accounts == ["user_1"]


class _Phone:
    """A real screen read by uiautomator2's xpath engine; a tap shows `after_tap`, if given."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2220}

    def __init__(self, screen, after_tap=None):
        self.screen = screen
        self.after_tap = after_tap
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return 1080, 2220

    def click(self, x, y):
        self.taps.append((x, y))
        if self.after_tap is not None:
            self.screen = self.after_tap


@pytest.fixture
def locale():
    before = active_locale()
    yield set_active_locale
    set_active_locale(before)


@pytest.mark.parametrize("known_language", [True, False], ids=["language-detected", "language-unknown"])
@pytest.mark.parametrize("profile, sheet, lang", SHEETS.values(), ids=SHEETS.keys())
def test_tapping_the_username_opens_the_sheet_and_says_so(monkeypatch, locale, profile, sheet, lang,
                                                          known_language):
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    locale(lang if known_language else None)
    phone = _Phone(profile, after_tap=sheet)
    assert InstagramSwitchAccount(phone, "device-1")._open_account_switcher() is True
    assert len(phone.taps) == 1 and phone.screen is sheet


@pytest.mark.parametrize("screen", [OWN_PROFILE, OWN_PROFILE_FR, HOME_FEED], ids=["profile-en", "profile-fr",
                                                                              "home-feed"])
def test_a_screen_without_the_sheet_is_not_an_open_switcher(locale, screen):
    locale(None)
    assert InstagramSwitchAccount(_Phone(screen), "device-1")._switcher_is_open() is False


def test_enumerate_accounts_drops_home_feed_bottom_nav():
    # On the home feed (an account active) the IG bottom-nav tabs are clickable content-desc'd
    # nodes — they must never be listed as accounts (device-side: Reels/Message/Profile leaked).
    assert all(f'content-desc="{tab}"' in HOME_FEED for tab in ("Home", "Reels", "Message", "Profile"))
    accounts = InstagramSwitchAccount(_FakeDevice(HOME_FEED), "device-1")._list_accounts_on_screen()
    assert not {"Home", "Reels", "Message", "Search and explore", "Profile"} & set(accounts)


def test_username_normalisation():
    assert InstagramSwitchAccount._norm("@Account.One ") == "account.one"
    assert InstagramSwitchAccount._norm("  AcCoUnT.two") == "account.two"
    assert InstagramSwitchAccount._norm("") == ""
    assert InstagramSwitchAccount._norm(None) == ""


# --- Active-account detection (home feed → profile → read active @username) ---------------------

def test_detect_active_account_none_when_on_picker(monkeypatch):
    # On the logged-out picker there is no active account → None, and the profile is never read.
    switcher = _switcher()
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: True)
    monkeypatch.setattr(switcher, "_read_profile_username",
                        lambda: (_ for _ in ()).throw(AssertionError("profile must not be read")))
    assert switcher.detect_active_account() is None


def test_detect_active_account_reads_normalises_and_emits(monkeypatch):
    # Logged in: read the profile username, normalise it, emit it (so the front recales the DB).
    emitted = []
    switcher = InstagramSwitchAccount(_FakeDevice(_dump()), "device-1", on_active_account=emitted.append)
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "_read_profile_username", lambda: "@Account.Two")
    assert switcher.detect_active_account() == "account.two"
    assert emitted == ["account.two"]


def test_detect_active_account_rejects_non_handle(monkeypatch):
    # A display name (spaces) or empty read is not a real @handle → None, and nothing is emitted.
    emitted = []
    switcher = InstagramSwitchAccount(_FakeDevice(_dump()), "device-1", on_active_account=emitted.append)
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "_read_profile_username", lambda: "Account One")
    assert switcher.detect_active_account() is None
    assert emitted == []



class _ForegroundDevice(_FakeDevice):
    """A device that also answers which app is on screen, like uiautomator2's `app_current()`."""

    def __init__(self, xml: str, package: str):
        super().__init__(xml)
        self._package = package

    def app_current(self):
        return {"package": self._package, "activity": ".Main"}


def _never(what):
    return lambda *a, **k: (_ for _ in ()).throw(AssertionError(f"{what} must not be read"))


def test_another_app_on_screen_is_not_a_logged_out_account(monkeypatch):
    # Out of Instagram: nothing tapped, nothing read, and said as such (it used to be "logged out?").
    switcher = InstagramSwitchAccount(_ForegroundDevice(_dump(), "com.google.android.apps.nexuslauncher"),
                                      "device-1")
    monkeypatch.setattr(switcher, "_on_account_picker", _never("the picker"))
    monkeypatch.setattr(switcher, "_read_profile_username", _never("the profile"))
    reading = switcher.read_active_account()
    assert (reading.username, reading.reason) == (None, "app_not_foreground")
    assert reading.foreground_package == "com.google.android.apps.nexuslauncher"
    assert switcher.detect_active_account() is None


def test_an_instagram_clone_on_screen_is_instagram(monkeypatch):
    switcher = InstagramSwitchAccount(_ForegroundDevice(_dump(), "com.instagram.androie"), "device-1")
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "_read_profile_username", lambda: "account.two")
    assert switcher.read_active_account().reason == "active"


def test_the_readings_name_why_there_is_no_account(monkeypatch):
    switcher = InstagramSwitchAccount(_ForegroundDevice(_dump(), "com.instagram.android"), "device-1")
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: True)
    assert switcher.read_active_account().reason == "logged_out"
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "_read_profile_username", lambda: None)
    assert switcher.read_active_account().reason == "unreadable"


def _lab_detect_active_account(device):
    import types
    from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    return ACTION_REGISTRY["account.detect_active_account"](
        types.SimpleNamespace(device=device, device_id="device-1"), {})


def test_the_lab_says_instagram_is_not_on_screen_instead_of_logged_out(monkeypatch):
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.InstagramSwitchAccount, "_read_profile_username", _never("the profile"))
    result = _lab_detect_active_account(_ForegroundDevice(_dump(), "com.android.chrome"))
    assert result["success"] is False
    assert "logged out" not in result["message"]
    assert "not in the foreground (com.android.chrome)" in result["message"]
    assert result["details"]["reason"] == "app_not_foreground"


def test_the_lab_still_says_logged_out_on_the_picker(monkeypatch):
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.InstagramSwitchAccount, "_on_account_picker", lambda self: True)
    result = _lab_detect_active_account(_ForegroundDevice(_dump(), "com.instagram.android"))
    assert result["details"]["reason"] == "logged_out"
    assert "logged out" in result["message"]

def test_list_accounts_returns_active_account_when_logged_in(monkeypatch):
    # When an account is active (not on the picker), list_accounts is non-destructive: it reads the
    # active account from the profile and returns just that one (instead of the old empty list).
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher()
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "account.two")
    assert switcher.list_accounts() == ["account.two"]


# --- list_saved_accounts (DESTRUCTIVE: logout -> picker -> enumerate every saved account) --------

def test_list_saved_accounts_enumerates_directly_on_picker(monkeypatch):
    # Already on the picker (logged out) → no logout, just enumerate the saved accounts.
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher("account.one", "account.two,  New notifications", "Use another profile")
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: True)
    assert switcher.list_saved_accounts() == ["account.one", "account.two"]


def test_list_saved_accounts_recales_db_then_logs_out(monkeypatch):
    # An account is active → recale the DB (detect_active_account) BEFORE logging out to the picker.
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher("account.one", "account.two")
    calls = []
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: calls.append("detect"))
    monkeypatch.setattr(switcher, "_logout_to_picker", lambda: calls.append("logout") or True)
    assert switcher.list_saved_accounts() == ["account.one", "account.two"]
    assert calls == ["detect", "logout"]  # DB recaled before the destructive logout


def test_list_saved_accounts_empty_when_picker_unreached(monkeypatch):
    # If the picker can't be reached after logout, return [] (no crash, no bogus accounts).
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher("account.one")
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: None)
    monkeypatch.setattr(switcher, "_logout_to_picker", lambda: False)
    assert switcher.list_saved_accounts() == []
