"""The comment sheet, opened for the first time on 2026-08-29.

The catalogue that preceded this scored **0 of 6 on BOTH shipped versions**: `comment_input`,
`post_comment_button` and `comment_list` were guesses at Android-ish resource names TikTok does
not use. Nothing failed, because nothing had ever opened the sheet to find out.

Measured on two real sheets (3 comments on 43.1.4, 6 on 46.6.3), and — the half that decides
whether an anchor is an indicator — against every other captured screen.
"""

from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.comments import COMMENT_SELECTORS


def test_the_sheet_announces_itself_before_anything_is_read():
    """The gate exists because the author anchor is NOT comment-specific.

    `title` resolves 1 on the inbox and 1 on the feed. Reading rows without first proving the
    sheet is open returns a confident, wrong "comment" from whatever screen happens to be up —
    which is exactly the failure shape this catalogue is meant to end.
    """
    assert COMMENT_SELECTORS.sheet_indicator, "no way to tell the sheet is open"
    for selector in COMMENT_SELECTORS.sheet_indicator:
        assert "content-desc" in selector, "the indicator must not rest on a build id"


def test_the_comment_body_is_scoped_to_its_own_row():
    """A bare `//TextView[@focusable="true"]` resolves on half the app — the inbox included.
    The body is the focusable TextView OF THE ROW whose author is a `title`."""
    for selector in COMMENT_SELECTORS.comment_text:
        assert ":id/title" in selector
        assert '@focusable="true"' in selector


def test_the_composer_is_anchored_on_its_hint_not_its_id():
    """The id moves between versions (`dpl` -> `egn`); the hint is identical on both. `contains`
    also steps over the U+2026 ellipsis TikTok appends."""
    assert COMMENT_SELECTORS.comment_input
    for selector in COMMENT_SELECTORS.comment_input:
        assert "@hint" in selector or "@text" in selector
        assert ":id/" not in selector


def test_both_languages_are_carried_by_one_field():
    """Splitting an anchor per language does not work here: the resolver stops at the first
    selector that finds anything, and TikTok mixes languages on a French phone. Every localized
    field must offer both spellings at once."""
    for field in (COMMENT_SELECTORS.sheet_indicator,
                  COMMENT_SELECTORS.reply_button,
                  COMMENT_SELECTORS.comment_input):
        joined = " ".join(field)
        assert any(fr in joined for fr in ("Pouce", "Répondre", "Ajouter")), joined
        assert any(en in joined for en in ("Like", "Reply", "Add comment")), joined


def test_the_author_row_climbs_to_what_is_tappable():
    """The author name is not clickable on its own; opening a commenter's profile means tapping
    the row. Same climb the post grid and the search results use."""
    selectors = COMMENT_SELECTORS.author_row_for_name("Bob")
    assert 'ancestor::*[@clickable="true"][1]' in selectors[0]
    assert '@text="Bob"' in selectors[0]


def test_a_quote_in_a_display_name_cannot_break_the_expression():
    """Display names are arbitrary text; an unescaped double quote would truncate the XPath and
    silently match something else."""
    for selector in COMMENT_SELECTORS.author_row_for_name('He said "hi"'):
        assert selector.count('"') % 2 == 0
