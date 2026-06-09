"""Human typing plan: turn a target string into a sequence of type / backspace / pause
operations that reproduce how a person actually types — occasional adjacent-key typos
that get corrected, and think-pauses (after a sentence, sometimes before a word).

A robotic bot commits the exact string in one burst; a human fumbles a key now and then
and pauses to think. Applying the plan (`render_plan`) ALWAYS yields the exact target
text — every typo is corrected — so callers never post a mistake.

Pure functions, no device. The device execution (keyboard broadcasts + DEL keyevents)
lives in `taktik/core/shared/input/taktik_keyboard.py::type_text_human`.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

# One op is ("type", text) | ("backspace", count) | ("pause", seconds).
TypingOp = Tuple

# Adjacent keys on a QWERTY layout — the realistic "wrong nearby key" for a typo. The
# exact layout matters little (the typo is corrected immediately); the human signal is
# the type → notice → backspace → retype rhythm, not which wrong key was hit.
_QWERTY_NEIGHBORS = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr",
    "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb", "i": "ujko", "j": "huikmn",
    "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp",
    "p": "ol", "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy",
    "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}


def _adjacent_key(ch: str, rng: random.Random) -> Optional[str]:
    """A plausible wrong neighbouring key for `ch`, preserving case. None if unknown."""
    neighbors = _QWERTY_NEIGHBORS.get(ch.lower())
    if not neighbors:
        return None
    wrong = rng.choice(neighbors)
    return wrong.upper() if ch.isupper() else wrong


def build_typing_plan(
    text: str,
    *,
    rng: Optional[random.Random] = None,
    typo_prob: float = 0.04,
    space_pause_prob: float = 0.10,
    sentence_pause_prob: float = 0.6,
) -> List[TypingOp]:
    """Plan how to type `text` like a human.

    typo_prob: per-letter chance of a corrected adjacent-key typo (~4% default).
    space_pause_prob: chance of a short think-pause at a space.
    sentence_pause_prob: chance of a longer pause after . ! ?.

    Returns a list of ("type", s) / ("backspace", n) / ("pause", seconds) ops whose
    rendering equals `text` exactly.
    """
    rng = rng or random
    ops: List[TypingOp] = []
    buf: List[str] = []

    def flush() -> None:
        if buf:
            ops.append(("type", "".join(buf)))
            buf.clear()

    for ch in text:
        # A typo before this letter: type a wrong neighbour, hesitate, backspace.
        if ch.isalpha() and rng.random() < typo_prob:
            wrong = _adjacent_key(ch, rng)
            if wrong and wrong != ch:
                buf.append(wrong)
                flush()
                ops.append(("pause", round(rng.uniform(0.15, 0.5), 3)))
                ops.append(("backspace", 1))
        buf.append(ch)

        # Think-pauses: longer after a sentence, shorter at some word boundaries.
        if ch in ".!?" and rng.random() < sentence_pause_prob:
            flush()
            ops.append(("pause", round(rng.uniform(0.4, 1.2), 3)))
        elif ch == " " and rng.random() < space_pause_prob:
            flush()
            ops.append(("pause", round(rng.uniform(0.2, 0.7), 3)))

    flush()
    return ops


def render_plan(ops: List[TypingOp]) -> str:
    """Apply a typing plan to an empty field and return the resulting text — used to
    prove every typo is corrected (rendering == the original target text)."""
    out: List[str] = []
    for op in ops:
        kind = op[0]
        if kind == "type":
            out.extend(op[1])
        elif kind == "backspace":
            for _ in range(op[1]):
                if out:
                    out.pop()
        # "pause" has no effect on the text
    return "".join(out)


__all__ = ["build_typing_plan", "render_plan", "TypingOp"]
