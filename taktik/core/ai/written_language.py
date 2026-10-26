"""Is a text a model wrote in a language it was asked for? One rule for every such text the engine keeps.

A prompt asks a model for a language ("Write in English", "write the summary in French"), and the
model does not always obey. The audit of October 2026, on a month of real outputs: five comments out
of five that October asked in English came back French, and 363 profile summaries written in
French carried Chinese ideographs in the middle of a sentence ("sert de portfolio pour展示 son
style"). Nothing read the text that came back, so they were published, or stored and shown on the
profile card.

The comments and the replies (`ai/comments/generation.py`), the DMs (`ai/dm_rules.py`) and the
profile summaries (`classify_profile_niche`) ask this module, never their own copy of it. Two
readings, in this order:

- letters of another script than the Latin one (`letters_of_another_script`) when every language
  accepted is written in Latin letters: an ideograph or a Cyrillic letter in a French text is a
  model that drifted, not a word;
- the language the engine reads everywhere else (`detect_text_language`, the comments' caption,
  the DMs): a text it reads in a language that is not accepted is refused. A text it cannot tell
  (too short, too mixed, a language outside the six it reads) passes, and the log says so:
  refusing every short text would refuse the texts the rule exists for. The DM rule has said the
  same since 2026-10-18.
"""

from __future__ import annotations

from typing import Optional, Sequence

from loguru import logger

from taktik.core.shared.text import detect_text_language, letters_of_another_script

#: The languages the engine asks a model to write in that are written in Latin letters. Arabic, the
#: other language an account can declare (`COMMENT_LANG_ALIASES`), is not: when it is accepted,
#: the letters say nothing.
LATIN_SCRIPT_LANGUAGES = ("fr", "en", "es", "de", "it", "pt", "nl")


def language_outside(text: Optional[str], accepted: Sequence[str], what: str) -> Optional[str]:
    """What `text` is written in when it is in none of the `accepted` languages; None when it may be kept.

    `accepted` holds language codes ("fr", "en"); `what` names the text for the log ("comment for
    @x"). The answer says what was found, for a log or a refusal: a code the detector reads ("fr")
    or the letters of another script ("letters of another script (展示)").
    """
    codes = tuple(code for code in accepted if code)
    if codes and all(code in LATIN_SCRIPT_LANGUAGES for code in codes):
        foreign = letters_of_another_script(text)
        if foreign:
            return f"letters of another script ({foreign[:12]})"
    detected = detect_text_language(text)
    if detected is None:
        logger.info(f"{what}: language not recognised (too short, mixed or not one of the six read), kept")
        return None
    return None if detected in codes else detected


__all__ = ["LATIN_SCRIPT_LANGUAGES", "language_outside"]
