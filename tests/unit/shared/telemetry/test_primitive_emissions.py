"""The instrumented primitives emit telemetry — verified without a real device.

Keyboard typing/backspace are the easiest choke points to exercise headless
(they only need `run_adb_shell` stubbed). Taps/scrolls need a device facade, so
they're covered by the sink contract + integration runs, not here.
"""

import pytest

from taktik.core.shared import input as _input_pkg  # noqa: F401  (ensure package import)
from taktik.core.shared.input import taktik_keyboard as kb
from taktik.core.shared.telemetry import configure_telemetry_sink, clear_telemetry_sink


@pytest.fixture(autouse=True)
def _sink():
    got = []
    configure_telemetry_sink(got.append)
    yield got
    clear_telemetry_sink()


def test_typing_emits_keystroke_with_length_not_text(monkeypatch, _sink):
    # Simulate a healthy device: keyboard already active, broadcast returns OK.
    monkeypatch.setattr(kb, "is_taktik_keyboard_active", lambda _d: True)
    monkeypatch.setattr(kb, "run_adb_shell", lambda _d, _cmd: "Broadcast completed")
    monkeypatch.setattr(kb.time, "sleep", lambda _s: None)

    assert kb.type_with_taktik_keyboard("dev1", "hello secret", delay_mean=80, delay_deviation=30) is True

    keystrokes = [m for m in _sink if m.category == "keystroke" and m.action == "type"]
    assert len(keystrokes) == 1
    m = keystrokes[0]
    assert m.detail["length"] == len("hello secret")
    # Telemetry must NEVER carry the typed text (passwords/2FA).
    assert "hello secret" not in str(m.detail)
    assert "text" not in m.detail


def test_backspace_emits_count(monkeypatch, _sink):
    monkeypatch.setattr(kb, "run_adb_shell", lambda _d, _cmd: "")
    monkeypatch.setattr(kb.time, "sleep", lambda _s: None)

    assert kb._press_backspace("dev1", 2) is True
    bs = [m for m in _sink if m.category == "keystroke" and m.action == "backspace"]
    assert len(bs) == 1
    assert bs[0].detail["count"] == 2
    assert bs[0].detail["success"] is True


def test_empty_text_does_not_emit(_sink):
    assert kb.type_with_taktik_keyboard("dev1", "") is True
    assert [m for m in _sink if m.category == "keystroke"] == []
