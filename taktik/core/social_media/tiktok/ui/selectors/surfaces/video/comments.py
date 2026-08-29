"""UI selectors for the TikTok comment sheet.

Measured on both shipped versions on 2026-08-29, the first time this surface was ever opened.
The catalogue that preceded this file scored **0 of 6** on both — `comment_input`,
`post_comment_button` and `comment_list` were guesses at Android-ish resource ids
(`comment_input`, `post`, `comment_list`) that TikTok does not use.

The anchors below come from two real sheets (3 comments on 43.1.4, 6 on 46.6.3) and were checked
against every other captured screen, which is the half that decides whether an anchor is an
indicator or a decoration:

    anchor                     43.1.4 sheet   46.6.3 sheet   everywhere else
    comment like button              3              5              0
    header ("N commentaires")        1              1              0
    reply button                     3              5              0
    author (`title`)                 3              6         1 on the inbox AND the feed
    like count (`tv_like_count`)     0              4              0

So `title` is NOT comment-specific — it is a generic id TikTok reuses — and the row readers below
are only meaningful once `sheet_indicator` says the sheet is open. That gate is the contract, the
same way the follower-row readers are gated on being on the followers list.
"""

from typing import List
from dataclasses import dataclass, field

from ...locales import L


@dataclass
class CommentSelectors:
    """Selectors for the TikTok comment sheet."""

    # === Is the sheet open at all? ===
    #
    # The per-comment like button: content-desc, present on BOTH versions, and the only candidate
    # measured at zero on every non-sheet screen. Everything else here is read only after this
    # answers yes.
    @property
    def sheet_indicator(self) -> List[str]:
        return L("comment.sheet_indicator")

    # === One comment ===
    #
    # `title` carries the AUTHOR. It resolves on the inbox and the feed too, so these two fields
    # are valid ONLY inside an open sheet -- see the module docstring.
    comment_author: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/title")]',
    ])

    #: The comment body: the focusable TextView of the row whose author is a `title`. Scoped to
    #: that row rather than taken bare, because `//TextView[@focusable="true"]` alone resolves on
    #: half the app.
    comment_text: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/title")]/../..'
        '//android.widget.TextView[@focusable="true"]',
    ])

    #: How many likes a comment has. `tv_like_count` is a READABLE id and clean everywhere, but it
    #: exists only on 46.6.3 and only on comments that have at least one like -- so an absent
    #: value means "no likes or old version", never "the sheet is not open".
    comment_like_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tv_like_count")]',
    ])

    @property
    def reply_button(self) -> List[str]:
        return L("comment.reply_button")

    #: The row to tap to open its author's profile — what `post_url` would need, TikTok having no
    #: public likers list. The author name is not clickable on its own row in every version, so
    #: the tap target is the nearest clickable ancestor, the same climb the post grid uses.
    def author_row_for_name(self, display_name: str) -> List[str]:
        escaped = str(display_name or "").replace('"', "")
        return [
            f'//*[contains(@resource-id, ":id/title")][@text="{escaped}"]'
            '/ancestor::*[@clickable="true"][1]',
            f'//*[contains(@resource-id, ":id/title")][@text="{escaped}"]',
        ]

    # === Composer ===
    @property
    def comment_input(self) -> List[str]:
        return L("comment.comment_input")

    @property
    def post_comment_button(self) -> List[str]:
        return L("comment.post_comment_button")

    @property
    def close_button(self) -> List[str]:
        return L("comment.close_button")

    # === The header, which also carries the total ===
    @property
    def comment_count_header(self) -> List[str]:
        return L("comment.comment_count_header")


COMMENT_SELECTORS = CommentSelectors()
