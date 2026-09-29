"""Pure classification helpers for the Instagram activity feed.

Given a notification row's concatenated text and the localized type fragments
(``NOTIFICATION_SELECTORS.classifier_fragments``), decide the notification type
and best-effort actor username. No device access, no selectors — pure string
work, so it is unit-testable and shared by the engagement workflow's scan pass
and the ``notifications.scan`` diagnostics probe.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Time tokens like "54m", "10 h", "2 j", "1w", "3 d" trailing a row.
_TIME_RE = re.compile(r"\b(\d+\s*(?:min|mois|sem|[smhjdwy]))\b", re.IGNORECASE)

# Inline action affordances that mark a row as actionable (FR + EN).
# "suivre en retour" was missing while "follow back" was there: on a FR device a
# new-follower row with its follow-back button read as has_action=False.
_ACTION_WORDS = (
    "confirmer", "confirm", "répondre", "repondre", "reply",
    "follow back", "suivre en retour", "se réabonner", "message", "supprimer", "remove",
)


def extract_time(text: str) -> str:
    """Return the last trailing time token in ``text`` (e.g. "2 j"), or ""."""
    matches = _TIME_RE.findall(text or "")
    return matches[-1].strip() if matches else ""


def row_has_action(text: str) -> bool:
    """True if the row text exposes an inline action affordance (Confirm/Reply…)."""
    low = (text or "").lower()
    return any(word in low for word in _ACTION_WORDS)


# Button captions that leak into a row's concatenated text and are stripped from
# the DISPLAY label (FR + EN). Distinct captions only: bare words like
# "suivre"/"follow"/"like" also end the type phrases, so removing them would
# change the classification.
_TRAILING_AFFORDANCES = (
    "suivre en retour", "follow back", "envoyer un message", "send a message", "send message",
    "bouton j'aime", "bouton jaime", "like button", "répondre", "repondre", "reply",
    "confirmer", "confirm", "supprimer", "delete", "remove", "télécharger", "telecharger",
    "download", "voir plus", "afficher plus", "show more", "see more", "se réabonner",
    "se reabonner",
)
_TRUNCATION_RE = re.compile(r"(?:…|\.\.\.)\s*(?:suite|more|plus)\b", re.IGNORECASE)
_TRAILING_TIME_RE = re.compile(r"\b\d+\s*(?:min|mois|sem|[smhjdwy])\s*$", re.IGNORECASE)
_TRIM_CHARS = " ·-—:•."

# Glyphs that pollute extracted text: the U+FFFD replacement char (the accessibility
# dump emits it for some username badges and emojis), plus zero-width and
# bidirectional control marks. NBSP is normalized to a plain space.
_BAD_CHARS_RE = re.compile("[�​-‏‪-‮⁦-⁩﻿]")


def sanitize_text(text: str) -> str:
    """Strip undisplayable replacement / zero-width / bidi chars and normalize whitespace."""
    cleaned = _BAD_CHARS_RE.sub("", text or "")
    return " ".join(cleaned.split())


# Emoji-placeholder noise the XML dump leaves where a supplementary-plane emoji was
# (runs of 2+ dots, the ellipsis, the U+FFFD replacement char).
_EMOJI_NOISE_RE = re.compile(r"\.{2,}|…|�")


def longest_clean_run(text: str, min_len: int = 12) -> str:
    """Longest substring of ``text`` free of emoji-placeholder noise, or "".

    The XML dump replaces some emojis with placeholders, so a clean run makes a
    reliable ``textContains`` anchor to re-read the node's real text through the
    element API. Returns "" if no run reaches ``min_len`` (too short to anchor
    uniquely).
    """
    segments = _EMOJI_NOISE_RE.split(text or "")
    best = max((seg.strip() for seg in segments), key=len, default="")
    return best if len(best) >= min_len else ""


def clean_label(full: str) -> str:
    """Human display label for a notification row: drop the truncation marker, the
    trailing affordance captions (Reply/Like/Follow back/…) and the trailing time
    token that leak into the concatenated row text. Pure, locale-aware (FR+EN)."""
    text = full or ""
    match = _TRUNCATION_RE.search(text)
    if match:
        text = text[:match.start()]  # keep only the content before "… suite/more"
    text = " ".join(text.split())
    changed = True
    while changed and text:
        changed = False
        stripped = text.rstrip(_TRIM_CHARS)
        low = stripped.lower()
        for affordance in _TRAILING_AFFORDANCES:
            if low == affordance or low.endswith(" " + affordance):
                stripped = stripped[: len(stripped) - len(affordance)].rstrip(_TRIM_CHARS)
                changed = True
                break
        time_match = _TRAILING_TIME_RE.search(stripped)
        if time_match:
            stripped = stripped[: time_match.start()].rstrip(_TRIM_CHARS)
            changed = True
        text = stripped
    return sanitize_text(text).strip(_TRIM_CHARS)


def classify_row(full: str, fragments: Dict[str, List[str]]) -> Tuple[str, str]:
    """Return ``(type, username)`` for a row's concatenated text.

    ``fragments`` is an ordered ``type -> [fragment, ...]`` dict (classification
    priority = insertion order). The actor username usually leads the type phrase
    ("<user> a commencé à vous suivre"); for ``message``/``shared`` the phrase
    leads, so we fall back to the token AFTER it. Best-effort — an unmatched row
    is ``("other", "")``.
    """
    low = (full or "").lower()
    for type_name, frags in fragments.items():
        for frag in frags:
            if not frag:
                continue
            idx = low.find(frag.lower())
            if idx == -1:
                continue
            if idx > 0:
                user = full[:idx]
            else:
                # Phrase leads (message/shared "... from <user>"): take what follows.
                after = full[idx + len(frag):]
                user = after.split(".")[0]
            user = sanitize_text(_TIME_RE.sub("", user)).strip(" :·-—· ")
            return type_name, user
    return "other", ""


__all__ = ["classify_row", "clean_label", "extract_time", "row_has_action", "sanitize_text",
           "longest_clean_run", "_TIME_RE", "_ACTION_WORDS"]
