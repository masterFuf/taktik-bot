"""Cleaning a post caption BEFORE it reaches the comment-writing model.

The caption the UI hands us is not the author's words: it is rendered text. Measured on the
556 AI comments stored locally: 89% start with the author's handle glued to the prose, 72.7%
end with the localized collapse control ("moins"/"less") the expander leaves in the text,
15% still carry the "… plus"/"… more" truncation marker, and 8.3% are dot runs — an
emoji-only caption after the XML dump ate the emoji (see `text_lost_emoji`). Every one of
those artifacts was sent to the model as if the author had written it; the dot runs are how
the model ended up INVENTING a subject to praise.

Pure functions — no device, no dump. The UI words come from the centralized feed selectors,
never inlined here.
"""

from dataclasses import dataclass
from typing import Optional

from taktik.core.shared.behavior.dwell import caption_prose_text
from taktik.core.shared.text import text_lost_emoji

from ...ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS

# Below this many characters of actual prose (after cleaning), a caption carries nothing a
# comment can anchor to — the model would write from thin air, which reads as fake. The
# 8.3% invented comments in the stored corpus all sat under this bar.
MIN_CAPTION_SUBSTANCE_CHARS = 12


@dataclass
class CleanCaption:
    """A caption reduced to the author's actual words, plus what was learned cleaning it."""

    text: str                       # the prose itself, UI chrome stripped
    author_prefix: Optional[str]    # leading handle the UI glued on (None if none)
    truncated: bool                 # still ends with the "… plus"/"… more" marker (expand failed)
    mangled: bool                   # dot-scarred by the XML dump (emoji eaten, prose lost)

    @property
    def has_substance(self) -> bool:
        """Whether there is enough real prose to ground a comment on.

        Hashtags, mentions and URLs are not prose: a caption reading
        "#Ornevy #LivrePhoto #Souvenirs #EntrepreneuriatFéminin" says nothing a comment can
        honestly react to (seen in a real run — only the vision analysis of the image saved
        that one). Dots are dropped too: they are what the XML dump leaves of an emoji.
        """
        prose = caption_prose_text(self.text)
        prose = "".join(ch for ch in prose if ch not in ".…·").strip()
        return len(prose) >= MIN_CAPTION_SUBSTANCE_CHARS


def _looks_like_handle(token: str, author_hint: Optional[str]) -> bool:
    """Whether a caption's first token is a handle, not a first word of prose.

    A token matching the known author is always a handle. Otherwise require a strong handle
    signal — a digit, a dot or an underscore — so a caption that genuinely starts with a
    lowercase word ("incroyable soirée…") never loses its first word. Collab/repost captions
    start with the ORIGINAL author's handle (11% of the stored corpus), which is why the
    author match alone is not enough.
    """
    if not token or len(token) > 30:
        return False
    if author_hint and token.lower() == author_hint.lower():
        return True
    if not all(ch.isalnum() or ch in "._" for ch in token):
        return False
    return any(ch.isdigit() or ch in "._" for ch in token) and token == token.lower()


def clean_post_caption(raw: Optional[str], author_hint: Optional[str] = None) -> CleanCaption:
    """Strip the UI chrome off a rendered caption: leading handle, trailing expander words.

    `author_hint` is the handle the caption is expected to start with (the post author from
    the framed header, or the target profile).
    """
    text = " ".join((raw or "").split())
    author_prefix = None

    first, _, rest = text.partition(" ")
    if _looks_like_handle(first, author_hint):
        author_prefix, text = first, rest.strip()

    truncated = False
    for suffix in FS.caption_expand_suffixes + FS.caption_collapse_suffixes:
        if text.endswith(suffix):
            truncated = suffix in FS.caption_expand_suffixes
            text = text[: -len(suffix)].rstrip()
            break
    if text.endswith(("…", "...")):
        truncated = True

    return CleanCaption(
        text=text,
        author_prefix=author_prefix,
        truncated=truncated,
        mangled=text_lost_emoji(text),
    )


__all__ = ["CleanCaption", "clean_post_caption", "MIN_CAPTION_SUBSTANCE_CHARS"]
