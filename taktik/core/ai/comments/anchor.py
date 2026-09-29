"""The anchor of a written comment: the words it says it reacts to, checked against the author's own.

Shared by every comment writer, Instagram's and TikTok's, so it lives with them and loads no
platform. What feeds `anchor_material` its thread (`select_thread_comments`, the post's comments
split by trust) stays with Instagram, the platform that reads a post's thread:
`social_media/instagram/workflows/common/comment_context.py`, which also tells the eighteen real
posts the measurements below were made on.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, List

_WORD_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def _strip_marks(value: str) -> str:
    """Casefolded, accent-free, emoji-free — the form two texts are compared in."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    letters = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", "".join(
        ch for ch in letters if ord(ch) < 0x2190 or ch.isspace()
    )).strip().casefold()


_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF]"
)


def _anchor_words(value: str) -> List[str]:
    """Like `_words`, but a mention or a hashtag keeps its body instead of vanishing.

    `_words` deletes them whole, which is right where it is used — a stranger's "@lea" is a
    copyable handle and "#foryou" is noise. It is WRONG here: on the author's side those are
    the author's own words about their own post. Measured on a real post whose entire caption
    was "@shame", `_words` left the anchor empty and the check rejected a perfectly grounded
    comment; the same deletion also threw away "#metz" under a photo of Metz.
    """
    return _WORD_RE.findall(re.sub(r"[@#]", " ", value or ""))


# ── The anchor ──────────────────────────────────────────────────────────────────────────────
#
# WHY A CONTRACT AND NOT A BETTER INSTRUCTION. A register offered to a model as an equal option
# becomes its default. Measured on 2026-09-09 across the same eighteen posts: adding a rule that
# ALLOWS a plain reaction about the form when nothing is certain took the bland count from 1 to 8
# of 18 and cut the average comment from 96 to 63 characters — "la lumière sur cette photo est
# incroyable" under a mountain sunset, "la photo est incroyable" under a longboard run.
#
# So the model no longer chooses. It writes BOTH registers and NAMES what it reacted to, in the
# author's own words; code checks those words exist and picks which one is published. Same corpus
# with the contract: 2 bland of 18, 53 characters, 6 emoji instead of 17, no cinema metaphor.
#
# WHAT THE CHECK IS WORTH, HONESTLY. Across two full replays of those eighteen posts it rejected
# three anchors, and all three were right: a caption that was only "@shame", a caption that was
# only "⛱️", and a Czech phrase the model copied with one letter missing ("vděnost" for the
# caption's "vděčnost"). Zero fabrications caught. So the thresholds below are set where a
# FABRICATION fails and a clumsy copy passes — the opposite calibration would trade a proven cost
# (a specific comment downgraded to a plain one) against an unproven benefit.
#
# What earns the mechanism its place is the OBLIGATION it puts upstream — a model made to name a
# concrete thing before writing stops reaching for style to fill the gap — not the rejection.

ANCHOR_MIN_COVERAGE = 0.5   # share of the anchor's content words that must be in the material.
                            # HALF, not a majority: at 0.6 a two-word anchor needed BOTH words,
                            # which rejected "nekonečná vděnost" — a real caption phrase copied
                            # with one letter missing. A fabrication still fails, because a
                            # fabricated anchor scores 0, not 0.5.
ANCHOR_MIN_WORDS = 1        # ONE content word is a real anchor ("melon", "solstice"); the
                            # stopword list below is what stops "la photo" from being one

# Words too common to prove anything: an anchor made of these matches every post ever written.
_ANCHOR_STOPWORDS = frozenset("""
photo image video post story reel picture shot pic
le la les un une des du de das ce cette cet et ou mais donc pour avec dans sur sous par
the this that these those and but for with from into over under about
il elle ils elles on nous vous je tu son sa ses leur leurs mon ma mes
est sont etre avoir fait faire tres plus moins bien tout tous toute toutes
is are was were be been has have had very more most all any some
""".split())


def anchor_material(caption: str = "", vision: str = "", selection: Any = None) -> str:
    """Everything an anchor may legitimately point at.

    The author's words and what the vision pass actually read — NOT the strangers' comments. A
    stranger's guess about a photo is context for understanding, never evidence to quote: letting
    the anchor rest on one would launder someone else's mistake into our own observation, which is
    the very failure this whole mechanism exists to stop.
    """
    parts = [caption or "", vision or ""]
    if selection is not None:
        parts.extend(entry["text"] for entry in getattr(selection, "author_replies", None) or [])
    return " ".join(part for part in parts if part)


def verify_anchor(anchor: str, material: str) -> bool:
    """Whether the model's stated anchor is really in the material.

    Not an exact substring: a model paraphrases, and demanding a verbatim match would reject
    honest anchors and push everything to the fallback — the failure mode we just measured in the
    other direction. What is required is that the anchor's CONTENT words are present, which is
    what tells "the creaminess in sauces" (said by the author) from "a rooftop terrace" (absent).

    An anchor made only of stopwords fails: it would otherwise match any post ever written.
    """
    # An emoji is a word here. `_strip_marks` drops emoji everywhere else, rightly — they are
    # noise inside a sentence. But a caption that is ONLY "⛱️" is the whole of what the author
    # wrote about their post, and dropping it left nothing to anchor on and downgraded a good
    # comment about the orange umbrella that emoji stands for.
    words = [w for w in _anchor_words(_strip_marks(anchor)) if w not in _ANCHOR_STOPWORDS]
    words += _EMOJI_RE.findall(anchor or "")
    if len(words) < ANCHOR_MIN_WORDS:
        return False
    haystack = set(_anchor_words(_strip_marks(material))) | set(_EMOJI_RE.findall(material or ""))
    if not haystack:
        return False
    # Prefix match on the first five characters for longer words, because French morphology
    # would otherwise reject honest anchors: creme/cremeux, reflet/reflets, lumiere/lumineux are
    # the same claim. Demanding identity there would push every paraphrase to the safe register —
    # which is precisely the blandness this mechanism exists to avoid. Five characters is short
    # enough for inflection and long enough that "cave" never reaches "calme".
    stems = {w[:5] for w in haystack if len(w) >= 5}

    def present(word: str) -> bool:
        return word in haystack or (len(word) >= 5 and word[:5] in stems)

    found = sum(1 for w in words if present(w))
    return (found / len(words)) >= ANCHOR_MIN_COVERAGE


__all__ = ["anchor_material", "verify_anchor"]
