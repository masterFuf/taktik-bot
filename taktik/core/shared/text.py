"""Shared text primitives.

`detect_text_language` — a deterministic, dependency-free language detector for short social-media
prose (post captions, comments, bios), in the six languages the comment pipeline can tell apart:
French, English, Spanish, German, Italian, Portuguese. The author's CAPTION is ground truth for a
post's language; the vision model's guess is not (a French post whose image carries stylised
English design text reads as English). Returns None when unsure (too little signal, a mixed text no
language clearly wins, any other language) so the caller keeps its own fallback.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import FrozenSet, Optional

#: Everything a UI can add and a dump can mangle.
_NON_ALNUM = re.compile(r"[^0-9a-z]+")

# French letters with diacritics — an extremely strong French signal (English prose essentially
# never uses them outside rare loanwords). Weighted heavily below. No umlaut: French does not write
# them, German does.
_FR_DIACRITICS = "àâçéèêëîïôùûÿœæ"

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

# The four other languages. Each list keeps the words it shares with French ("de", "la", "il"):
# they count for both and decide nothing between them. Left out: English words ("a", "no") and
# words French or English also write ("su", "ci", "foi", "dos", "ter", "onde", "agora", "hier",
# "tag", "dove", "ai", "são" of São Paulo), one of which is enough to take a short caption.
_ES_WORDS = {
    "el", "los", "las", "del", "al", "lo", "una", "unos", "unas", "uno", "con", "para", "por",
    "pero", "muy", "más", "como", "cómo", "qué", "cuando", "donde", "dónde", "porque", "también",
    "siempre", "nunca", "ahora", "aquí", "hoy", "gracias", "hola", "todo", "todos", "toda",
    "todas", "este", "esta", "esto", "estos", "estas", "eso", "esa", "ese", "hay", "está",
    "están", "estamos", "estoy", "somos", "fue", "ser", "tiene", "tienen", "tengo", "puede",
    "hacer", "mucho", "mucha", "muchos", "muchas", "nuestro", "nuestra", "nuestros", "nuestras",
    "vuestro", "sí", "nada", "algo", "otro", "otra", "nuevo", "nueva", "año", "años", "día",
    "días", "mejor", "desde", "hasta", "quiero", "vamos", "bueno", "buena", "feliz", "vida",
    "amigos",
    # shared with French
    "de", "la", "que", "un", "se", "tu", "son", "le", "les",
}

_DE_WORDS = {
    "und", "der", "die", "das", "ist", "nicht", "mit", "für", "ein", "eine", "einen", "einem",
    "einer", "eines", "ich", "wir", "sie", "auf", "zu", "den", "dem", "von", "auch", "wie",
    "noch", "nur", "wenn", "oder", "aber", "sich", "bei", "nach", "aus", "unser", "unsere",
    "unseren", "unserem", "unserer", "heute", "mehr", "sehr", "schon", "jetzt", "immer", "alle",
    "diese", "dieser", "dieses", "diesem", "euch", "uns", "mein", "meine", "meinen", "dein",
    "deine", "ihr", "ihre", "haben", "habe", "sind", "wird", "werden", "kann", "können", "gibt",
    "viel", "vielen", "dank", "danke", "neue", "neuen", "neues", "zum", "zur", "vom", "beim",
    "ins", "dass", "über", "schön", "jahr", "wieder", "unter", "durch", "ohne", "seit", "euer",
    "eure",
}

_IT_WORDS = {
    "di", "che", "è", "sono", "della", "delle", "degli", "dello", "del", "dei", "nel", "nella",
    "nelle", "nei", "alla", "alle", "al", "gli", "questo", "questa", "questi", "queste", "anche",
    "grazie", "molto", "molta", "più", "tutti", "tutto", "tutta", "tutte", "sempre", "quando",
    "ancora", "oggi", "ogni", "cosa", "nostro", "nostra", "nostri", "nostre", "vostro", "suo",
    "sua", "suoi", "loro", "stato", "stata", "essere", "hai", "abbiamo", "siamo", "mio", "mia",
    "uno", "una", "da", "dal", "dalla", "dai", "con", "ed", "ti", "bella", "bello", "buon",
    "buona", "nuova", "nuovo", "anni", "anno", "giorno", "vita", "amici", "perché", "qua", "sei",
    "siete", "fatto", "ciao",
    # shared with French
    "il", "la", "le", "un", "se", "tu", "ne", "ma", "qui",
}

_PT_WORDS = {
    "não", "uma", "umas", "para", "por", "pelo", "pela", "pelos", "pelas", "muito", "muita",
    "muitos", "muitas", "você", "vocês", "está", "estão", "estamos", "também", "obrigado",
    "obrigada", "isso", "isto", "esse", "essa", "este", "esta", "seu", "sua", "seus", "suas",
    "nosso", "nossa", "nossos", "nossas", "ao", "aos", "às", "ser", "tem", "têm", "mas", "como",
    "quando", "porque", "sempre", "aqui", "hoje", "dia", "dias", "vida", "todos", "todas",
    "tudo", "nada", "já", "só", "eu", "ele", "ela", "eles", "elas", "da", "das", "em", "na",
    "nas", "num", "numa", "é", "meu", "minha", "bem", "novo", "nova", "ano", "anos", "melhor",
    "fazer", "pra", "vamos", "gente", "feliz",
    # shared with French
    "de", "que", "se", "mais", "ou", "nos",
}


@dataclass(frozen=True)
class _Language:
    """What tells one language apart in a short social text."""

    code: str
    words: FrozenSet[str]
    #: Letters English never writes; each one weighs as much as one and a half words.
    letters: str


_FRENCH = _Language("fr", frozenset(_FR_WORDS), _FR_DIACRITICS)
_ENGLISH = _Language("en", frozenset(_EN_WORDS), "")
_OTHER_LANGUAGES = (
    _Language("es", frozenset(_ES_WORDS), "ñ¿¡áíóú"),
    _Language("de", frozenset(_DE_WORDS), "ßäöü"),
    _Language("it", frozenset(_IT_WORDS), "ìò"),
    _Language("pt", frozenset(_PT_WORDS), "ãõáíóú"),
)

#: The letters of all six languages, so a word does not stop at "á" ("está" is not the French "est").
_WORD_RE = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœæñáíóúãõìòß']+", re.IGNORECASE)

#: A language needs at least this many points...
_MIN_SCORE = 2
#: ...and this many times the points of its rival, or nothing is decided.
_MARGIN = 1.5


def _score(language: _Language, words: list, lowered: str) -> float:
    """One point per word of the language, one and a half per letter only it writes."""
    hits = sum(1 for word in words if word in language.words)
    letters = sum(1 for char in lowered if char in language.letters)
    return hits + 1.5 * letters


def _has_a_word_of_its_own(language: _Language, words: list) -> bool:
    """A word of this language that French and English do not have ("und", "más", "questo").

    Without one, its letters alone come from a proper noun (Zürich, Málaga, São Paulo), not from
    prose in that language.
    """
    return any(
        word in language.words and word not in _FR_WORDS and word not in _EN_WORDS
        for word in words
    )


def _french_or_english(fr_score: float, en_score: float) -> Optional[str]:
    """French against English: at least 2 points and one and a half times the other's."""
    if fr_score >= _MIN_SCORE and fr_score > en_score * _MARGIN:
        return "fr"
    if en_score >= _MIN_SCORE and en_score > fr_score * _MARGIN:
        return "en"
    return None


def detect_text_language(text: Optional[str]) -> Optional[str]:
    """Return 'fr', 'en', 'es', 'de', 'it' or 'pt' when the text is confidently one of them.

    Deterministic: function words and letters. French and English decide between themselves as
    they always did. The best of the four others takes the text only when it has a word of its
    own, at least 2 points, and one and a half times the points of French and of English;
    otherwise the French/English verdict stands. A mixed caption therefore stays with the
    language we write in unless the other one clearly dominates.

    No margin is asked BETWEEN the four others: Spanish and Portuguese share too many words to
    be told apart on a short caption, and for an account writing French or English any of them
    means the same thing — not a language it writes in. On a tie the first of the list wins
    (Spanish before Portuguese).

    Returns None (rather than guessing) on too-short or ambiguous input, or any other language —
    the caller then keeps its own fallback (the vision guess, or the account's base language).
    """
    if not text:
        return None
    lowered = text.lower()
    words = _WORD_RE.findall(lowered)
    if len(words) < 2:
        return None

    fr_score = _score(_FRENCH, words, lowered)
    en_score = _score(_ENGLISH, words, lowered)
    verdict = _french_or_english(fr_score, en_score)

    best_other, best_score = None, 0.0
    for language in _OTHER_LANGUAGES:
        if not _has_a_word_of_its_own(language, words):
            continue
        score = _score(language, words, lowered)
        if score > best_score:
            best_other, best_score = language.code, score

    if best_score >= _MIN_SCORE and best_score > max(fr_score, en_score) * _MARGIN:
        return best_other
    return verdict


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


def as_xml_dumped(text: Optional[str]) -> str:
    """What an XML dump will report for `text` — the projection, not a detection.

    `text_lost_emoji` answers "was this text scarred?". This answers the question a caller has
    when it holds BOTH sides: "if I type this, what will I read back?". Same AOSP rule, applied
    forwards: `stripInvalidXMLChars` walks UTF-16 code units and replaces each illegal one with
    a dot, so an astral character (a surrogate PAIR) becomes exactly two dots while every BMP
    character survives untouched.

    Measured on device 2026-08-30: typing `Bien vu 😂 vraiment` into a TikTok composer
    reads back as `Bien vu .. vraiment` — U+1F602 replaced by U+002E U+002E, nothing else moved.

    Why this exists. `CommentActions` confirmed its own typing with an exact equality between
    the text it sent and the text the dump reported. An AI-written comment almost always carries
    an emoji, so that equality could never hold: the comment was typed correctly, the check said
    it had failed, and the path returned False WITHOUT logging — the composer kept a draft nobody
    sent, and the run reported zero comments. Comparing through this projection is what makes the
    check answer the question it means to ask.
    """
    if not text:
        return ""
    return "".join(".." if ord(char) > 0xFFFF else char for char in text)


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

def fold_for_match(text: Optional[str]) -> str:
    """Strip a string down to what two readings of it will always agree on.

    Accent-folded, case-folded, and reduced to letters and digits. Everything a UI adds and a dump
    mangles disappears: spaces, punctuation, curly apostrophes, and emoji -- which the XML dump
    turns into pairs of dots anyway.

    Written once because it kept being written. It decides whether a post read twice is the same
    post, whether a caption matches a niche keyword, and whether the name in a conversation header
    is the person we meant to write to. That last one is what forced it into a shared home: the
    header reads `Cin(é)Club` where the handle is `cineclub_demo`, so a guard comparing them
    literally refuses to send a message to exactly the right person.

    NOT for handles that must stay distinct from one another: this folds `demo.2` and `demo2`
    together. Use it to recognise, never to key.
    """
    folded = unicodedata.normalize("NFKD", (text or "").casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return _NON_ALNUM.sub("", folded)


_HANDLE = re.compile(r"[A-Za-z0-9._]+")

#: Length bounds each platform puts on a handle; another platform gets the widest.
_HANDLE_LENGTHS = {"instagram": (1, 30), "tiktok": (2, 24)}


def is_platform_handle(value: Optional[str], platform: str = "instagram") -> bool:
    """Whether `value`, exactly as given, can be a handle on `platform`.

    Letters, digits, "." and "_" within the platform's bounds: no space, no control character, no
    accent, no emoji. Nothing is cleaned first, unlike `ActionUtils.is_valid_username`, which
    squeezes "Send message" into "sendmessage" and accepts it.
    """
    if not isinstance(value, str) or not _HANDLE.fullmatch(value):
        return False
    low, high = _HANDLE_LENGTHS.get(platform, (1, 30))
    return low <= len(value) <= high


def handle_from_screen_text(text: Optional[str], platform: str = "instagram") -> Optional[str]:
    """The handle a username node shows, or None when the node shows anything else.

    Removes only what a screen puts around a handle: surrounding spaces, the "@" prefix and
    invisible format characters (direction marks, joiners). A sentence, a display name or a button
    label is refused, never cleaned into a handle.
    """
    value = "".join(char for char in (text or "") if unicodedata.category(char) != "Cf").strip()
    if value.startswith("@"):
        value = value[1:]
    return value if is_platform_handle(value, platform) else None
