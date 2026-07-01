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


def test_enumerate_accounts_drops_android_navbar_buttons():
    # The status/nav bar (com.android.systemui) leaks "Back"/"Home" ("Retour"/"Accueil") into the
    # dump — they must never count as accounts (device-side: "Accueil" was listed as an account).
    xml = (
        '<hierarchy rotation="0">'
        '<node class="android.widget.ImageView" clickable="true" package="com.android.systemui" content-desc="Retour" />'
        '<node class="android.widget.ImageView" clickable="true" package="com.android.systemui" content-desc="Accueil" />'
        '<node class="android.view.ViewGroup" clickable="true" package="com.instagram.android" content-desc="sandra.lelit,  New notifications" />'
        '<node class="android.view.ViewGroup" clickable="true" package="com.instagram.android" content-desc="erika.spahn,  New notifications" />'
        '</hierarchy>'
    )
    switcher = InstagramSwitchAccount(_FakeDevice(xml), "device-1")
    assert switcher._list_accounts_on_screen() == ["sandra.lelit", "erika.spahn"]


def test_enumerate_accounts_drops_home_feed_bottom_nav():
    # On the home feed (an account active) the IG bottom-nav tabs are clickable content-desc'd
    # nodes — they must never be listed as accounts (device-side: Reels/Message/Profile leaked).
    switcher = _switcher(
        "Home", "Reels", "Message", "Search and explore", "Profile",
        "the_mermaid_tavern_metz",  # a post author — has no ",  New notifications" but is a handle
    )
    accounts = switcher._list_accounts_on_screen()
    assert "Reels" not in accounts and "Message" not in accounts and "Profile" not in accounts


def test_username_normalisation():
    assert InstagramSwitchAccount._norm("@Sandra.Lelit ") == "sandra.lelit"
    assert InstagramSwitchAccount._norm("  ErIkA.spahn") == "erika.spahn"
    assert InstagramSwitchAccount._norm("") == ""
    assert InstagramSwitchAccount._norm(None) == ""


# --- Active-account detection (Kevin's flow: home feed → profile → read active @username) --------

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
    monkeypatch.setattr(switcher, "_read_profile_username", lambda: "@Erika.Spahn")
    assert switcher.detect_active_account() == "erika.spahn"
    assert emitted == ["erika.spahn"]


def test_detect_active_account_rejects_non_handle(monkeypatch):
    # A display name (spaces) or empty read is not a real @handle → None, and nothing is emitted.
    emitted = []
    switcher = InstagramSwitchAccount(_FakeDevice(_dump()), "device-1", on_active_account=emitted.append)
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "_read_profile_username", lambda: "Sandra Lelit")
    assert switcher.detect_active_account() is None
    assert emitted == []


def test_list_accounts_returns_active_account_when_logged_in(monkeypatch):
    # When an account is active (not on the picker), list_accounts is non-destructive: it reads the
    # active account from the profile and returns just that one (instead of the old empty list).
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher()
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "erika.spahn")
    assert switcher.list_accounts() == ["erika.spahn"]


# --- list_saved_accounts (DESTRUCTIVE: logout -> picker -> enumerate every saved account) --------

def test_list_saved_accounts_enumerates_directly_on_picker(monkeypatch):
    # Already on the picker (logged out) → no logout, just enumerate the saved accounts.
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher("sandra.lelit", "erika.spahn,  New notifications", "Use another profile")
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: True)
    assert switcher.list_saved_accounts() == ["sandra.lelit", "erika.spahn"]


def test_list_saved_accounts_recales_db_then_logs_out(monkeypatch):
    # An account is active → recale the DB (detect_active_account) BEFORE logging out to the picker.
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher("sandra.lelit", "erika.spahn")
    calls = []
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: calls.append("detect"))
    monkeypatch.setattr(switcher, "_logout_to_picker", lambda: calls.append("logout") or True)
    assert switcher.list_saved_accounts() == ["sandra.lelit", "erika.spahn"]
    assert calls == ["detect", "logout"]  # DB recaled before the destructive logout


def test_list_saved_accounts_empty_when_picker_unreached(monkeypatch):
    # If the picker can't be reached after logout, return [] (no crash, no bogus accounts).
    import taktik.core.social_media.instagram.auth.switch as switch_mod
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *a, **k: None)
    switcher = _switcher("sandra.lelit")
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: None)
    monkeypatch.setattr(switcher, "_logout_to_picker", lambda: False)
    assert switcher.list_saved_accounts() == []
