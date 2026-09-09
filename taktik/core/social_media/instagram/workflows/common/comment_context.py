"""Turning a post's own comment thread into material a comment writer can be held to.

WHY THIS EXISTS — a comment can only be as specific as the material it was given, and a caption
plus one vision reading is thin material. Measured on 2026-09-09 over eighteen real posts, the
production prompt compensates for that thinness with STYLE rather than substance: six of the
eighteen comments reached for a cinema metaphor ("on dirait un plan-séquence", "une image volée
d'un film noir", "un documentaire sur le post-punk"), and seventeen of the eighteen carried an
emoji. Both are recognisable across an account long before any single comment looks wrong.

A NOTE ON WHAT THIS IS NOT — this feature was first justified by an invention: a comment reading
"j'adore cette idée de l'intégrer dans des cakes" under a tofu post. Checked against the caption
afterwards, the caption says "que vous souhaitiez l'intégrer dans des sauces onctueuses ou des
cakes" — the model was quoting the author. Replaying those eighteen posts found no invention at
all, so nothing here is a hallucination shield: the thread is about giving the writer MORE real
material, and the anchor below is about spending it.

The thread is where a human looks before commenting, and it carries two things the caption does
not: what the author SAID about their own post when someone asked, and what has already been
said eight times over.

THREE CHANNELS, BY HOW MUCH THEY CAN BE TRUSTED — this is the whole design:

- The AUTHOR's own replies are FACTS about the post. An author clarifying their post almost
  always does it as a reply ("no, it's silken tofu, fermented 24h"), and that sentence exists
  nowhere else — not in the caption, not in the image. It is the only material this feature
  adds that the writer could not already have had.
- A stranger's substantial comment is CONTEXT, never a fact. Someone else's guess about what a
  photo shows is not evidence, and a model told otherwise will happily repeat a stranger's
  mistake as its own observation.
- SHORT PRAISE is never listed, only counted. Listing eight "magnifique 😍" costs ~120 tokens
  AND teaches the model the exact register the rules forbid. Counted, the same information
  costs ~15 tokens and says the one useful thing: the obvious reaction is already taken.

Everything here is PURE — no device, no I/O — so the rules below are testable against captured
records rather than against a phone.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from taktik.core.shared.text import detect_text_language

# ── Bounds. Each one is a decision, not a default. ──────────────────────────────────────────
MAX_RECORDS = 20          # what we ever look at: the first screen carries 5-9 comments
MAX_AUTHOR = 3            # the factual channel; more than three and the author is ranting
MAX_ITEMS = 12            # strangers' comments actually listed
MAX_PRAISE_SAMPLES = 5
AUTHOR_TRUNCATE = 160     # a clarification is worth its length
ITEM_TRUNCATE = 140
PRAISE_SAMPLE_TRUNCATE = 20
ITEMS_CHAR_BUDGET = 900   # ~250 tokens for the whole strangers block

# Substance: what it takes to be LISTED rather than counted as praise.
MIN_WORDS, MIN_CHARS = 3, 12
MIN_WORDS_AUTHOR, MIN_CHARS_AUTHOR = 2, 6

_URL_MARKERS = ("http", "www.", ".com/", ".fr/", "t.me", "wa.me")
# One character is a valid Instagram handle, and a burst of "@a @b @c" is exactly the shape
# of a tag-farm comment — requiring two characters let the most obvious case through.
_MENTION_RE = re.compile(r"@[A-Za-z0-9._]{1,30}")
_HASHTAG_RE = re.compile(r"#\w+")
_DIGIT_RUN_RE = re.compile(r"\d{8,}")
_REPEAT_RE = re.compile(r"(.)\1{5,}")
_WORD_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


@dataclass(frozen=True)
class ThreadSelection:
    """What the thread gave, split by trust, plus why the rest was dropped."""

    author_replies: List[Dict[str, Any]] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    praise_count: int = 0
    praise_samples: List[str] = field(default_factory=list)
    banned_openers: List[str] = field(default_factory=list)
    banned_emoji: List[str] = field(default_factory=list)
    already_commented: bool = False
    truncated: bool = False
    seen: int = 0
    kept: int = 0
    dropped: Dict[str, int] = field(default_factory=dict)

    @property
    def has_material(self) -> bool:
        return bool(self.author_replies or self.items or self.praise_count)


def _strip_marks(value: str) -> str:
    """Casefolded, accent-free, emoji-free — the form two texts are compared in."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    letters = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", "".join(
        ch for ch in letters if ord(ch) < 0x2190 or ch.isspace()
    )).strip().casefold()


def _is_emoji(ch: str) -> bool:
    # Same threshold `_build_anti_tic_block` uses: arrows and above, never a letter.
    return ord(ch) >= 0x2190


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


def _words(value: str) -> List[str]:
    """Words left once mentions, hashtags, emoji and punctuation are gone."""
    stripped = _HASHTAG_RE.sub(" ", _MENTION_RE.sub(" ", value or ""))
    return _WORD_RE.findall(stripped)


def _foreign_script(value: str) -> bool:
    """More than 30 % of the letters outside the Latin range.

    `detect_text_language` only ever answers fr / en / None, so a CJK, Cyrillic or Arabic
    comment would sail through the language filter, eat the budget and teach the model nothing.
    """
    letters = [ch for ch in (value or "") if ch.isalpha()]
    if len(letters) < 4:
        return False
    foreign = sum(1 for ch in letters if ord(ch) > 0x024F)
    return foreign / len(letters) > 0.30


def _spammy(value: str) -> bool:
    """Structural spam only — no word list, so no i18n debt and nothing to maintain."""
    low = (value or "").lower()
    if any(marker in low for marker in _URL_MARKERS):
        return True
    if len(_MENTION_RE.findall(value or "")) >= 3:
        return True
    if len(_HASHTAG_RE.findall(value or "")) >= 5:
        return True
    if _DIGIT_RUN_RE.search(value or ""):
        return True
    if _REPEAT_RE.search(value or ""):
        return True
    letters = [ch for ch in (value or "") if ch.isalpha()]
    if len(letters) > 20 and sum(1 for ch in letters if ch.isupper()) / len(letters) > 0.40:
        return True
    return False


def _truncate(value: str, limit: int) -> str:
    """Cut on a word boundary; a half-word reads as a transcription error."""
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.6 else cut).rstrip() + "…"


def select_thread_comments(
    records: Optional[List[Dict[str, Any]]],
    *,
    own_handle: str = "",
    own_recent_texts: Optional[List[str]] = None,
    post_author: str = "",
    comment_lang: Optional[str] = None,
    base_lang: Optional[str] = None,
) -> ThreadSelection:
    """Split a thread into the three channels, dropping what cannot help.

    Order is SCREEN order throughout, never a re-sort by likes: Instagram already puts what it
    judges most relevant on top, likes are parsed only intermittently, and the fallback reader
    carries none at all — re-sorting would make two runs disagree on the same screen.
    """
    dropped: Dict[str, int] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    rows = list(records or [])[:MAX_RECORDS]
    author = (post_author or "").strip().lstrip("@").casefold()
    mine = (own_handle or "").strip().lstrip("@").casefold()
    own_norm = {_strip_marks(t) for t in (own_recent_texts or []) if t}
    # The language filter only runs when we KNOW what language we are aiming at. With both
    # unknown the allowed set would collapse to English alone and drop every French comment
    # on a French post — filtering against an unknown target is worse than not filtering.
    target_known = bool(comment_lang or base_lang)
    allowed = {code for code in (comment_lang, base_lang, "en") if code} if target_known else set()

    author_replies: List[Dict[str, Any]] = []
    items: List[Dict[str, Any]] = []
    praise: List[str] = []
    already_commented = False
    seen_keys = set()
    used_chars = 0
    truncated = False

    for row in rows:
        text = re.sub(r"\s+", " ", str(row.get("text") or "")).strip()
        if not text:
            drop("empty")
            continue
        handle = str(row.get("username") or "").strip().lstrip("@").casefold()
        is_author = bool(author) and handle == author

        # 1. A reply between third parties is a conversation about something else, and it
        #    carries copyable @mentions. The AUTHOR's reply is the opposite: it is the one
        #    place they explain their own post.
        if row.get("is_reply") and not is_author:
            drop("reply_between_others")
            continue

        # 2. Never feed the account its own words back. Two nets, because the handle can be
        #    unresolvable while the text comparison never is.
        if (mine and handle == mine) or (_strip_marks(text) in own_norm):
            already_commented = True
            drop("our_own")
            continue

        if _foreign_script(text):
            drop("foreign_script")
            continue
        if _spammy(text):
            drop("spam")
            continue

        key = _strip_marks(text)[:24]
        if key and key in seen_keys:
            drop("duplicate")
            continue

        words = _words(text)
        min_words, min_chars = (
            (MIN_WORDS_AUTHOR, MIN_CHARS_AUTHOR) if is_author else (MIN_WORDS, MIN_CHARS)
        )
        substantial = len(words) >= min_words and len(" ".join(words)) >= min_chars

        # 6. Language: drop only on a CONFIDENT verdict outside the allowed set. `None` keeps
        #    the comment — short texts return None almost always, and the script filter above
        #    has already removed the genuinely foreign alphabets.
        if substantial and target_known:
            verdict = detect_text_language(text)
            if verdict and verdict not in allowed:
                drop("other_language")
                continue

        if key:
            seen_keys.add(key)

        if is_author:
            if len(author_replies) < MAX_AUTHOR and substantial:
                author_replies.append({
                    "text": _truncate(text, AUTHOR_TRUNCATE),
                    "answers": str(row.get("parent_username") or "") or None,
                })
            continue

        if not substantial:
            praise.append(text)
            continue

        if len(items) >= MAX_ITEMS:
            drop("over_item_cap")
            continue
        piece = _truncate(text, ITEM_TRUNCATE)
        if used_chars + len(piece) > ITEMS_CHAR_BUDGET:
            truncated = True
            drop("over_char_budget")
            continue
        used_chars += len(piece)
        items.append({"text": piece, "likes": int(row.get("likes") or 0)})

    # Praise: counted, and sampled only to show the register that is already taken.
    praise_samples: List[str] = []
    for text in praise:
        short = _truncate(text, PRAISE_SAMPLE_TRUNCATE)
        if short and short not in praise_samples and len(praise_samples) < MAX_PRAISE_SAMPLES:
            praise_samples.append(short)

    banned_openers, banned_emoji = _recurring(
        [entry["text"] for entry in items] + praise_samples
    )

    return ThreadSelection(
        author_replies=author_replies,
        items=items,
        praise_count=len(praise),
        praise_samples=praise_samples,
        banned_openers=banned_openers,
        banned_emoji=banned_emoji,
        already_commented=already_commented,
        truncated=truncated,
        seen=len(rows),
        kept=len(author_replies) + len(items),
        dropped=dropped,
    )


def _recurring(texts: List[str]) -> tuple:
    """Openers and emoji already used twice in this thread.

    Same deterministic mechanism as `_build_anti_tic_block`, and for the same measured reason:
    a nominal ban does not hold (the sparkle stayed at 13.6 % of all emoji while nominally
    banned), an explicit list does. Here it bans what THIS thread is already saturated with —
    which is how a comment stops being the ninth identical reaction.
    """
    openers: Dict[str, int] = {}
    emoji: Dict[str, int] = {}
    for text in texts:
        words = (text or "").lower().split()
        if words:
            opener = " ".join(words[:2])
            openers[opener] = openers.get(opener, 0) + 1
        for ch in text or "":
            if _is_emoji(ch):
                emoji[ch] = emoji.get(ch, 0) + 1
    return (
        [key for key, count in openers.items() if count >= 2],
        [key for key, count in emoji.items() if count >= 2],
    )


def context_overlap(comment: str, selection: ThreadSelection) -> float:
    """How much of `comment` is lifted from the thread — 0.0 to 1.0.

    A comment that merely re-says what is already on screen is worse than a bland one: it reads
    as a bot echoing the room. Measured on the produced comment AFTER generation, never fed back
    into it, so it is an observation and not a lever the model can game.
    """
    words = _strip_marks(comment).split()
    if len(words) < 3:
        return 0.0
    grams = {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}
    if not grams:
        return 0.0
    source_words = _strip_marks(" ".join(
        [entry["text"] for entry in selection.items]
        + [entry["text"] for entry in selection.author_replies]
        + selection.praise_samples
    )).split()
    source = {" ".join(source_words[i:i + 3]) for i in range(max(0, len(source_words) - 2))}
    if not source:
        return 0.0
    return len(grams & source) / len(grams)



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


def anchor_material(caption: str = "", vision: str = "", selection: Optional[ThreadSelection] = None) -> str:
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


__all__ = [
    "ThreadSelection",
    "select_thread_comments",
    "context_overlap",
    "anchor_material",
    "verify_anchor",
]
