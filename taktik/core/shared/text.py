"""Shared text primitives.

`detect_text_language` — a deterministic, dependency-free FR/EN language detector for short
social-media prose (post captions, comments, bios). It exists because the vision model's guess of
a post's language is unreliable (a French post whose image carries stylised English design text
gets misread as English), whereas the author's CAPTION is ground truth and right there in the UI.

Scope: reliably tells French from English and returns None when unsure (any other language, or too
little signal) so the caller can fall back to another signal. Not a general N-language classifier —
FR/EN is what the comment pipeline needs; extend the word sets to add a language.
"""

import re
from typing import Optional

# French letters with diacritics — an extremely strong French signal (English prose essentially
# never uses them outside rare loanwords). Weighted heavily below.
_FR_DIACRITICS = "àâäçéèêëîïôöùûüÿœæ"

# Discriminative function words. Kept to words that are FREQUENT and (mostly) unique to one of the
# two languages, so a handful of them in a caption tips the balance reliably. Overlap between the
# two sets is avoided on purpose.
_FR_WORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "où", "au", "aux",
    "pour", "avec", "dans", "sur", "sous", "par", "sans", "chez", "mais", "donc",
    "ne", "pas", "plus", "très", "trop", "ce", "cette", "ces", "cet", "qui", "que",
    "quoi", "dont", "vous", "nous", "je", "tu", "il", "elle", "ils", "elles", "on",
    "se", "sa", "son", "ses", "leur", "leurs", "mon", "ma", "mes", "ton", "ta", "tes",
    "notre", "votre", "vos", "nos", "est", "sont", "être", "avoir", "fait", "faire",
    "comme", "aussi", "bien", "tout", "tous", "toute", "toutes", "deux", "trois",
    "venez", "voir", "revoir", "découvrir", "moi", "toi", "oui", "merci", "bonjour",
    "salut", "alors", "encore", "déjà", "ici", "là", "vraiment", "toujours", "jamais",
    "parce", "quand", "chaque", "notamment", "cœur",
}

_EN_WORDS = {
    "the", "a", "an", "of", "and", "or", "to", "for", "with", "from", "at", "by",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "you", "we", "they", "he", "she", "it", "my", "your", "our", "their",
    "his", "her", "its", "so", "but", "not", "all", "more", "what", "which", "who",
    "when", "where", "how", "some", "any", "no", "yes", "thanks", "hello", "hi",
    "very", "just", "like", "love", "wish", "could", "would", "should", "can",
    "both", "sounds", "fun", "amazing", "beautiful", "about", "into", "over",
    "really", "always", "never", "here", "there", "because",
}

_WORD_RE = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœæ']+", re.IGNORECASE)


def detect_text_language(text: Optional[str]) -> Optional[str]:
    """Return 'fr' or 'en' when the text is confidently one of them, else None.

    Deterministic: diacritics + discriminative stop-word frequency. Returns None (rather than
    guessing) on too-short or ambiguous input, or any language other than FR/EN — the caller then
    keeps its own fallback (the vision guess, or the account's base language).
    """
    if not text:
        return None
    lowered = text.lower()
    words = _WORD_RE.findall(lowered)
    if len(words) < 2:
        return None

    fr_hits = sum(1 for w in words if w in _FR_WORDS)
    en_hits = sum(1 for w in words if w in _EN_WORDS)
    fr_diacritics = sum(1 for ch in lowered if ch in _FR_DIACRITICS)

    # Diacritics count strongly toward French; word hits count 1 each.
    fr_score = fr_hits + 1.5 * fr_diacritics
    en_score = float(en_hits)

    # Require a real signal AND a clear margin, otherwise stay undecided (None).
    if fr_score >= 2 and fr_score > en_score * 1.5:
        return "fr"
    if en_score >= 2 and en_score > fr_score * 1.5:
        return "en"
    return None


# Every apostrophe shape an Android app can render, folded onto the ASCII one. Instagram and
# TikTok render the TYPOGRAPHIC apostrophe (U+2019) in "S’abonner", "J’aime", "Don’t allow";
# selector catalogues and label lists are typed with the ASCII one. A raw comparison therefore
# never matched and the row was skipped IN SILENCE — no error, just nothing found.
_APOSTROPHES = {"\u2019": "'", "\u02bc": "'", "\u2032": "'", "\u00b4": "'", "\u0060": "'"}


def normalize_ui_label(value: Optional[str]) -> str:
    """Fold a UI label to a comparable form: trimmed, lowercased, apostrophes unified.

    Use this on BOTH sides of any comparison between a label we typed and a label the device
    rendered. Normalising both sides is the fix; adding "the curly variant too" to a catalogue
    only moves the trap to the next label someone types.
    """
    text = (value or "").strip().lower()
    for exotic, ascii_quote in _APOSTROPHES.items():
        text = text.replace(exotic, ascii_quote)
    return text


# A run of 2+ dots, or a single dot carrying an emoji variation selector. See
# ``text_lost_emoji`` for why that is the signature of a mangled emoji.
_MANGLED_EMOJI_RE = re.compile(r"\.{2,}|\.[︎️]")


def text_lost_emoji(text: Optional[str]) -> bool:
    """Return whether an XML-dumped text lost emoji to Android's XML sanitiser.

    UIAutomator serialises the hierarchy through AOSP's ``AccessibilityNodeInfoDumper``,
    whose ``stripInvalidXMLChars`` walks the string **one UTF-16 code unit at a time** and
    replaces anything outside the XML-legal ranges with ``"."``. UTF-16 surrogates are
    outside those ranges, so an astral emoji — which is a surrogate PAIR — comes back as
    exactly two dots, while a BMP symbol (heart, cloud, bullet: one code unit) survives.

    Measured on the local base: 9 490 bios hold a dot run, even-length runs outnumber odd
    ones 9.6 to 1, 828 runs are immediately followed by a variation selector (a character
    that only ever trails an emoji), and NOT ONE of those bios still contains an astral
    character — while 1 386 bios do carry BMP symbols intact.

    A real ellipsis ("great photographer...") also matches, which is why callers only use
    this as a hint to re-read the text through a channel that does not go through XML
    (JSON-RPC ``element.info['text']`` carries the real thing). Platform-agnostic: every
    uiautomator2 XML dump is scarred the same way, whatever the app.
    """
    return bool(text) and bool(_MANGLED_EMOJI_RE.search(text))


def text_is_truncated_utf16(text: Optional[str]) -> bool:
    """Return whether a text came back as a UTF-16 string truncated to its LOW bytes.

    A different scar from ``text_lost_emoji``, and a worse one. Something on the read path keeps
    only the low byte of each UTF-16 code unit and the result is re-decoded as UTF-8, so:

    - ``Cadeaux Personnalisés`` -> ``Cadeaux Personnalis\ufffds`` (the accent is GONE, not just
      the emoji);
    - ``\U0001F4CD Metz`` -> ``=\ufffd Metz`` (``0x3D`` = ``=`` is the low byte of ``\ud83d``,
      the first surrogate; the second becomes the replacement character).

    Both shapes were reproduced exactly with ``s.encode('utf-16-le')[::2].decode('utf-8', 'replace')``
    and both are in the base verbatim: 64 721 of 121 423 bios carry U+FFFD.

    The point of detecting it: a dotted bio has LOST its emoji but kept its accents, so it is
    strictly better than a truncated one. A caller re-reading a text through another channel must
    treat this as a failed read and keep what it had.

    U+FFFD never appears in text a person typed — it is by definition what a decoder writes when
    it gave up — so its presence alone is the signal.
    """
    return bool(text) and '\ufffd' in text
