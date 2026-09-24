"""L12 (H1): the phone's keyboard is remembered before the first switch and given back."""

import pytest

from taktik.core.shared.input import taktik_keyboard as kb

ADB = kb.TAKTIK_KEYBOARD_IME
SAMSUNG = "com.samsung.android.honeyboard/.service.HoneyBoardService"


class FakeAdb:
    """`run_adb_shell`, answering like a phone whose default keyboard is `default`."""

    def __init__(self, default, enabled=(kb.GBOARD_IME, ADB)):
        self.default = default
        self.enabled = list(enabled)
        self.commands = []

    def __call__(self, device_id, command):
        self.commands.append(command)
        if command == "settings get secure default_input_method":
            return self.default or "null"
        if command == "ime list -s":
            return "\n".join(self.enabled)
        if command.startswith("ime set "):
            self.default = command[len("ime set "):]
            return f"Input method {self.default} selected for user 0"
        return ""


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(kb, "_original_ime", {})
    monkeypatch.setattr(kb, "_active_ime_cache", {})
    monkeypatch.setattr(kb, "_atexit_registered", True)   # no real atexit hook from tests
    yield


def test_the_phone_gets_its_own_keyboard_back(monkeypatch):
    adb = FakeAdb(default=SAMSUNG, enabled=(SAMSUNG, ADB))
    monkeypatch.setattr(kb, "run_adb_shell", adb)

    assert kb.activate_taktik_keyboard("phone") is True and adb.default == ADB
    assert kb.restore_original_keyboard("phone") is True
    assert adb.default == SAMSUNG


def test_the_original_is_read_before_the_first_switch_only(monkeypatch):
    adb = FakeAdb(default=SAMSUNG, enabled=(SAMSUNG, ADB))
    monkeypatch.setattr(kb, "run_adb_shell", adb)
    kb.activate_taktik_keyboard("phone")
    kb.activate_taktik_keyboard("phone")    # already ADB now: must not become "the original"
    kb.restore_original_keyboard("phone")
    assert adb.default == SAMSUNG


def test_a_phone_whose_keyboard_was_already_the_adb_one_gets_gboard(monkeypatch):
    adb = FakeAdb(default=ADB)
    monkeypatch.setattr(kb, "run_adb_shell", adb)
    kb.activate_taktik_keyboard("pixel")
    assert kb.restore_original_keyboard("pixel") is True
    assert adb.default == kb.GBOARD_IME


def test_without_gboard_the_first_other_enabled_keyboard(monkeypatch):
    adb = FakeAdb(default=ADB, enabled=(ADB, SAMSUNG))
    monkeypatch.setattr(kb, "run_adb_shell", adb)
    kb.activate_taktik_keyboard("phone")
    kb.restore_original_keyboard("phone")
    assert adb.default == SAMSUNG


def test_a_phone_never_switched_is_left_alone(monkeypatch):
    adb = FakeAdb(default=SAMSUNG)
    monkeypatch.setattr(kb, "run_adb_shell", adb)
    assert kb.restore_original_keyboard("phone") is False
    assert adb.commands == []


def test_the_restore_happens_once(monkeypatch):
    adb = FakeAdb(default=SAMSUNG, enabled=(SAMSUNG, ADB))
    monkeypatch.setattr(kb, "run_adb_shell", adb)
    kb.activate_taktik_keyboard("phone")
    assert kb.restore_all_keyboards() == 1
    assert kb.restore_all_keyboards() == 0


def test_the_first_switch_registers_the_exit_hook(monkeypatch):
    adb = FakeAdb(default=SAMSUNG, enabled=(SAMSUNG, ADB))
    monkeypatch.setattr(kb, "run_adb_shell", adb)
    monkeypatch.setattr(kb, "_atexit_registered", False)
    hooks = []
    monkeypatch.setattr(kb.atexit, "register", hooks.append)
    kb.activate_taktik_keyboard("phone")
    kb.activate_taktik_keyboard("other")
    assert hooks == [kb.restore_all_keyboards]


def test_the_instagram_typing_path_switches_through_the_shared_owner(monkeypatch):
    from taktik.core.social_media.instagram.actions.core.base_action.typing import TypingMixin

    adb = FakeAdb(default=SAMSUNG, enabled=(SAMSUNG, ADB))
    monkeypatch.setattr(kb, "run_adb_shell", adb)

    class Typist(TypingMixin):
        logger = kb.logger

        def _get_device_serial(self):
            return "phone"

    assert Typist()._activate_taktik_keyboard() is True
    assert kb._original_ime == {"phone": SAMSUNG}


# ── Review of 2026-09-24 ────────────────────────────────────────────────────────

def test_a_phone_already_on_the_adb_keyboard_is_remembered_at_the_first_check(monkeypatch):
    """The Pixels: every typing path checks first and skips the switch, since ADB is active."""
    adb = FakeAdb(default=ADB)
    monkeypatch.setattr(kb, "run_adb_shell", adb)

    assert kb.is_taktik_keyboard_active("pixel") is True
    assert kb.restore_original_keyboard("pixel") is True
    assert adb.default == kb.GBOARD_IME
    assert adb.commands.count("settings get secure default_input_method") == 1


def test_uiautomator2_s_own_keyboard_is_never_given_back(monkeypatch):
    adb = FakeAdb(default=kb.UIAUTOMATOR_IME, enabled=(kb.UIAUTOMATOR_IME, ADB, SAMSUNG))
    monkeypatch.setattr(kb, "run_adb_shell", adb)
    kb.is_taktik_keyboard_active("phone")
    kb.restore_original_keyboard("phone")
    assert adb.default == SAMSUNG


def test_the_instagram_typing_check_goes_through_the_shared_owner(monkeypatch):
    from taktik.core.social_media.instagram.actions.core.base_action.typing import TypingMixin

    adb = FakeAdb(default=SAMSUNG, enabled=(SAMSUNG, ADB))
    monkeypatch.setattr(kb, "run_adb_shell", adb)

    class Typist(TypingMixin):
        logger = kb.logger

        def _get_device_serial(self):
            return "phone"

    assert Typist()._is_taktik_keyboard_active() is False
    assert kb._original_ime == {"phone": SAMSUNG}
