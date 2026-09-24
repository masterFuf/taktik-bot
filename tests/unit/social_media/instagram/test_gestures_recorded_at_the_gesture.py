"""A gesture published on Instagram is counted and filed the moment it happens.

2026-09-24, hashtag run: a comment was sent and the run stopped six seconds later, while the
comments sheet was being closed. The comment action wrote its session counter, its ledger
row and its rich record only AFTER the post-comment pause and that close, so the session kept
no row at all and the comment escaped the session caps. The like of the same posts pass never
wrote anything but the live counter.
"""

import types

import pytest

from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)

COMMENT_MODULE = "taktik.core.social_media.instagram.actions.business.actions.comment.action"
LIKE_MODULE = "taktik.core.social_media.instagram.actions.business.actions.like.orchestration"


class _RunStopped(BaseException):
    """What a stop in the middle of the sheet close looks like to the action."""


def _log():
    return types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )


class _Session:
    def __init__(self):
        self.actions = []

    def record_action(self, action_type, success=True, source=None):
        self.actions.append(action_type)


@pytest.fixture
def ledger(monkeypatch):
    """What reaches posted_comments; the ledger rows are captured per action object."""
    rich = []
    monkeypatch.setattr(f"{COMMENT_MODULE}.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        f"{COMMENT_MODULE}.InstagramPostedComments.record",
        staticmethod(lambda **kw: rich.append(kw) or len(rich)),
    )
    return rich


def _comment_action(close=None):
    act = CommentAction.__new__(CommentAction)
    act.logger = _log()
    act.default_config = {'comment_delay_range': (0, 0), 'max_comment_length': 150,
                          'min_comment_length': 1, 'capture_post_url': False}
    act.comment_templates = {'generic': ['Superbe travail']}
    act.session_manager = _Session()
    act.rows = []
    act._record_action = lambda u, k, c=1, **kw: act.rows.append((u, k, kw.get('content')))
    act._get_account_id = lambda: 7
    act._get_session_id = lambda: 1586
    act._is_comment_composer_open = lambda: True
    act._click_comment_button = lambda: True
    act._dismiss_share_sheet_if_open = lambda: False
    act._type_comment = lambda _text: True
    act._post_comment = lambda: True
    act._is_comments_view_open = lambda: True
    act._human_like_delay = lambda _kind: None
    act._find_comment_reply_control = lambda _handle: (1, 2, 3, 4)
    act._ensure_reply_mention = lambda _h, _t: None
    act.device = types.SimpleNamespace(human_tap=lambda bounds, **_k: (bounds[0], bounds[1]))
    act._close_comment_popup = close or (lambda: True)
    return act


def _stopped_while_closing():
    raise _RunStopped()


# ─────────────────────────────────────────────────────────────── comments

def test_a_comment_is_filed_before_the_sheet_is_closed(ledger):
    """The run of 2026-09-24: stopped while closing the sheet, after the send."""
    act = _comment_action(close=_stopped_while_closing)

    with pytest.raises(_RunStopped):
        act.comment_on_post(comment_text="Superbe travail", username="author_one")

    assert act.session_manager.actions == ['comment_posts']
    assert act.rows == [("author_one", "COMMENT", "Superbe travail")]
    assert [r['target_username'] for r in ledger] == ["author_one"]
    assert ledger[0]['session_id'] == 1586


def test_a_comment_still_reports_itself_as_commented(ledger):
    """The key every caller reads (`commented`) and the one the Lab reads (`success`)."""
    result = _comment_action().comment_on_post(comment_text="Superbe travail", username="author_one")

    assert result['commented'] is True and result['success'] is True
    assert result['comment_id'] == 1


def test_a_comment_without_a_known_target_is_still_counted(ledger):
    act = _comment_action()

    act.comment_on_post(comment_text="Superbe travail", username=None)

    assert act.session_manager.actions == ['comment_posts']
    assert act.rows == [] and ledger == []


def test_a_comment_that_was_not_sent_is_not_filed(ledger):
    act = _comment_action()
    act._post_comment = lambda: False

    result = act.comment_on_post(comment_text="Superbe travail", username="author_one")

    assert result['commented'] is False
    assert act.session_manager.actions == [] and act.rows == [] and ledger == []


def test_a_reply_is_filed_before_the_sheet_is_closed(ledger):
    act = _comment_action(close=_stopped_while_closing)

    with pytest.raises(_RunStopped):
        act.reply_to_comment_in_thread("commenter_two", "Merci !")

    assert act.session_manager.actions == ['comment_posts']
    assert act.rows == [("commenter_two", "COMMENT", "Merci !")]
    assert ledger[0]['kind'] == 'reply'


# ─────────────────────────────────────────────────────────────── likes

def _like_action(monkeypatch, *, already_liked=False, button_ok=True):
    monkeypatch.setattr(f"{LIKE_MODULE}.should_double_tap_like", lambda: False)
    act = LikeOrchestration.__new__(LikeOrchestration)
    act.logger = _log()
    act.session_manager = _Session()
    act.rows = []
    act._record_action = lambda u, k, c=1, **kw: act.rows.append((u, k, c))
    act.detection_actions = types.SimpleNamespace(
        is_on_post_screen=lambda: True, is_post_liked=lambda: already_liked,
    )
    act.click_actions = types.SimpleNamespace(like_post=lambda: button_ok)
    return act


def test_a_post_like_given_its_author_leaves_a_ledger_row(monkeypatch):
    act = _like_action(monkeypatch)

    assert act.like_current_post(record_as="author_one") is True

    assert act.rows == [("author_one", "LIKE", 1)]
    assert act.session_manager.actions == ['like_posts']


def test_an_already_liked_post_is_no_gesture_and_no_row(monkeypatch):
    act = _like_action(monkeypatch, already_liked=True)

    assert act.like_current_post(record_as="author_one") is True

    assert act.rows == [] and act.session_manager.actions == []


def test_a_failed_like_is_not_filed(monkeypatch):
    act = _like_action(monkeypatch, button_ok=False)

    assert act.like_current_post(record_as="author_one") is False

    assert act.rows == [] and act.session_manager.actions == []


def test_the_profile_sequence_still_records_its_own_likes(monkeypatch):
    """No `record_as`: the profile path writes its likes in one batch at the end of the
    profile, so a row here would be a second one."""
    act = _like_action(monkeypatch)

    assert act.like_current_post() is True

    assert act.rows == [] and act.session_manager.actions == []


# ─────────────────────────────────────────────────────────────── the hashtag posts pass

def test_the_posts_pass_files_its_like_under_the_post_author(monkeypatch):
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag import workflow as mod

    monkeypatch.setattr(mod.random, 'randint', lambda a, b: a)
    calls = []
    host = mod.HashtagBusiness.__new__(mod.HashtagBusiness)
    host.logger = _log()
    host.like_business = types.SimpleNamespace(
        like_current_post=lambda record_as=None: calls.append(record_as) or True)
    host.stats_manager = types.SimpleNamespace(increment=lambda *_a, **_k: None)

    stats = {'likes_made': 0, 'comments_made': 0}
    host._engage_post_itself({'like_percentage': 100, 'comment_percentage': 0}, stats, "author_one")

    assert calls == ["author_one"]
    assert stats['likes_made'] == 1


def test_the_posts_pass_leaves_a_post_whose_author_it_cannot_read(monkeypatch):
    """No author: no ledger row, no deduplication, no cap. The gesture is not made."""
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag import workflow as mod

    monkeypatch.setattr(mod.random, 'randint', lambda a, b: a)
    calls = []
    host = mod.HashtagBusiness.__new__(mod.HashtagBusiness)
    host.logger = _log()
    host.like_business = types.SimpleNamespace(
        like_current_post=lambda record_as=None: calls.append(record_as) or True)
    host.comment_business = types.SimpleNamespace(
        comment_on_post=lambda **kw: calls.append('comment') or {'commented': True})
    host.stats_manager = types.SimpleNamespace(increment=lambda *_a, **_k: None)

    engaged = host._engage_post_itself(
        {'like_percentage': 100, 'comment_percentage': 100}, {'likes_made': 0, 'comments_made': 0}, None)

    assert engaged is False and calls == []
