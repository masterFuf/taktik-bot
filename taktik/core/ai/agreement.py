"""Making a determiner agree with its noun, after the model has written the sentence.

WHY THIS EXISTS — every hard mistake the cheap generation model makes is the same shape: a
determiner that does not agree with its noun ("le vibe", "cette oxymore", "la néon", "la combo")
or a missed elision ("ce angle"). Not vocabulary, not tense, not register. One narrow class.

WHY IT IS A DICTIONARY AND NOT A MODEL — three mechanisms were built against this and measured
on 2026-09-09/10, and all three made things worse:

- an LLM proofreader REWROTE correct text ("c'est vraiment spécial" -> "spéciale");
- lowering the temperature kept the mistakes and tripled repeated openings at 0.3;
- asking the model itself for a noun's gender broke five correct comments out of six
  ("ce dont" -> "cette dont", "Ce coin" -> "Cette coin", "du live" -> "de la live").

They shared one flaw: they consulted the same source that wrote the text, outside the context
where that source is reliable. Measured in production, the written form was right five times out
of six. A dictionary is an INDEPENDENT authority, which is the whole difference.

WHY TWO AUTHORITIES AND NOT ONE — Lexique alone still broke correct French, always on the same
family: clipped words and anglicisms whose modern usage fixed a gender the lexicographic entry
does not know ("la box", "la typo", "une french"). So a noun is only in `data/agreement_fr.tsv`
when Lexique AND our own corpus of real human French agree on it. Measured on 1 370 generated
comments: 4 corrections, 4 correct, 0 correct text damaged.

WHAT IT WILL NOT CATCH — a compound noun whose head is elsewhere ("le face à face"), and every
word the two authorities do not both know. It is deliberately narrow: an unresolved gender is
not a mistake, while a fabricated correction is one we introduced ourselves.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_DATA = Path(__file__).with_name("data")


@dataclass(frozen=True)
class DeterminerFamily:
    """One determiner in all its gendered spellings, plus the forms that carry no gender.

    `elided` lists spellings of the SAME determiner that say nothing about the noun ("l'",
    "de l'"). They are recognised so they are never read as a disagreement and never rewritten:
    "l'ambiance" is correct and rewriting it to "la ambiance" would turn a right sentence wrong.
    """

    forms: Dict[str, str]
    elided: Tuple[str, ...] = ()
    # A spelling used only before a vowel sound, keyed by the gender it belongs to. French "ce"
    # becomes "cet" there, and getting that wrong is its own measured mistake ("ce angle").
    before_vowel: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LanguageAgreement:
    genders: Tuple[str, ...]
    families: Tuple[DeterminerFamily, ...] = ()
    lexicon_file: str = ""
    # Set when the language HAS grammatical gender but this mechanism cannot serve it safely.
    # Kept as a value rather than an omission, so the reason survives where someone reads it.
    unsupported_reason: str = ""

    @property
    def checks(self) -> bool:
        return bool(self.families and self.lexicon_file) and not self.unsupported_reason


_NO_GENDER = LanguageAgreement(genders=())

LANGUAGES: Dict[str, LanguageAgreement] = {
    "fr": LanguageAgreement(
        genders=("m", "f"),
        lexicon_file="agreement_fr.tsv",
        families=(
            # Contracted determiners lead: "de la" must be replaced whole, or the shorter `la`
            # matches inside it and produces "de le", which is not French.
            DeterminerFamily({"m": "du", "f": "de la"}, elided=("de l'",)),
            DeterminerFamily({"m": "au", "f": "à la"}, elided=("à l'",)),
            DeterminerFamily({"m": "ce", "f": "cette"}, before_vowel={"m": "cet"}),
            DeterminerFamily({"m": "le", "f": "la"}, elided=("l'",)),
            DeterminerFamily({"m": "un", "f": "une"}),
        ),
    ),
    # No grammatical gender: nothing to check. This emptiness is a FACT about the language, not
    # a gap waiting to be filled, and saying so is the point — a guard that silently protects
    # one language and not the others reads as coverage it does not have.
    "en": _NO_GENDER,
    "zh": _NO_GENDER,
    "ja": _NO_GENDER,
    "ko": _NO_GENDER,
    "tr": _NO_GENDER,
    "fi": _NO_GENDER,
    "hu": _NO_GENDER,
    "id": _NO_GENDER,
    # Gendered, but out of reach for now. Each needs its own validated lexicon before it can be
    # switched on, and shipping the mechanism without one would be worse than not shipping it.
    "es": LanguageAgreement(genders=("m", "f"),
                            unsupported_reason="no validated Spanish lexicon yet"),
    "pt": LanguageAgreement(genders=("m", "f"),
                            unsupported_reason="no validated Portuguese lexicon yet"),
    "it": LanguageAgreement(genders=("m", "f"),
                            unsupported_reason="no validated Italian lexicon yet"),
    "nl": LanguageAgreement(genders=("de", "het"),
                            unsupported_reason="no validated Dutch lexicon yet"),
    "de": LanguageAgreement(
        genders=("m", "f", "n"),
        unsupported_reason=(
            "a German determiner encodes gender AND case (der/die/das/den/dem/des), so the "
            "correct spelling cannot be derived from the noun's gender alone — swapping one "
            "would produce a case error in place of a gender error"
        ),
    ),
    "ar": LanguageAgreement(
        genders=("m", "f"),
        unsupported_reason=(
            "the Arabic definite article does not inflect for gender, so a determiner carries "
            "no agreement to check"
        ),
    ),
}

_VOWELS = set("aeiouâàéèêëïîôöûü")
_WORD = r"[^\W\d_]"
_lexicons: Dict[str, Dict[str, str]] = {}


def _bare(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _starts_with_vowel(word: str) -> bool:
    """Whether the elided form applies. `h` counts: French treats most of them as vowels here,
    and "cet hôtel" is right far more often than "ce hôtel"."""
    bare = _bare(word).lower()
    return bool(bare) and (bare[0] in _VOWELS or bare[0] == "h")


def lexicon(language: str) -> Dict[str, str]:
    """The validated noun genders for `language`, read once and kept.

    A missing or unreadable file yields an empty lexicon, which disables the check for that
    language rather than raising: this is a bonus on top of a comment, never a blocker.
    """
    code = (language or "").strip().lower()[:2]
    if code in _lexicons:
        return _lexicons[code]
    profile = LANGUAGES.get(code)
    words: Dict[str, str] = {}
    if profile is not None and profile.lexicon_file:
        try:
            with (_DATA / profile.lexicon_file).open(encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("#") or "\t" not in line:
                        continue
                    word, gender = line.rstrip("\n").split("\t", 1)
                    if gender in profile.genders:
                        words[word.lower()] = gender
        except OSError:
            words = {}
    _lexicons[code] = words
    return words


def profile_for(language: str) -> Optional[LanguageAgreement]:
    """The language's profile, or None when nobody has looked at this language at all.

    None and a profile carrying `unsupported_reason` are DIFFERENT answers, and the difference
    is worth keeping: one means unexamined, the other means examined and declined.
    """
    return LANGUAGES.get((language or "").strip().lower()[:2])


def apply(text: str, language: str) -> Tuple[str, List[str]]:
    """`text` with every disagreeing determiner corrected, and one note per correction.

    Only ever substitutes a determiner for another spelling OF THE SAME determiner. Nothing else
    in the string can change — not a word, not an emoji, not the deliberately missing final
    period — which is what makes this safe to run on output the whole prompt was shaped to get.
    """
    profile = profile_for(language)
    if not text or profile is None or not profile.checks:
        return text, []
    words = lexicon(language)
    if not words:
        return text, []

    spans = _determiner_spans(text, profile)
    fixes: List[str] = []
    result = text
    # Right to left, so an earlier span's offsets survive a later replacement.
    for start, end, written, noun, family in sorted(spans, reverse=True):
        gender = words.get(noun.lower())
        if gender is None or gender not in family.forms:
            continue                      # unknown gender is not a mistake: leave it alone
        wanted = family.forms[gender]
        if gender in family.before_vowel and _starts_with_vowel(noun):
            wanted = family.before_vowel[gender]
        if written.lower() == wanted.lower():
            continue
        if written[:1].isupper():
            wanted = wanted[:1].upper() + wanted[1:]
        result = result[:start] + wanted + result[end:]
        fixes.append(f"{written} {noun} -> {wanted} {noun}")
    return result, list(reversed(fixes))


def _determiner_spans(text: str, profile: LanguageAgreement):
    """Every (span, written determiner, following noun, family), overlaps resolved.

    The LONGEST match wins every overlap. Without that, the `le`/`la` family matches inside
    "de la" and turns "de la néon" into "de le néon" — a contracted determiner is corrected
    whole or not at all.
    """
    found = []
    for family in profile.families:
        spellings = set(family.forms.values()) | set(family.before_vowel.values())
        for spelling in spellings:
            pattern = re.compile(
                r"(?<!\w)(" + re.escape(spelling).replace(r"\ ", r"\s+")
                + r")\s+(" + _WORD + r"{2,24})\b",
                re.IGNORECASE | re.UNICODE,
            )
            for match in pattern.finditer(text):
                if _bare(match.group(1)).lower() in {
                    _bare(form).lower() for form in family.elided
                }:
                    continue
                found.append((match.start(1), match.end(1), match.group(1),
                              match.group(2), family))

    found.sort(key=lambda item: (item[0] - item[1], item[0]))
    kept = []
    for start, end, written, noun, family in found:
        if any(start < k_end and k_start < end for k_start, k_end, _, _, _ in kept):
            continue
        kept.append((start, end, written, noun, family))
    return kept


def unchecked_languages() -> Dict[str, str]:
    """Languages we know of and deliberately do not check, with the reason for each.

    Exposed so the reason reaches a log or a panel instead of living only in this file: a guard
    that silently does nothing is the failure this module is shaped against.
    """
    reasons = {}
    for code, profile in LANGUAGES.items():
        if profile.unsupported_reason:
            reasons[code] = profile.unsupported_reason
        elif not profile.genders:
            reasons[code] = "this language has no grammatical gender"
    return reasons


__all__ = [
    "LANGUAGES",
    "LanguageAgreement",
    "DeterminerFamily",
    "apply",
    "lexicon",
    "profile_for",
    "unchecked_languages",
]
