"""The Feed comments only with a text of its own: an AI comment or one of the operator's.

Kevin (2026-09-25): without AI and without custom comments, the Feed posts no comment at all.
It used to take one of the built-in templates ("🔥", "Great post!"...), and the same few fixed
comments on post after post are a trace of automation.

The rule lives in `CommentAction.comment_on_post(template_fallback=False)`, which the Feed's
comment (`_comment_feed_post`) passes. The AI comment hook forwards it, so a failed generation
does not fall back on a template either. The hashtag and post URL comments keep the template
fallback (default `True`); the difference is reported, not changed here.
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
        self.comment_templates = {'generic': ['Template comment']}
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

    result = action.comment_on_post(custom_comments=[], username='bob', template_fallback=False)

    assert result['commented'] is False
    assert result['skipped'] is True
    assert result['skip_reason'] == 'no_comment_text'
    assert action.screen == [] and action.typed == []


def test_a_custom_comment_is_still_posted():
    action = _ScreenlessComment()

    result = action.comment_on_post(custom_comments=['Merci pour ce post'], username='bob',
                                    template_fallback=False)

    assert result['commented'] is True
    assert action.typed == ['Merci pour ce post']


def test_the_default_still_falls_back_on_a_template():
    """What the hashtag and post URL comments still do (reported, not changed)."""
    action = _ScreenlessComment()

    result = action.comment_on_post(username='bob')

    assert result['commented'] is True
    assert action.typed == ['Template comment']


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


def test_the_feed_comment_never_asks_for_a_template():
    feed = _Feed()

    feed._comment_feed_post('bob', {'custom_comments': []})

    assert feed.calls[0]['template_fallback'] is False
    assert feed.calls[0]['username'] == 'bob'


def test_the_feed_comment_uses_the_operator_texts_and_a_given_text():
    feed = _Feed()

    feed._comment_feed_post('bob', {'custom_comments': ['Superbe']})
    feed._comment_feed_post('bob', {}, comment_text='Texte de l IA')

    assert feed.calls[0]['custom_comments'] == ['Superbe']
    assert feed.calls[1]['comment_text'] == 'Texte de l IA'


# ─────────────────────────────────────────────────────────────── the AI comment hook

def test_the_ai_hook_forwards_the_no_template_rule_when_generation_fails(monkeypatch):
    """With smart comments on, a failed generation falls back on the wrapped action: it must get
    `template_fallback=False` too. The wrapper took six named arguments and raised TypeError on
    anything else."""
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

    CommentAction.comment_on_post(types.SimpleNamespace(), custom_comments=None, username='bob',
                                  template_fallback=False)

    assert original_calls and original_calls[-1].get('template_fallback') is False
