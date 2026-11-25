"""A post the account's excluded terms leave out gets neither like nor comment: the guard sits in the
like (`LikeOrchestration.like_framed_post`, `like_current_post`) and in the comment
(`CommentAction.comment_on_post`) themselves, so every workflow that likes or comments a post goes
through it.

The screen is a real home feed of Instagram 410 in French (Pixel 3a, 1080x2220), anonymized: the framed
post by `name_4` is shown whole, its caption untruncated (« name_7 name_8 name_9, name_10 la name_11
name_12 de name_13. »). `profile_posts_phone.py` replays it; a tap on a heart, or a double tap on the
post, likes it as Instagram does. The terms are the anonymizer's words, or invented.
"""

import pytest
from loguru import logger

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.base.base_business.term_exclusion as term_exclusion
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
import taktik.core.social_media.instagram.services.like.orchestration as orchestration
from profile_posts_phone import ProfilePostsPhone, ReplayScroll, capture, like_on_phone
from taktik.core.contract.shared import CAPTION, EXCLUDED_TERM, POST_EXCLUDED_TERM, USERNAME
from taktik.core.shared.filtering.excluded_terms import ExcludedTerms
from taktik.core.social_media.instagram.services.comment.action import CommentAction
from taktik.core.social_media.instagram.services.like.orchestration import FramedLike
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

WHOLE_POST = capture("ig410_fr_feed_two_captions.xml")
PIXEL_3A_H = 2220


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: False)
    set_active_locale("fr")
    yield
    set_active_locale(None)


@pytest.fixture
def said(monkeypatch):
    lines = []
    monkeypatch.setattr(term_exclusion.IPCEmitter, "emit_term_exclusion",
                        staticmethod(lambda *args: lines.append(args)))
    return lines


def _like(terms: ExcludedTerms):
    phone = ProfilePostsPhone(screen=WHOLE_POST, height=PIXEL_3A_H, likes_on_tap=True)
    like = like_on_phone(phone)
    like.session_manager.excluded_terms = terms
    return phone, like


def test_a_post_term_in_the_caption_leaves_the_post_unliked_and_untouched(said):
    phone, like = _like(ExcludedTerms(post_terms=("name_11",)))

    assert like.like_framed_post(record_as="name_4") is FramedLike.EXCLUDED

    assert phone.taps == [], "the post was touched"
    assert like.rows == [], "a like was filed"
    assert said == [(POST_EXCLUDED_TERM, "name_4", "name_11", CAPTION)]


def test_a_post_without_the_term_is_liked_as_before(said):
    phone, like = _like(ExcludedTerms(post_terms=("ame_11",)))

    assert like.like_framed_post(record_as="name_4") is FramedLike.LIKED

    assert [kind for kind, _x, _y in phone.taps] == ["tap"]
    assert said == []


def test_the_like_of_the_post_screen_refuses_a_post_whose_author_is_left_out(said):
    phone, like = _like(ExcludedTerms(profile_terms=("ame4",)))

    assert like.like_current_post(record_as="name_4") is FramedLike.EXCLUDED

    assert phone.taps == []
    assert said == [(EXCLUDED_TERM, "name_4", "ame4", USERNAME)]


def test_without_terms_the_like_reads_nothing_more(said):
    phone, like = _like(ExcludedTerms())
    like.scroll_actions.read_framed_caption = lambda: pytest.fail("a caption was read without post terms")

    assert like.like_framed_post(record_as="name_4") is FramedLike.LIKED
    assert said == []


def _comment(terms: ExcludedTerms):
    phone = ProfilePostsPhone(screen=WHOLE_POST, height=PIXEL_3A_H, likes_on_tap=True)
    like = like_on_phone(phone)
    comment = object.__new__(CommentAction)
    comment.device = like.device
    comment.logger = logger.bind(module="test_excluded_terms_at_the_like_and_comment")
    comment.scroll_actions = ReplayScroll(phone, like.device)
    comment.session_manager = like.session_manager
    comment.session_manager.excluded_terms = terms
    comment.default_config = {"comment_delay_range": (0, 0), "max_comment_length": 150,
                              "min_comment_length": 3, "capture_post_url": False}
    comment.opened = []
    comment._is_comment_composer_open = lambda: False
    # The sheet is not part of this capture: the comment stops at its button, the guard is before it.
    comment._click_comment_button = lambda: comment.opened.append("comment_button") or False
    return phone, comment


def test_a_post_term_in_the_caption_leaves_the_post_uncommented(said):
    phone, comment = _comment(ExcludedTerms(post_terms=("name_11",)))

    result = comment.comment_on_post(custom_comments=["Très belle photo"], username="name_4")

    assert result["commented"] is False and result["excluded"] is True
    assert result["skip_reason"] == POST_EXCLUDED_TERM
    assert comment.opened == [] and phone.taps == [], "the comment box was opened"
    assert said == [(POST_EXCLUDED_TERM, "name_4", "name_11", CAPTION)]


def test_a_post_without_the_term_goes_on_to_its_comment_button(said):
    _phone, comment = _comment(ExcludedTerms(post_terms=("ame_11",)))

    comment.comment_on_post(custom_comments=["Très belle photo"], username="name_4")

    assert comment.opened == ["comment_button"]
    assert said == []
