"""Comment composer detection — the bot must not try to click the comment button when
the composer is already open (cross-language, version-drift tolerant).

Caught on a real Lab run (IG v410 FR): `comment.open_and_type` failed 0/8 because the
screen was already in the comments thread (composer present) — there is no comment button
to click there. The fix: detect the open composer and type directly.
"""

import logging

from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
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
