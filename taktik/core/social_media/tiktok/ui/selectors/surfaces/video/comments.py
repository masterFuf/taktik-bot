"""UI selectors for the TikTok comment sheet.

Measured on both shipped versions on 2026-08-29, the first time this surface was ever opened.
The catalogue that preceded this file scored **0 of 6** on both — `comment_input`,
`post_comment_button` and `comment_list` were guesses at Android-ish resource ids
(`comment_input`, `post`, `comment_list`) that TikTok does not use.

The anchors below come from two real sheets (3 comments on 43.1.4, 6 on 46.6.3) and were checked
against every other captured screen, which is the half that decides whether an anchor is an
indicator or a decoration:

    anchor                     43.1.4 sheet   46.6.3 sheet   empty sheet   everywhere else
    composer affordance              1              1              1              0
    comment like button              3              5              0              0
    header ("N commentaires")        1              1              1              0
    reply button                     3              5              0              0
    author (`title`)                 3              6              0     1 on the inbox AND the feed
    like count (`tv_like_count`)     0              4              0              0

Two things that column of zeroes decided.

`title` is NOT comment-specific — it is a generic id TikTok reuses — so the row readers below are
only meaningful once `sheet_indicator` says the sheet is open. That gate is the contract, the same
way the follower-row readers are gated on being on the followers list.

And the gate itself is the COMPOSER, not a comment's like button. The like button scored just as
cleanly on full sheets and answers NO on an open-but-EMPTY one, which would have made the bot
refuse to comment on precisely the videos where a first comment is worth something.
"""

from typing import List
from dataclasses import dataclass, field

from ...locales import L


@dataclass
class CommentSelectors:
    """Selectors for the TikTok comment sheet."""

    # === Is the sheet open at all? ===
    #
    # The SHEET PANEL itself, one id per version. Measured 2026-08-30 across 59 captured screens:
    # it fires on all 9 sheets -- both versions, full, empty and mid-typing -- and on none of the
    # 50 others.
    #
    # Two anchors were tried before it and both were wrong in opposite directions.
    #
    # A comment's like button proved "there ARE comments", not "the sheet is open": it answers NO
    # on an open-but-empty sheet, so the bot would have refused to comment on exactly the videos
    # where a first comment is worth something.
    #
    # The COMPOSER affordance ("Mention someone" / "Stickers") replaced it and was worse, because
    # it never says no: the composer bar belongs to the VIDEO screen and is there whether or not
    # the sheet is up. Measured on device the same day -- sheet closed, `is_comment_sheet_open()`
    # answered True. Everything downstream then reads the video's own nodes as if they were a
    # comment: `read_comments` returned the video AUTHOR as a commenter, and `open_comments`
    # reported success without opening anything. An indicator that never says no is a decoration.
    #
    # These ids are obfuscated and will die on a version bump. That is accepted here and it is not
    # silent: when they go, the sheet reads as closed and every comment action refuses, which is
    # the safe direction -- unlike the composer, which failed by saying yes.
    _sheet_indicator_base: List[str] = field(default_factory=lambda: [
        # 46.6.3 — the panel from y=768 to the bottom of the screen.
        '//*[contains(@resource-id, ":id/o3y")]',
        '//*[contains(@resource-id, ":id/ieb")]',
        # 43.1.4 — the same panel, same geometry, other id.
        '//*[contains(@resource-id, ":id/maf")]',
        '//*[contains(@resource-id, ":id/h7t")]',
    ])

    @property
    def sheet_indicator(self) -> List[str]:
        return self._sheet_indicator_base + L("comment.sheet_indicator")

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

    #: The row that holds ONE comment: the author's `title` node, two levels up. Used to scope a
    #: read to a single comment instead of pairing two flat lists by index -- a comment with no
    #: body node yields no entry in the body list, and every pairing after it shifts by one, which
    #: attributes one person's words to the next person down. Measured on 46.6.3: the row carries
    #: author, body, date, the reply label and the like count, in that order.
    comment_row: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/title")]/../..',
    ])

    #: How many likes a comment has. `tv_like_count` is a READABLE id and clean everywhere, but it
    #: exists only on 46.6.3 and only on comments that have at least one like -- so an absent
    #: value means "no likes or old version", never "the sheet is not open".
    comment_like_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tv_like_count")]',
    ])

    # === One comment, read inside its own row ===

    def author_at(self, anchor: str, index: int) -> List[str]:
        """The author node of the row at `index` (0-based), addressed positionally.

        `anchor` is whichever entry of `comment_author` resolved on this screen -- the package
        name differs between the musically and trill builds, and a positional xpath built on a
        selector that finds nothing addresses no row at all.
        """
        return [f"({anchor})[{index + 1}]"]

    def body_at(self, anchor: str, index: int) -> List[str]:
        """The body of the row at `index`, and nothing else that row happens to render.

        The body is the row's focusable TextView -- the same structural rule `comment_text` uses,
        scoped to one row instead of collected flat across all of them. Taking "the first text
        after the author" instead looked simpler and was wrong twice: with the body absent it
        returns the date, and with the date absent too it returns the localized reply label.
        """
        return [f"({anchor})[{index + 1}]/../..//android.widget.TextView[@focusable=\"true\"]"]

    def like_count_at(self, anchor: str, index: int) -> List[str]:
        """The like count of the row at `index`. Absent means no likes or 43.1.4, never "shut"."""
        return [
            f"({anchor})[{index + 1}]/../..//*[contains(@resource-id, \":id/tv_like_count\")]"
        ]

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
    #
    # The hint-based anchors below find the input while it is EMPTY. Once text is typed the hint
    # is gone and they read 0 — measured, and it matters: a workflow types, then needs the input
    # again to check the field emptied after sending. `_comment_input_typed` is that second
    # reading. It is only valid inside an open sheet: a followers list and the search page each
    # have their own EditText.
    _comment_input_typed: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@clickable="true"]',
    ])

    @property
    def comment_input(self) -> List[str]:
        return L("comment.comment_input") + self._comment_input_typed

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
