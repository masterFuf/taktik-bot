"""`type_text_human` executes a typing plan on the device: type fragments through the
Taktik Keyboard, backspace (DEL keyevent) to correct typos, sleep for think-pauses —
and types the exact string with no typos when `typos=False` (passwords / 2FA / login).
"""

import taktik.core.shared.input.taktik_keyboard as kb


def test_typos_false_types_exact_text_once(monkeypatch):
    calls = []
    monkeypatch.setattr(kb, "type_with_taktik_keyboard",
                        lambda dev, text, dm=80, dd=30: calls.append(text) or True)
    assert kb.type_text_human("dev", "secretPassword", typos=False) is True
    assert calls == ["secretPassword"]  # one burst, exact, no typos


def test_executes_plan_ops_in_order(monkeypatch):
    typed, deleted, slept = [], [], []
    monkeypatch.setattr(kb, "type_with_taktik_keyboard",
                        lambda dev, text, dm=80, dd=30: typed.append(text) or True)
    monkeypatch.setattr(kb, "_press_backspace", lambda dev, n=1: deleted.append(n) or True)
    monkeypatch.setattr(kb.time, "sleep", lambda s: slept.append(s))
    fake_plan = [("type", "hel"), ("type", "p"), ("pause", 0.3), ("backspace", 1), ("type", "lo")]
    monkeypatch.setattr("taktik.core.shared.behavior.typing.build_typing_plan",
                        lambda text, rng=None: fake_plan)

    assert kb.type_text_human("dev", "hello", typos=True) is True
    assert typed == ["hel", "p", "lo"]  # fragments typed in order (typo 'p' then 'lo')
    assert deleted == [1]               # the typo was corrected
    assert 0.3 in slept                 # the think-pause happened


def test_empty_text_is_a_noop(monkeypatch):
    monkeypatch.setattr(kb, "type_with_taktik_keyboard",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not type")))
    assert kb.type_text_human("dev", "", typos=True) is True
