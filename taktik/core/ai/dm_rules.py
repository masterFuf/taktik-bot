"""The one rule every DM written by an AI goes through before it is typed (decision of 18/10, q. 33).

A DM written by an AI holds 20 to 500 characters, is in the account's language (a reply may also be in
the language of the message it answers), carries no link,
e-mail address nor phone number unless the account's frame allows them, and none of the account's
forbidden terms. The cold DM, the DM reply and the welcome DM call `check_ai_dm_text` (or
`refuse_ai_dm_texts` for a list given up front) instead of each growing its own checks; the app sends
the frame in the `aiDmRules` block (`taktik/core/contract/ai_dm.py`), and checks a text before it
keeps it in a proposal through `check_ai_dm_texts`, by the tool bridge `ai_dm_check_bridge`.

Nothing here is new knowledge: the language of a text is the rule every text written by an AI goes
through (`language_outside`, `taktik/core/ai/written_language.py`: `detect_text_language`, and
letters of another script than the Latin one), the account's language is `resolve_base_language`,
the comments' rules. A text too short or too mixed for the detector passes the language rule (and
the log says so): refusing every short greeting would refuse the DMs the rule exists for.

The language of a reply (decision of 19/10): the account's or that of the message received, the same
`detect_text_language` on that message. A message too short to be recognised allows the account's
language only. A cold DM and a welcome DM answer nobody: they stay in the account's language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from loguru import logger

from taktik.core.ai.comments.decisions import UNKNOWN_ACCOUNT_LANGUAGES, resolve_base_language
from taktik.core.ai.written_language import language_outside
from taktik.core.contract.ai_dm import (
    AI_DM_MAX_CHARS,
    AI_DM_MIN_CHARS,
    EMAIL,
    FORBIDDEN_TERM,
    LANGUAGE,
    LINK,
    PHONE,
    TOO_LONG,
    TOO_SHORT,
)
from taktik.core.shared.text import detect_text_language, fold_case_and_accents

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)
#: A link written in full, or a bare domain on a common ending (`maboutique.fr`, `bit.ly/x`). A word
#: glued to the next sentence ("merci.Bonne") is not a domain: its ending is not in the list.
_LINK = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|fr|be|ch|ca|de|es|it|pt|uk|us|eu|io|co|me|ly|gl|gg|tv|ai|app|dev"
    r"|shop|store|site|online|link|info|biz|xyz)\b(?:/\S*)?",
    re.IGNORECASE,
)
#: Digits with the separators a phone number is written with; one counts from 8 digits.
_PHONE_CANDIDATE = re.compile(r"(?:\+|\b00)?\d[\d \t.\-()/]{6,}\d")
_PHONE_MIN_DIGITS = 8


@dataclass(frozen=True)
class AiDmRules:
    """What one account's DMs written by an AI are held to.

    base_language    the account's language (`resolve_base_language`); None: unknown, French or
                     English only
    links_allowed    the frame lets a DM carry a link, an e-mail address or a phone number
    forbidden_terms  the account's forbidden terms
    """

    base_language: Optional[str] = None
    links_allowed: bool = False
    forbidden_terms: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AiDmRefusal:
    """Why one text is not sent: the rule (`reason`, one of `AiDmRefusalReason`) and the measure.

    `detail` is the measure written in English, for a model. The same measure is also given typed, for
    a screen to say it in its own language, by the rules that have one to give: `measure` and `limit`
    (the length of a text too short or too long, and the bound it broke), `term` (the forbidden term
    found). A rule with nothing to count (language, link, e-mail address, phone number) gives none.
    """

    reason: str
    detail: str
    #: Its rank in the list it came in, from 1; None for a single text.
    index: Optional[int] = None
    measure: Optional[int] = None
    limit: Optional[int] = None
    term: Optional[str] = None

    def describe(self) -> str:
        """For a person or a model: `message 2: 612 characters, 500 at most`."""
        return f"message {self.index}: {self.detail}" if self.index is not None else self.detail

    def as_line(self) -> Dict[str, Any]:
        """The `textRefusal` of a bridge line (`AiDmTextRefusal`)."""
        line: Dict[str, Any] = {"reason": self.reason, "detail": self.detail}
        for key in ("index", "measure", "limit", "term"):
            value = getattr(self, key)
            if value is not None:
                line[key] = value
        return line


class AiDmTextRefused(ValueError):
    """A run refused before the phone is touched: a text written by an AI breaks the rule."""

    def __init__(self, refusal: AiDmRefusal):
        super().__init__(f"Text refused: {refusal.describe()}")
        self.refusal = refusal


def ai_dm_rules_from_payload(block: Any) -> AiDmRules:
    """The rules an `aiDmRules` block describes; absent, the most prudent (no link, no forbidden
    term declared, the account's language unknown). A block that is not an object is refused."""
    if block is None:
        return AiDmRules()
    if not isinstance(block, Mapping):
        raise ValueError(f"aiDmRules: an object is expected, got {type(block).__name__}")
    terms = block.get("forbiddenTerms")
    if terms is None:
        terms = ()
    if not isinstance(terms, (list, tuple)) or not all(isinstance(term, str) for term in terms):
        raise ValueError("aiDmRules.forbiddenTerms: a list of texts is expected")
    return AiDmRules(
        base_language=resolve_base_language(block.get("accountProfile")),
        links_allowed=block.get("linksAllowed") is True,
        forbidden_terms=tuple(term.strip() for term in terms if term.strip()),
    )


def check_ai_dm_text(
    text: Optional[str], rules: AiDmRules, received_text: Optional[str] = None
) -> Optional[AiDmRefusal]:
    """The first rule `text` breaks, or None when it may be sent.

    `received_text` is the message a reply answers; given, its language is allowed besides the
    account's.

    In this order: its length, an e-mail address, a link, a phone number, a forbidden term, its
    language. The length counts the characters of the text without its surrounding spaces.
    """
    body = (text or "").strip()
    if len(body) < AI_DM_MIN_CHARS:
        return AiDmRefusal(TOO_SHORT, f"{len(body)} characters, {AI_DM_MIN_CHARS} at least",
                           measure=len(body), limit=AI_DM_MIN_CHARS)
    if len(body) > AI_DM_MAX_CHARS:
        return AiDmRefusal(TOO_LONG, f"{len(body)} characters, {AI_DM_MAX_CHARS} at most",
                           measure=len(body), limit=AI_DM_MAX_CHARS)
    if not rules.links_allowed:
        refusal = _contact_refusal(body)
        if refusal is not None:
            return refusal
    term = _forbidden_term_in(body, rules.forbidden_terms)
    if term is not None:
        return AiDmRefusal(FORBIDDEN_TERM, f"contains the forbidden term \"{term}\"", term=term)
    return _language_refusal(body, rules.base_language, received_text)


def check_ai_dm_texts(
    texts: Iterable[Any], rules: AiDmRules, received_text: Optional[str] = None
) -> List[AiDmRefusal]:
    """Every text of `texts` the rule refuses, in order, each with its rank (`index`, from 1); an
    empty list when all may be sent. A value that is not a text is refused as an empty one."""
    refusals: List[AiDmRefusal] = []
    for rank, text in enumerate(texts, start=1):
        refusal = check_ai_dm_text(text if isinstance(text, str) else None, rules, received_text)
        if refusal is not None:
            refusals.append(replace(refusal, index=rank))
    return refusals


def refuse_ai_dm_texts(texts: Iterable[Any], rules: AiDmRules, received_text: Optional[str] = None) -> None:
    """Raise `AiDmTextRefused` on the first of `texts` (given up front) the rule refuses; its rank
    is said when the list holds more than one text."""
    texts = list(texts)
    refusals = check_ai_dm_texts(texts, rules, received_text)
    if refusals:
        first = refusals[0]
        index = first.index if len(texts) > 1 else None
        raise AiDmTextRefused(replace(first, index=index))


def _contact_refusal(body: str) -> Optional[AiDmRefusal]:
    if _EMAIL.search(body):
        return AiDmRefusal(EMAIL, "contains an e-mail address")
    # An e-mail's domain is a link too: it is reported as the e-mail it is, above.
    link = _LINK.search(body)
    if link:
        return AiDmRefusal(LINK, f"contains a link ({link.group(0)[:60]})")
    for candidate in _PHONE_CANDIDATE.finditer(body):
        if sum(char.isdigit() for char in candidate.group(0)) >= _PHONE_MIN_DIGITS:
            return AiDmRefusal(PHONE, "contains a phone number")
    return None


def _forbidden_term_in(body: str, terms: Tuple[str, ...]) -> Optional[str]:
    """The first term found at the start of a word of `body`, case and accents aside."""
    folded = fold_case_and_accents(body)
    for term in terms:
        if re.search(r"(?<!\w)" + re.escape(fold_case_and_accents(term)), folded):
            return term
    return None


def _language_refusal(
    body: str, base_language: Optional[str], received_text: Optional[str] = None
) -> Optional[AiDmRefusal]:
    accepted = (base_language,) if base_language else UNKNOWN_ACCOUNT_LANGUAGES
    answered = detect_text_language(received_text)
    if answered is not None:
        accepted = (*accepted, answered)
    written = language_outside(body, accepted, "DM written by an AI")
    if written is None:
        return None
    wanted = " or ".join(dict.fromkeys(accepted))
    return AiDmRefusal(LANGUAGE, f"written in {written}, the account writes in {wanted}")


__all__ = [
    "AiDmRefusal",
    "AiDmRules",
    "AiDmTextRefused",
    "ai_dm_rules_from_payload",
    "check_ai_dm_text",
    "check_ai_dm_texts",
    "refuse_ai_dm_texts",
]
