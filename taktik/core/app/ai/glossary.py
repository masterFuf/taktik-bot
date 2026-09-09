"""Spellings a model gets wrong often enough to be worth naming, per language.

WHY THIS SHAPE AND NOT ANOTHER — three mechanisms were built and measured against this same
problem on 2026-09-09, and all three failed for the same reason: they asked the model to JUDGE
text after the fact.

- An LLM proofreader rewrote correct text ("c'est vraiment spécial" -> "spéciale").
- Lowering the temperature did not remove the mistakes and tripled repeated openings at 0.3.
- A determiner corrector, fed the model's own out-of-context gender answers, broke five correct
  comments out of six ("ce dont" -> "cette dont", "Ce coin" -> "Cette coin").

That last one carries the lesson this file is built on: the model's generation IN CONTEXT is more
reliable than its lookup out of context. So this does not correct anything. It informs the
writing, in the one place the model is at its best, and then gets out of the way.

ONLY CORRECT FORMS, NEVER THE MISTAKE. Measured the same day: given "ça m'intrigue" as an example
in the rules, mistral-nemo published that exact phrase in 5 of 18 comments. A model reads an
example as something to use, so a wrong form shown here would be a wrong form offered.

HOW IT GROWS — from mistakes actually seen in published output, added by hand. There is no
automatic detector, and the day's measurements are why: every automatic judge tried was less
reliable than the writing it was judging. A human reading a comment remains the only detector we
have, which makes this list short and slow-growing on purpose.

WHAT IT COSTS — it rides in the CACHED prefix, so its tokens are billed at about a tenth.
Measured on 54 comments: 25 -> 26 uSD each, +4 %, with repeated openings going from 4 to 1.
"""

from __future__ import annotations

from typing import Dict, Tuple

# Every entry here was written WRONG by a production model at least once, on a real post.
# French: 216 replayed comments plus a corpus mining pass over 427 more, 2026-09-09.
# `scripts/mine_agreement_glossary.py` finds them without asking a model to judge anything:
# it counts what the reference model wrote unanimously, and reports where the cheap one
# contradicts it. Re-run it as the published corpus grows.
GLOSSARY: Dict[str, Tuple[str, ...]] = {
    # Six entries, and every one of them was written WRONG by a production model on a real post.
    # The list stayed at six on purpose: a first draft carried a dozen, but half of those had
    # been copied from a test fixture rather than observed, which made this file claim more
    # coverage than it had. An entry earns its place by having been a mistake, not by being a
    # word somebody suspected.
    "fr": (
        "la vibe",        # written "le vibe" and "ce vibe"
        "cet angle",      # written "ce angle"
        "ce néon",        # written "la néon"
        "la légèreté",    # written "ce légereté"
        "cet oxymore",    # written "cette oxymore"
        "le noir",        # written "cette noir"
        "le combo",       # written "la combo", 3 times in 943 comments
    ),
}

# Languages with no grammatical gender have nothing to put here, which is a fact about the
# language rather than a gap in our data — English, Chinese, Japanese, Korean, Turkish, Finnish,
# Hungarian and Indonesian will stay empty, and that is the correct state for them.


def block(language: str) -> str:
    """The glossary line for `language`, or "" when there is nothing to say.

    Returned as a whole prompt line so the caller never has to know the shape. An unknown
    language, or one with no entries, contributes nothing at all — no header, no empty list,
    nothing for a model to interpret.
    """
    entries = GLOSSARY.get((language or "").strip().lower()[:2], ())
    if not entries:
        return ""
    seen = list(dict.fromkeys(entries))
    return (
        "\n- These spellings are the correct ones and are easy to get wrong — use them exactly "
        "as written when the word comes up: " + ", ".join(seen)
    )


__all__ = ["GLOSSARY", "block"]
