"""Human typing plan: a person doesn't type a clean string in one burst — they
occasionally hit an adjacent key and correct it, and pause to think (after a sentence,
before a word). The plan encodes that as type / backspace / pause ops; crucially,
applying the ops always reproduces the *exact* target text (every typo is corrected).

Part of P2 (typing) — `internal docs`. Pure and
offline-testable; the device execution lives in `shared/input/taktik_keyboard.py`.
"""

import random

from taktik.core.shared.behavior.typing import build_typing_plan, render_plan


TEXTS = [
    "hello world",
    "Salut, ça va bien aujourd'hui ?",
    "Trop beau ce shoot ! J'adore vraiment le rendu.",
    "amazing content keep it up",
    "Merci beaucoup. A bientot !",
    "1234 #hashtag @mention http://x.co",
    "a",
    "",
]


def test_plan_always_renders_to_the_exact_text():
    rng = random.Random(7)
    for text in TEXTS:
        for _ in range(50):
            plan = build_typing_plan(text, rng=rng)
            assert render_plan(plan) == text, (text, plan)


def test_typos_produce_backspaces_but_still_correct_text():
    rng = random.Random(1)
    text = "abcdefghij klmnop qrstuv"
    plan = build_typing_plan(text, rng=rng, typo_prob=1.0)  # force a typo on every letter
    assert any(op[0] == "backspace" for op in plan)  # corrections happened
    assert render_plan(plan) == text  # ...and the field still ends with the exact text


def test_no_typo_on_non_letters():
    # Digits / spaces / punctuation never get an adjacent-key typo.
    rng = random.Random(2)
    plan = build_typing_plan("12 34 .. !!", rng=rng, typo_prob=1.0)
    assert all(op[0] != "backspace" for op in plan)
    assert render_plan(plan) == "12 34 .. !!"


def test_pause_after_sentence_punctuation():
    rng = random.Random(3)
    # With a high sentence-pause chance over many tries, a pause op appears after '.'/'!'.
    saw_pause = False
    for _ in range(40):
        plan = build_typing_plan("Done. Next!", rng=rng)
        if any(op[0] == "pause" for op in plan):
            saw_pause = True
            break
    assert saw_pause


def test_deterministic_with_seed():
    a = build_typing_plan("reproducible please", rng=random.Random(42))
    b = build_typing_plan("reproducible please", rng=random.Random(42))
    assert a == b


def test_pause_durations_are_reasonable():
    rng = random.Random(5)
    for _ in range(200):
        for op in build_typing_plan("Hey. How are you? Good!", rng=rng):
            if op[0] == "pause":
                assert 0.1 <= op[1] <= 1.5
