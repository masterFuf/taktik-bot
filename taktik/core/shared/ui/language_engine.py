"""Shared engine for detecting an app's UI language and filtering selectors by it.

Both platforms had their own copy of this. Ten of their eleven functions carried the
same name, five were byte-identical, and the copies drifted where it mattered: the
defect that let the always-English resource-ids of a dump inflate the English score was
found and fixed on one platform, then rediscovered on the other weeks later.

What is genuinely platform-specific stays with the platform: the vocabulary, the
probes, the decision thresholds, the list of selector singletons to optimize, and the
locale wiring. What is shared is the mechanism below.

Scoring rule, applied identically everywhere: an exact value match is worth one point, a
whole-word match half a point. Whole-word matching is what keeps a word of one language
from scoring inside a longer word of another.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Pattern, Sequence, Set, Tuple

# Only the VALUES of the visible-text attributes are ever scored. A hierarchy dump always
# carries English identifiers, so testing the raw XML hands English a free point per
# probe, independently of the language the app actually runs in.
_VISIBLE_ATTR_RE = re.compile(r'(?:text|content-desc)="([^"]*)"')

# Quoted text values of an xpath: @text="…", @content-desc="…", @hint="…", text()="…",
# and the contains() form, whose comma is covered by the [,=] class. Two alternations, so
# an apostrophe inside a double-quoted value does not end the match early.
_XPATH_TEXT_RE = re.compile(
    r'''(?:@text|@content-desc|@hint|text\(\))\s*[,=]\s*(?:"([^"]+)"|'([^']+)')'''
)


WordPattern = Tuple[str, Pattern]


def visible_strings(xml: str) -> List[str]:
    """The text and content-desc values of a dump — what the user can actually read."""
    return _VISIBLE_ATTR_RE.findall(xml or "")


def word_pattern(word: str) -> Pattern:
    """Whole-word, case-insensitive pattern for one vocabulary word."""
    return re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)


def compile_vocabulary(words: Iterable[str]) -> Tuple[WordPattern, ...]:
    """Compile a vocabulary once: detection scores every word against every string."""
    return tuple((w, word_pattern(w)) for w in sorted(words))


def score_patterns(patterns: Sequence[WordPattern], values: Sequence[str]) -> Tuple[float, List[str]]:
    """Score a compiled vocabulary against the visible strings.

    Returns ``(score, matched_words)``. The matched words are reported so an undecided
    detection can say WHY in one log line, rather than printing a bare score.
    """
    score = 0.0
    matched: List[str] = []
    lowered = [v.strip().lower() for v in values]
    for word, pattern in patterns:
        needle = word.strip().lower()
        if needle in lowered:
            score += 1.0
            matched.append(word)
            continue
        if any(pattern.search(v) for v in values):
            score += 0.5
            matched.append(word)
    return score, matched


def read_dump(device) -> Optional[str]:
    """The hierarchy dump of ``device``, whatever shape of device object it is."""
    for accessor in ("get_xml_dump", "dump_hierarchy"):
        if hasattr(device, accessor):
            return getattr(device, accessor)()
    inner = getattr(device, "device", None)
    if inner is not None and hasattr(inner, "dump_hierarchy"):
        return inner.dump_hierarchy()
    return None


@dataclass(frozen=True)
class Decision:
    """Outcome of one detection, with everything a log line needs to explain it."""

    language: str
    fr_score: float
    en_score: float
    fr_matched: List[str]
    en_matched: List[str]
    values_seen: int


def decide(
    xml: str,
    fr_patterns: Sequence[WordPattern],
    en_patterns: Sequence[WordPattern],
    *,
    min_score: float,
    min_ratio: float,
) -> Decision:
    """Score a dump and commit to a language only when the winner is clearly ahead.

    A wrong language is worse than no language: it strips the correct selectors, whereas
    an undecided one keeps every locale. Hence both a floor and a ratio — at low score
    levels a one-point lead is noise.
    """
    values = visible_strings(xml)
    fr_score, fr_matched = score_patterns(fr_patterns, values)
    en_score, en_matched = score_patterns(en_patterns, values)

    if fr_score >= min_score and fr_score >= en_score * min_ratio:
        language = "fr"
    elif en_score >= min_score and en_score >= fr_score * min_ratio:
        language = "en"
    else:
        language = "unknown"

    return Decision(language, fr_score, en_score, fr_matched, en_matched, len(values))


def classify_selector(
    xpath: str,
    fr_words: Set[str],
    en_words: Set[str],
) -> str:
    """Classify one xpath as ``'fr'``, ``'en'`` or ``'neutral'``.

    A selector referencing only a resource-id, a class or a position is neutral and is
    never filtered. For the others, two safety rules.

    Substring collisions are settled by the LONGEST match, since a word of one language
    can be contained in a word of another; on a tie the two are treated as mixed. And a
    selector holding both languages stays neutral rather than being attributed
    arbitrarily: keeping it costs a useless lookup, dropping it breaks the screen.
    """
    raw_matches = _XPATH_TEXT_RE.findall(xpath or "")
    text_values = [m[0] or m[1] for m in raw_matches]
    if not text_values:
        return "neutral"

    has_fr = False
    has_en = False
    for value in text_values:
        # XPath escapes an apostrophe inside a string, so normalise it back first.
        stripped = value.strip().replace("\\'", "'")
        best_fr = max((len(w) for w in fr_words if w in stripped), default=0)
        best_en = max((len(w) for w in en_words if w in stripped), default=0)
        if best_fr > 0 and best_fr >= best_en:
            has_fr = True
        elif best_en > 0 and best_en > best_fr:
            has_en = True
        elif best_fr > 0 and best_en > 0:
            has_fr = True
            has_en = True

    if has_fr and has_en:
        return "neutral"
    if has_fr:
        return "fr"
    if has_en:
        return "en"
    return "neutral"


def filter_selectors(
    selectors: List[str],
    lang: str,
    fr_words: Set[str],
    en_words: Set[str],
) -> List[str]:
    """Drop the selectors targeting another language. Undecided keeps them all."""
    if lang == "unknown" or not lang:
        return selectors
    exclude = "fr" if lang == "en" else "en"
    return [s for s in selectors if classify_selector(s, fr_words, en_words) != exclude]


def optimize_selector_dataclass(
    instance,
    lang: str,
    fr_words: Set[str],
    en_words: Set[str],
) -> int:
    """Filter every list field of a selector dataclass in place. Returns the count removed.

    Only real fields are touched. A dataclass exposing concatenated selectors through a
    property is left alone there, since the property recomputes from the internal lists
    that this pass has already filtered.
    """
    if lang == "unknown" or not lang:
        return 0

    removed = 0
    for name in getattr(instance, "__dataclass_fields__", {}):
        value = getattr(instance, name, None)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            continue
        kept = filter_selectors(value, lang, fr_words, en_words)
        if len(kept) != len(value):
            removed += len(value) - len(kept)
            setattr(instance, name, kept)
    return removed


__all__ = [
    "Decision",
    "classify_selector",
    "compile_vocabulary",
    "decide",
    "filter_selectors",
    "optimize_selector_dataclass",
    "read_dump",
    "score_patterns",
    "visible_strings",
    "word_pattern",
]
