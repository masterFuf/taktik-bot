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

    # It must rest on the SHEET PANEL, not on a label. This assertion used to say the opposite —
    # "the indicator must not rest on a build id" — and the label it forced was the composer
    # affordance, which belongs to the VIDEO screen. Measured on device 2026-08-30: sheet closed,
    # `is_comment_sheet_open()` answered True, `read_comments` returned the video's AUTHOR as a
    # commenter, and `open_comments` reported success without opening anything.
    #
    # The ids are obfuscated and will die on a version bump. That is the accepted trade, because
    # the failure direction is safe: when they go, the sheet reads as closed and every comment
    # action refuses — unlike the composer, which failed by saying yes.
    for selector in COMMENT_SELECTORS.sheet_indicator:
        assert "resource-id" in selector, selector
    for label in ("Mention", "Stickers"):
        assert not any(label in s for s in COMMENT_SELECTORS.sheet_indicator), (
            f"{label!r} is on the video screen too — as an indicator it never says no"
        )


def test_the_comment_body_is_scoped_to_its_own_row():
    """A bare `//TextView[@focusable="true"]` resolves on half the app — the inbox included.
    The body is the focusable TextView OF THE ROW whose author is a `title`."""
    for selector in COMMENT_SELECTORS.comment_text:
        assert ":id/title" in selector
        assert '@focusable="true"' in selector


def test_the_composer_is_anchored_on_its_hint_not_its_id():
    """The id moves between versions (`dpl` -> `egn`); the hint is identical on both. `contains`
    also steps over the U+2026 ellipsis TikTok appends.

    The last entry is the second reading: once text is typed the hint is GONE and the hint-based
    anchors read 0 — measured, and it matters, because the send check needs to find the field
    again to see it emptied."""
    assert COMMENT_SELECTORS.comment_input
    for selector in COMMENT_SELECTORS.comment_input:
        assert ":id/" not in selector, selector
    hint_based = [s for s in COMMENT_SELECTORS.comment_input if "@hint" in s or "@text" in s]
    typed = [s for s in COMMENT_SELECTORS.comment_input if "EditText" in s and "@hint" not in s]
    assert hint_based, "no way to find the composer while it is empty"
    assert typed, "no way to find the composer once it holds text"


def test_both_languages_are_carried_by_one_field():
    """Splitting an anchor per language does not work here: the resolver stops at the first
    selector that finds anything, and TikTok mixes languages on a French phone. Every localized
    field must offer both spellings at once."""
    # `sheet_indicator` is deliberately absent: it is language-NEUTRAL now (the sheet panel),
    # which is stronger than carrying both spellings.
    for field, fr_words, en_words in (
        (COMMENT_SELECTORS.post_comment_button, ("Mentionne",), ("Mention someone",)),
        (COMMENT_SELECTORS.reply_button, ("Répondre",), ("Reply",)),
        (COMMENT_SELECTORS.comment_input, ("Ajouter",), ("Add comment",)),
    ):
        joined = " ".join(field)
        assert any(w in joined for w in fr_words), joined
        assert any(w in joined for w in en_words), joined


def test_the_indicator_carries_both_apostrophe_shapes():
    """TikTok renders U+2019 on some screens and U+0027 on others; a selector naming only one
    matches NOTHING, silently. The repo has a guard for this — it caught this very field."""
    # Now on `post_comment_button`, which is where the mention affordance still anchors: the
    # send button carries an unresolved Android resource as its description, so it is addressed
    # by position AFTER that affordance.
    mention = [s for s in COMMENT_SELECTORS.post_comment_button if "Mentionne" in s]
    assert mention, "the French mention anchor is gone"
    for selector in mention:
        assert "quelqu'un" in selector and "quelqu’un" in selector, selector


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
