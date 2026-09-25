"""Persona Analysis — owner writing-style line extraction (pure, no device).

`owner_lines_from_comment_descs` keeps only the comment rows authored by the analyzed account
(its own voice), stripping the leading author handle from the row content-desc. This is the pure
core of the writing-style enrichment folded into persona analysis; on-device row reading + reply
expansion are validated separately on real dumps.
"""

from bridges.instagram.analysis.runtime.persona_comments import (
    owner_lines_from_comment_descs,
)
from bridges.instagram.analysis.runtime.persona_posts import comment_count_signal


def test_comment_count_signal():
    # None -> unknown (caller opens the sheet anyway)
    assert comment_count_signal("") is None
    assert comment_count_signal(None) is None
    assert comment_count_signal("Comments") is None
    # 0 -> no comments (skip the sheet)
    assert comment_count_signal("0") == 0
    assert comment_count_signal("0 comments") == 0
    # any non-zero digit (incl. abbreviated) -> has comments
    assert comment_count_signal("1") == 1
    assert comment_count_signal("42 comments") == 1
    assert comment_count_signal("1.2k") == 1
    assert comment_count_signal("View all 128 comments") == 1


def test_keeps_only_owner_rows_and_strips_handle():
    pairs = [
        ("someone great post!", "someone"),
        ("prospect merci beaucoup 😊", "prospect"),
        ("fan love it", "fan"),
        ("prospect trop gentil !", "prospect"),
    ]
    lines = owner_lines_from_comment_descs(pairs, "@Prospect")
    assert lines == ["merci beaucoup 😊", "trop gentil !"]


def test_dedup_and_length_bounds():
    pairs = [
        ("me hello", "me"),
        ("me hello", "me"),          # duplicate
        ("me ok", "me"),             # text too short (<3 after strip)
        ("me " + "x" * 300, "me"),   # too long
        ("me a real sentence here", "me"),
    ]
    lines = owner_lines_from_comment_descs(pairs, "me")
    assert lines == ["hello", "a real sentence here"]


def test_cross_post_dedup_via_shared_seen():
    seen: set = set()
    a = owner_lines_from_comment_descs([("me same line", "me")], "me", seen=seen)
    b = owner_lines_from_comment_descs([("me same line", "me")], "me", seen=seen)
    assert a == ["same line"]
    assert b == []


def test_only_strips_leading_author_occurrence():
    # The handle may legitimately reappear inside the text; strip only the leading author token.
    pairs = [("me tag me in the next one", "me")]
    lines = owner_lines_from_comment_descs(pairs, "me")
    assert lines == ["tag me in the next one"]


def test_empty_when_no_owner_or_no_match():
    assert owner_lines_from_comment_descs([("x hi there", "x")], "") == []
    assert owner_lines_from_comment_descs([], "me") == []
    assert owner_lines_from_comment_descs([("x hello", "x")], "me") == []


def test_visible_comment_texts_reads_the_comment_bodies():
    """The method named a catalogue it never imported: the NameError was swallowed and it always
    returned an empty list, on the id path and the dump path alike."""
    from types import SimpleNamespace

    from bridges.instagram.analysis.runtime.persona_comments import PersonaCommentsMixin

    class _Node:
        def __init__(self, text):
            self._text = text

        def get_text(self):
            return self._text

    reader = PersonaCommentsMixin()
    reader.device = SimpleNamespace(
        xpath=lambda _selector: SimpleNamespace(all=lambda: [_Node("first body"), _Node("second body")]))
    assert reader._visible_comment_texts() == ["first body", "second body"]
