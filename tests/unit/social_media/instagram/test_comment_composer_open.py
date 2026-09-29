"""Comment composer detection — the bot must not try to click the comment button when
the composer is already open (cross-language, version-drift tolerant).

Caught on a real Lab run (IG v410 FR): `comment.open_and_type` failed 0/8 because the
screen was already in the comments thread (composer present) — there is no comment button
to click there. The fix: detect the open composer and type directly.
"""

import logging

from taktik.core.social_media.instagram.services.comment.action import CommentAction
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class _XPath:
    def __init__(self, exists):
        self._exists = exists

    @property
    def exists(self):
        return self._exists


class _Device:
    def __init__(self, exists):
        self._exists = exists
        self.last_query = None

    def xpath(self, query):
        self.last_query = query
        return _XPath(self._exists)


def _make(exists):
    # Bypass the heavy BaseBusinessAction.__init__ — we only exercise the detector.
    c = object.__new__(CommentAction)
    c.device = _Device(exists)
    c.post_selectors = POST_COMMENTS_SELECTORS
    c.logger = logging.getLogger("test_comment")
    return c


def test_composer_open_true_when_field_present():
    assert _make(True)._is_comment_composer_open() is True


def test_composer_open_false_when_absent():
    assert _make(False)._is_comment_composer_open() is False


def test_detector_queries_the_composer_indicators():
    c = _make(False)
    c._is_comment_composer_open()
    # The combined query is built from the dedicated composer indicators.
    assert "layout_comment_thread_edittext" in c.device.last_query
    assert "comment_composer" in c.device.last_query


def test_composer_indicators_are_specific_not_a_bare_edittext():
    inds = POST_COMMENTS_SELECTORS.comment_composer_indicators
    # contains() match tolerates v410's `_multiline` rename.
    assert any("layout_comment_thread_edittext" in s for s in inds)
    # Must NOT include a bare EditText catch-all (would false-positive on any text field).
    assert not any(s.strip() == "//android.widget.EditText" for s in inds)


def test_comment_field_selectors_match_v410_multiline_autocompletetextview():
    """Regression: IG v410 FR comment field is an AutoCompleteTextView with id
    `layout_comment_thread_edittext_multiline` and hint 'Rejoindre la conversation…' — the
    old EditText/exact-id/hint selectors all missed it, so the bot could never type a comment."""
    sels = POST_COMMENTS_SELECTORS.comment_field_selectors
    # The robust contains() on the thread-edittext id (matches base + _multiline, any class).
    robust = [s for s in sels if 'contains(@resource-id, "layout_comment_thread_edittext")' in s]
    assert robust, "missing the contains() selector that matches the _multiline field id"
    # It must be tried FIRST (most reliable, before broad EditText fallbacks).
    assert sels[0] == robust[0]
    # The composer is an AutoCompleteTextView — at least one selector targets that class.
    assert any('AutoCompleteTextView' in s for s in sels)
    # The v410 thread hint is covered too.
    assert any('Rejoindre la conversation' in s for s in sels)


# ── Share-sheet recovery: a mis-tap on "Send post" opens the Direct share sheet, which must be
#    backed out of so the workflow is never blocked. ──────────────────────────────────────────

class _ShareDevice:
    """Reports the share sheet as present until a back press dismisses it; counts back presses."""

    def __init__(self, present):
        self._present = present
        self.back_presses = 0

    def xpath(self, query):
        return _XPath(self._present)

    def press(self, key):
        self.back_presses += 1
        self._present = False  # a back press closes the bottom sheet


def _make_share(present):
    c = object.__new__(CommentAction)
    c.device = _ShareDevice(present)
    c.post_selectors = POST_COMMENTS_SELECTORS
    c.logger = logging.getLogger("test_comment")
    return c


def test_dismiss_share_sheet_when_open(monkeypatch):
    import taktik.core.social_media.instagram.services.comment.action as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    c = _make_share(True)
    assert c._dismiss_share_sheet_if_open() is True
    assert c.device.back_presses >= 1


def test_dismiss_share_sheet_noop_when_absent():
    c = _make_share(False)
    assert c._dismiss_share_sheet_if_open() is False
    assert c.device.back_presses == 0


def test_share_sheet_indicators_use_language_independent_direct_ids():
    inds = POST_COMMENTS_SELECTORS.share_sheet_indicators
    assert any("direct_private_share_container_view" in s for s in inds)
    assert any("direct_private_share_recipients_recycler_view" in s for s in inds)
    # No localized text — resource-id based, so it holds across languages.
    assert all("@text" not in s for s in inds)
