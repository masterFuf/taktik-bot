"""The decisions taken AROUND a generated comment — which language, and is it usable at all.

Extracted from `instagram/workflows/core/ai_hooks.py` on 2026-08-30, unchanged, so TikTok can ask
the same questions instead of growing its own answers. Nothing here reads a screen or knows a
platform: it decides which language a comment may be written in, and whether what the model
returned is a comment or a refusal dressed as one.

Why shared rather than copied. Both rules are the kind that get *nearly* right the second time:
the language rule has an asymmetry that took a real incident to find (the app's UI language is
the OPERATOR's reading preference, never the audience's), and the refusal list grew one entry at
a time from replies that shipped. A second copy would drift on the day one platform learns
something the other does not.
"""

from typing import Any, Optional

from taktik.core.shared.text import detect_text_language

# Account/app language aliases -> a single code, so the detected POST language (an English name
# like "Spanish") can be compared against the account's preferred language (a code like "es").
# Codes match only exactly; full names match by prefix (so "Slovenian" is never read as English).
COMMENT_LANG_ALIASES = {
    "fr": ("french", "français", "francais"),
    "en": ("english", "anglais"),
    "es": ("spanish", "español", "espanol", "castellano"),
    "de": ("german", "deutsch", "allemand"),
    "it": ("italian", "italiano", "italien"),
    "pt": ("portuguese", "português", "portugues"),
    "ar": ("arabic", "arabe"),
}

#: Phrases a vision model produces when it did NOT see the post — an apology, not a comment.
#: Publishing one of these under someone's video says out loud that a machine wrote it.
COMMENT_REFUSAL_SIGNALS = (
    "i can't", "i cannot", "i'm unable", "i am unable",
    "without seeing", "without the image", "without viewing", "no image",
    "can't see", "cannot see", "don't have access", "do not have access",
    "provide an image", "share the image", "specific post", "specific content",
)

#: A real comment is short. Past this, the model is explaining itself rather than commenting.
COMMENT_MAX_LENGTH = 120


def detect_language_code(detected_lower: str) -> str:
    for code, names in COMMENT_LANG_ALIASES.items():
        if detected_lower == code or any(detected_lower.startswith(n) for n in names):
            return code
    return "other"


def resolve_base_language(account_persona: Any) -> Optional[str]:
    """The language THIS ACCOUNT speaks to its audience — or None if we cannot establish it.

    Takes no app language ON PURPOSE, so it cannot be passed back in: the app UI language is
    the OPERATOR's reading preference, not the audience's. A French coaching account operated
    from an English-language app is still a French account, and that former fallback made it
    both comment in English on French posts AND skip the French posts it should have taken.

    Order:
      1. the explicit `preferred_language` set on the account profile;
      2. failing that, the language the persona itself is WRITTEN IN — "Business coaching
         pour instituts de beauté" is unambiguously French. Free, needs no operator input,
         and works on accounts whose language field was never filled;
      3. None — the caller then follows the post, or skips. Never invents a language.
    """
    persona = account_persona if isinstance(account_persona, dict) else {}
    explicit = str(persona.get("language") or "").strip().lower()
    if explicit:
        code = detect_language_code(explicit)
        return code if code != "other" else explicit[:2]

    # The persona is stored in the account's own language — use it as the anchor.
    persona_text = " ".join(
        str(persona.get(key) or "")
        for key in ("niche", "tonePersonality", "targetAudience", "objective", "uniqueSellingPoint")
    ).strip()
    return detect_text_language(persona_text)


def resolve_comment_language(base_lang: Optional[str], post_language: Any) -> Optional[str]:
    """Decide which language to comment in, or None to SKIP the comment entirely.

    `base_lang` is the ACCOUNT's own language (see `resolve_base_language`), and may be None
    when it could not be established. A comment is read by real people, so it follows the
    POST's language — but only within {base_lang, English}:
      - post in base_lang                 -> comment in base_lang
      - post in English                   -> comment in English (universal 2nd language)
      - post in ANY other detected language -> None (skip): commenting a language we don't claim
        to speak isn't credible
      - language undetected                -> default to base_lang

    When base_lang is unknown, the post's own language is the only credible choice; with no
    signal at all we publish nothing rather than guess.

    **How far that third branch actually reaches.** `detect_text_language` answers `fr`, `en`, or
    None — and None for every other language, by design and by its own docstring. Measured
    2026-08-30: a Spanish caption and a German caption both come back None. So "post in ANY other
    detected language" cannot fire today, and such a post takes the *undetected* branch instead:
    a Spanish video gets a comment in the account's own language. The rule is written for a
    detector that knows more languages, and the alias table above already names the six it would
    need. Widening the detector is a change on Instagram's production path with a failure mode in
    the other direction (going silent on French posts when a Romance language wins by accident),
    so it is a deliberate decision, not a tidy-up. Until then this branch is dormant, and this
    paragraph is here so nobody reads the list above as a protection that already holds.
    """
    base = str(base_lang or "").strip().lower() or None
    detected = detect_language_code(str(post_language).strip().lower()) if post_language else None

    if base is None:
        # Account language unknown: follow the post when it is readable, else stay silent.
        return detected if detected and detected != "other" else None
    if detected is None:
        return base  # undetected → the account's own language
    if detected == base:
        return base
    if detected == "en":
        return "en"  # English is always allowed as a second language
    return None  # neither the account language nor English → don't comment


def is_comment_refusal(text: str) -> bool:
    """Did the model answer with a comment, or with an apology for not having seen the post?

    Both halves matter. The phrase list catches the explicit apologies; the length cap catches
    the ones that are polite enough not to say so — a model that could not read the image tends
    to write a paragraph about what it would say, and a paragraph is never a comment.
    """
    if not text:
        return True
    lowered = text.lower()
    return len(text) > COMMENT_MAX_LENGTH or any(
        signal in lowered for signal in COMMENT_REFUSAL_SIGNALS
    )


__all__ = [
    "COMMENT_LANG_ALIASES",
    "COMMENT_MAX_LENGTH",
    "COMMENT_REFUSAL_SIGNALS",
    "detect_language_code",
    "is_comment_refusal",
    "resolve_base_language",
    "resolve_comment_language",
]
