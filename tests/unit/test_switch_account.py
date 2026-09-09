"""Unit tests for the Instagram account-switch enumeration logic (no device needed).

Covers the pure parts of `InstagramSwitchAccount`: enumerating the connected-account
rows from the raw hierarchy XML (filtering the non-account buttons, the profile stats
that leak behind the switcher sheet, and story labels; stripping the trailing
",  New notifications" suffix; de-duplicating) and username normalisation.
"""

from taktik.core.social_media.instagram.auth.switch import InstagramSwitchAccount
from taktik.core.social_media.instagram.auth.switch.models import SwitchResult
from taktik.core.social_media.instagram.workflows.management.switch import SwitchAccountWorkflow


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
        self.pressed = []

    def dump_hierarchy(self):
        return self._xml

    def press(self, key):
        self.pressed.append(key)


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
    switcher = _switcher(
        "account.one",
        "1posts",
        "36followers",
        "91following",
        "account.one's story, 0 of 27, Unseen",
        "account.two",
    )
    assert switcher._list_accounts_on_screen() == ["account.one", "account.two"]


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
        '<node class="android.view.ViewGroup" clickable="true" package="com.instagram.android" content-desc="account.one,  New notifications" />'
        '<node class="android.view.ViewGroup" clickable="true" package="com.instagram.android" content-desc="account.two,  New notifications" />'
        '</hierarchy>'
    )
    switcher = InstagramSwitchAccount(_FakeDevice(xml), "device-1")
    assert switcher._list_accounts_on_screen() == ["account.one", "account.two"]


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


def test_switch_to_active_account_is_a_non_destructive_noop(monkeypatch):
    import taktik.core.social_media.instagram.auth.switch as switch_mod

    monkeypatch.setattr(switch_mod.time, "sleep", lambda *_args, **_kwargs: None)
    switcher = _switcher()
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "account.two")
    monkeypatch.setattr(
        switcher._logout,
        "_open_profile_tab",
        lambda: (_ for _ in ()).throw(AssertionError("already-active switch must not log out")),
    )

    result = switcher.switch_to("@Account.Two")

    assert result.success is True
    assert result.already_active is True
    assert result.active_username == "account.two"
    assert result.attempts == 0


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


def _fast_switcher(*content_descs: str, max_attempts: int = 2) -> InstagramSwitchAccount:
    return InstagramSwitchAccount(
        _FakeDevice(_dump(*content_descs)),
        "device-1",
        max_attempts=max_attempts,
        transition_timeout=0,
        sleeper=lambda _seconds: None,
    )


def test_switch_from_picker_succeeds_only_after_active_username_verification(monkeypatch):
    switcher = _fast_switcher("target.account")
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: True)
    monkeypatch.setattr(switcher, "_select_account", lambda _target: True)
    monkeypatch.setattr(switcher, "_password_required", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "target.account")

    result = switcher.switch_to("@Target.Account")

    assert result.success is True
    assert result.active_username == "target.account"
    assert result.attempts == 1


def test_switch_reports_expired_session_as_failure(monkeypatch):
    switcher = _fast_switcher("target.account")
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: True)
    monkeypatch.setattr(switcher, "_select_account", lambda _target: True)
    monkeypatch.setattr(switcher, "_password_required", lambda: True)

    result = switcher.switch_to("target.account")

    assert result.success is False
    assert result.error_type == "session_expired"
    assert result.relogin_required is True
    assert result.failure_stage == "verify"
    assert result.attempts == 1


def test_switch_missing_target_closes_native_switcher_and_keeps_prior_account(monkeypatch):
    switcher = _fast_switcher("current.account")
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "current.account")
    monkeypatch.setattr(switcher, "_open_account_switcher", lambda: True)
    monkeypatch.setattr(switcher, "_switcher_is_open", lambda: True)
    monkeypatch.setattr(
        switcher._logout,
        "_open_profile_tab",
        lambda: (_ for _ in ()).throw(AssertionError("native switcher must be used first")),
    )

    result = switcher.switch_to("missing.account")

    assert result.success is False
    assert result.error_type == "target_not_connected"
    assert result.active_username == "current.account"
    assert result.state_known is True
    assert switcher.device.pressed == ["back"]


def test_logout_fallback_restores_previous_account_when_target_is_missing(monkeypatch):
    switcher = _fast_switcher("current.account")
    picker = False
    selections = []

    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: picker)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "current.account")
    monkeypatch.setattr(switcher, "_open_account_switcher", lambda: False)
    monkeypatch.setattr(switcher._logout, "_open_profile_tab", lambda: True)
    monkeypatch.setattr(switcher._logout, "_open_options_menu", lambda: True)
    monkeypatch.setattr(switcher._logout, "_find_and_click_logout", lambda: True)
    monkeypatch.setattr(switcher._logout, "_confirm_logout", lambda: True)

    def reach_picker():
        nonlocal picker
        picker = True
        return True

    monkeypatch.setattr(switcher, "_ensure_on_picker", reach_picker)
    monkeypatch.setattr(
        switcher,
        "_select_account",
        lambda target: selections.append(target) or target == "current.account",
    )
    monkeypatch.setattr(
        switcher,
        "_wait_for_selected_account",
        lambda target: ("verified", target),
    )

    result = switcher.switch_to("missing.account")

    assert result.success is False
    assert result.error_type == "target_not_connected"
    assert result.previous_username == "current.account"
    assert result.active_username == "current.account"
    assert result.state_known is True
    assert selections == ["current.account"]


def test_verification_failure_does_not_report_stale_previous_account_as_active(monkeypatch):
    switcher = _fast_switcher("target.account", max_attempts=1)
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "current.account")
    monkeypatch.setattr(switcher, "_open_account_switcher", lambda: True)
    monkeypatch.setattr(switcher, "_select_account", lambda _target: True)
    monkeypatch.setattr(
        switcher,
        "_wait_for_selected_account",
        lambda _target: ("verification_failed", None),
    )
    monkeypatch.setattr(switcher, "_on_account_picker", lambda: False)

    result = switcher.switch_to("target.account")

    assert result.success is False
    assert result.error_type == "verification_failed"
    assert result.previous_username == "current.account"
    assert result.active_username is None
    assert result.state_known is False


def test_switch_rejects_duplicate_target_rows_as_ambiguous(monkeypatch):
    switcher = _fast_switcher("target.account", "@TARGET.ACCOUNT")
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: True)
    monkeypatch.setattr(
        switcher,
        "_select_account",
        lambda _target: (_ for _ in ()).throw(AssertionError("ambiguous target must not be tapped")),
    )

    result = switcher.switch_to("target.account")

    assert result.success is False
    assert result.error_type == "ambiguous_target"
    assert result.failure_stage == "lookup"


def test_logout_fallback_restores_previous_account_when_target_is_ambiguous(monkeypatch):
    switcher = _fast_switcher("current.account", "target.account", "@TARGET.ACCOUNT")
    picker = False
    selections = []
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: picker)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "current.account")
    monkeypatch.setattr(switcher, "_open_account_switcher", lambda: False)
    monkeypatch.setattr(switcher._logout, "_open_profile_tab", lambda: True)
    monkeypatch.setattr(switcher._logout, "_open_options_menu", lambda: True)
    monkeypatch.setattr(switcher._logout, "_find_and_click_logout", lambda: True)
    monkeypatch.setattr(switcher._logout, "_confirm_logout", lambda: True)

    def reach_picker():
        nonlocal picker
        picker = True
        return True

    monkeypatch.setattr(switcher, "_ensure_on_picker", reach_picker)
    monkeypatch.setattr(
        switcher,
        "_select_account",
        lambda target: selections.append(target) or target == "current.account",
    )
    monkeypatch.setattr(
        switcher,
        "_wait_for_selected_account",
        lambda target: ("verified", target),
    )

    result = switcher.switch_to("target.account")

    assert result.success is False
    assert result.error_type == "ambiguous_target"
    assert result.active_username == "current.account"
    assert result.state_known is True
    assert selections == ["current.account"]


def test_switch_retries_selector_miss_and_succeeds_on_second_attempt(monkeypatch):
    switcher = _fast_switcher("target.account")
    outcomes = iter([False, True])
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: True)
    monkeypatch.setattr(switcher, "_select_account", lambda _target: next(outcomes))
    monkeypatch.setattr(switcher, "_password_required", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "target.account")

    result = switcher.switch_to("target.account")

    assert result.success is True
    assert result.attempts == 2


def test_switch_reports_selector_failure_after_all_retries(monkeypatch):
    switcher = _fast_switcher("target.account", max_attempts=2)
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: True)
    monkeypatch.setattr(switcher, "_select_account", lambda _target: False)

    result = switcher.switch_to("target.account")

    assert result.success is False
    assert result.error_type == "select_failed"
    assert result.failure_category == "selector_not_found"
    assert result.failure_stage == "select"
    assert result.attempts == 2


def test_switch_reports_verification_failure_after_all_retries(monkeypatch):
    switcher = _fast_switcher("target.account", max_attempts=2)
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: True)
    monkeypatch.setattr(switcher, "_select_account", lambda _target: True)
    monkeypatch.setattr(switcher, "_password_required", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "wrong.account")

    result = switcher.switch_to("target.account")

    assert result.success is False
    assert result.error_type == "verification_failed"
    assert result.active_username == "wrong.account"
    assert result.failure_stage == "verify"
    assert result.attempts == 2


def test_switch_workflow_preserves_legacy_keys_and_adds_diagnostics():
    workflow = SwitchAccountWorkflow(_FakeDevice(_dump()), "device-1")
    workflow.switch_manager = type(
        "Manager",
        (),
        {
            "switch_to": lambda self, target: SwitchResult(
                False,
                "not verified",
                "verification_failed",
                requested_username=target,
                active_username="previous.account",
                attempts=2,
                failure_stage="verify",
                failure_category="switch_verification_failed",
                state_known=True,
            )
        },
    )()

    result = workflow.execute("target.account")

    assert result["success"] is False
    assert result["switched_to"] is None
    assert result["relogin_required"] is False
    assert result["requested_username"] == "target.account"
    assert result["active_username"] == "previous.account"
    assert result["attempts"] == 2
    assert result["failure_stage"] == "verify"
    assert result["failure_category"] == "switch_verification_failed"
    assert result["state_known"] is True
