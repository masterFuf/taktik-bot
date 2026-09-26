"""The Instagram facade's `press()` must reach the uiautomator2 server in a form the server
presses, and hand back the server's answer.

The server's `pressKey` knows key NAMES ("back", "enter"...) and `pressKeyCode` takes an int. Any
other string is ignored WITHOUT an error and answered False: the facade used to send
"KEYCODE_BACK" and return True, so every Back through it was a silent no-op. The fake server below
models that; a fake that obeys every key would hide the defect.
"""

import ast
import logging
from pathlib import Path

import pytest

import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from taktik.core.social_media.instagram.actions.atomic.text.text_input import TextInputMixin
from taktik.core.social_media.instagram.actions.core.base_business.modal_recovery import ModalRecoveryMixin
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade


class _Uiautomator2Server:
    """A uiautomator2 device as its server answers `press`.

    The name list is written out here, not imported from the facade: a model that copied the
    facade's list would agree with any mistake in it.
    """

    KEY_NAMES = {"home", "back", "left", "right", "up", "down", "center", "menu", "search",
                 "enter", "delete", "del", "recent", "volume_up", "volume_down", "volume_mute",
                 "camera", "power"}

    def __init__(self, answer=True):
        self.received = []   # every key the facade sent
        self.pressed = []    # the keys the server actually pressed
        self.answer = answer  # what the server says once a key is pressed

    def press(self, key, meta=None):
        self.received.append(key)
        if isinstance(key, int) or str(key).lower() in self.KEY_NAMES:
            self.pressed.append(key)
            return self.answer
        return False


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(facade_module.time, "sleep", lambda *_: None)


def _facade(server):
    return DeviceFacade(server)


# ── The key reaches the server as a key it presses ────────────────────────────────────────────

def test_back_reaches_the_server_as_a_name_it_presses():
    server = _Uiautomator2Server()
    assert _facade(server).press("back") is True
    assert server.pressed == ["back"]


def test_back_method_is_a_real_back():
    server = _Uiautomator2Server()
    _facade(server).back()
    assert server.pressed == ["back"]


@pytest.mark.parametrize("key", ["back", "enter", "del", "delete", "BACK", " back "])
def test_the_keys_instagram_code_sends_are_pressed(key):
    server = _Uiautomator2Server()
    assert _facade(server).press(key) is True
    assert len(server.pressed) == 1


def test_an_android_key_code_is_sent_as_is():
    server = _Uiautomator2Server()
    assert _facade(server).press(4) is True
    assert server.pressed == [4]


# ── The answer is the server's ────────────────────────────────────────────────────────────────

def test_the_answer_is_the_servers_not_a_blind_true():
    server = _Uiautomator2Server(answer=False)
    assert _facade(server).press("back") is False
    assert server.pressed == ["back"]


@pytest.mark.parametrize("key", ["ctrl+a", "ctrl+v", "KEYCODE_BACK", "profile", ""])
def test_a_key_the_server_cannot_press_is_not_sent(key):
    server = _Uiautomator2Server()
    assert _facade(server).press(key) is False
    assert server.received == []


def test_a_device_error_answers_false():
    class _Broken:
        def press(self, key, meta=None):
            raise RuntimeError("server gone")

    assert _facade(_Broken()).press("back") is False


# ── A production path through the real facade ────────────────────────────────────────────────

class _XPath:
    def __init__(self, exists):
        self.exists = exists


class _ServerWithModal(_Uiautomator2Server):
    """A blocking sheet that a PRESSED back closes; an ignored key leaves it up."""

    def __init__(self):
        super().__init__()
        self.modal_open = True

    def xpath(self, query):
        return _XPath(self.modal_open)

    def press(self, key, meta=None):
        answer = super().press(key, meta)
        if self.pressed and self.pressed[-1] == "back":
            self.modal_open = False
        return answer


class _Recoverer(ModalRecoveryMixin):
    def __init__(self, device):
        self.device = device
        self.logger = logging.getLogger("test_facade_press")


def test_modal_recovery_through_the_facade_closes_the_modal(monkeypatch):
    import taktik.core.social_media.instagram.actions.core.base_business.modal_recovery as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    server = _ServerWithModal()
    recoverer = _Recoverer(_facade(server))

    assert recoverer._recover_from_blocking_modal("someone", context="test") == "direct_share_sheet"
    assert server.pressed == ["back"]
    assert recoverer._detect_blocking_modal() is None


# ── Clearing a field presses no key ───────────────────────────────────────────────────────────

class _Field(TextInputMixin):
    def __init__(self, device, ime_clears):
        self.device = device
        self.logger = logging.getLogger("test_facade_press")
        self._ime_clears = ime_clears
        self.ime_clear_calls = 0

    def _clear_text_with_taktik_keyboard(self):
        self.ime_clear_calls += 1
        return self._ime_clears


class _ServerWithKeys(_Uiautomator2Server):
    def __init__(self):
        super().__init__()
        self.send_keys_calls = []

    def send_keys(self, text, clear=False):
        self.send_keys_calls.append((text, clear))


def test_clearing_a_field_goes_through_the_keyboard_not_a_lone_delete():
    """Select-all cannot be pressed; a delete on its own would eat the last two characters of a
    restored caption or a pre-filled field."""
    server = _ServerWithKeys()
    field = _Field(_facade(server), ime_clears=True)

    assert field.clear_text_field() is True
    assert field.ime_clear_calls == 1
    assert server.received == []
    assert server.send_keys_calls == []


def test_clearing_falls_back_to_uiautomator2_when_the_keyboard_cannot():
    server = _ServerWithKeys()
    field = _Field(_facade(server), ime_clears=False)

    assert field.clear_text_field() is True
    assert server.received == []
    assert server.send_keys_calls == [("", True)]


# ── Every key literal the Instagram code presses is one the server knows ─────────────────────

_CORE = Path(__file__).resolve().parents[5]
_SCANNED = [
    _CORE / "taktik" / "core" / "social_media" / "instagram",
    _CORE / "bridges" / "instagram",
    _CORE / "bridges" / "compat" / "diagnostics" / "actions" / "instagram",
]
# Key chords the server cannot press, left where they are: each call answers False and the
# caller carries on. Listed per file so a new one elsewhere fails here.
_KNOWN_CHORDS = {
    ("taktik/core/social_media/instagram/actions/atomic/text/keyboard_control.py", "ctrl+a"),
    ("taktik/core/social_media/instagram/actions/atomic/text/keyboard_control.py", "ctrl+v"),
    ("taktik/core/social_media/instagram/auth/login/credentials.py", "ctrl+a"),
}


def _pressed_literals():
    for root in _SCANNED:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "press" and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    yield path.relative_to(_CORE).as_posix(), node.args[0].value, node.lineno


def test_every_pressed_key_literal_is_one_the_server_presses():
    literals = list(_pressed_literals())
    assert literals, "the scan found no press() call: the paths above are wrong"
    unknown = [
        f"{path}:{line} press({key!r})"
        for path, key, line in literals
        if key.strip().lower() not in _Uiautomator2Server.KEY_NAMES
        and (path, key) not in _KNOWN_CHORDS
    ]
    assert unknown == []
