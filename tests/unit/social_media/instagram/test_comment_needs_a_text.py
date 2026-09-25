"""A comment is an AI comment or one of the operator's, or nothing: the bot has no template.

Kevin (2026-09-24/25): without AI and without custom comments, no workflow posts a comment. The
bot used to take one of its built-in templates ("🔥", "Great post!"...), and the same few fixed
comments on post after post are a trace of automation. The Feed stopped first; the hashtag, post
URL and profile workflows followed, and the templates are gone. The operator's custom comments
stay usable without any AI key.
"""

import types

import pytest

from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
from taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions import (
    FeedPostActionsMixin,
)
from taktik.core.social_media.instagram.workflows.core.ai_hooks import install_instagram_ai_hooks


def _log():
    return types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )


class _ScreenlessComment(CommentAction):
    """The real action; every screen step records that it was reached and succeeds."""

    def __init__(self):
        self.logger = _log()
        self.default_config = {'comment_delay_range': (0, 0), 'max_comment_length': 150,
                               'min_comment_length': 1, 'capture_post_url': False}
        self.session_manager = None
        self.screen = []
        self.typed = []

    def _is_comment_composer_open(self):
        self.screen.append('composer?')
        return True

    def _dismiss_share_sheet_if_open(self):
        return False

    def _type_comment(self, text):
        self.typed.append(text)
        return True

    def _post_comment(self):
        return True

    def _stop_if_action_blocked(self, *_a, **_k):
        return False

    def _record_posted_comment(self, *_a, **_k):
        return None

    def _close_comment_popup(self):
        return True


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    import taktik.core.social_media.instagram.actions.business.actions.comment.action as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_a, **_k: None)


def test_without_a_text_the_comment_is_skipped_and_the_screen_untouched():
    action = _ScreenlessComment()

    result = action.comment_on_post(custom_comments=[], username='bob')

    assert result['commented'] is False
    assert result['skipped'] is True
    assert result['skip_reason'] == 'no_comment_text'
    assert action.screen == [] and action.typed == []


def test_a_custom_comment_is_still_posted():
    action = _ScreenlessComment()

    result = action.comment_on_post(custom_comments=['Merci pour ce post'], username='bob')

    assert result['commented'] is True
    assert action.typed == ['Merci pour ce post']


def test_no_argument_means_no_comment_not_a_template():
    """What the hashtag and post URL comments did by default until 2026-09-24."""
    action = _ScreenlessComment()

    result = action.comment_on_post(username='bob')

    assert result['commented'] is False
    assert result['skip_reason'] == 'no_comment_text'
    assert action.typed == []


# ─────────────────────────────────────────────────────────────── the Feed's comment

class _Feed(FeedPostActionsMixin):
    def __init__(self):
        self.calls = []
        feed = self

        class _CommentBusiness:
            def comment_on_post(self, **kwargs):
                feed.calls.append(kwargs)
                return {'commented': False, 'skipped': True}

        self.comment_business = _CommentBusiness()


def test_the_feed_comment_is_filed_under_its_author():
    feed = _Feed()

    feed._comment_feed_post('bob', {'custom_comments': []})

    assert feed.calls[0]['username'] == 'bob'
    assert 'template_fallback' not in feed.calls[0]


def test_the_feed_comment_uses_the_operator_texts_and_a_given_text():
    feed = _Feed()

    feed._comment_feed_post('bob', {'custom_comments': ['Superbe']})
    feed._comment_feed_post('bob', {}, comment_text='Texte de l IA')

    assert feed.calls[0]['custom_comments'] == ['Superbe']
    assert feed.calls[1]['comment_text'] == 'Texte de l IA'


# ─────────────────────────────────────────────────────────────── the AI comment hook

def test_a_failed_ai_generation_falls_back_on_the_custom_comments(monkeypatch):
    """With smart comments on, a failed generation hands over to the wrapped action with the
    operator's custom comments, and every other argument goes through (the wrapper once took six
    named arguments and raised TypeError on anything else)."""
    original_calls = []

    def _original(self_comment, **kwargs):
        original_calls.append(kwargs)
        return {'commented': False, 'skipped': True}

    monkeypatch.setattr(CommentAction, 'comment_on_post', _original)

    class _AI:
        def generate_smart_comment(self, **_kwargs):
            return {'success': False, 'error': 'provider down'}

        def analyze_post(self, **_kwargs):
            return {'success': False}

    class _Device:
        def screenshot(self):
            raise RuntimeError('no screen in a unit test')

    install_instagram_ai_hooks(ai=_AI(), ai_config={'smartComments': True}, device=_Device(),
                               language='fr', log=lambda *_a: None)

    CommentAction.comment_on_post(types.SimpleNamespace(), custom_comments=['Superbe'], username='bob',
                                  ai_metadata=None)

    assert original_calls and original_calls[-1]['custom_comments'] == ['Superbe']
    assert 'ai_metadata' in original_calls[-1]
    assert 'template_category' not in original_calls[-1]
