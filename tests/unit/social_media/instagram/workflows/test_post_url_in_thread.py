"""Engaging a post's comment thread instead of the people behind it.

This loop publishes under other people's comments, so what it must never do is more
important than what it does: exceed its budget, answer itself, answer the same comment
twice, keep going after the session said stop, or invent text when no AI is attached.
"""

import types

from taktik.core.social_media.instagram.actions.business.workflows.post_url.in_thread import (
    engage_thread,
)


class _CommentAction:
    def __init__(self, like_ok=True):
        self.liked = []
        self.replied = []
        self._like_ok = like_ok

    def like_comment_in_thread(self, username):
        if not self._like_ok:
            return {'success': False, 'skipped_reason': 'already_liked'}
        self.liked.append(username)
        return {'success': True}

    def reply_to_comment_in_thread(self, username, text, reply_to_text='', ai_metadata=None):
        self.replied.append({'username': username, 'text': text,
                             'reply_to_text': reply_to_text, 'meta': ai_metadata})
        return {'success': True}


def _workflow(screens, comment_action=None, should_continue=None):
    """`screens` is a list of comment lists, handed out one per read."""
    served = {'i': 0}

    def _read(_device, _device_id=""):
        index = min(served['i'], len(screens) - 1)
        return list(screens[index])

    wf = types.SimpleNamespace(
        device=object(),
        logger=types.SimpleNamespace(
            debug=lambda *a, **k: None, info=lambda *a, **k: None,
            warning=lambda *a, **k: None, error=lambda *a, **k: None, success=lambda *a, **k: None,
        ),
        comment_business=comment_action if comment_action is not None else _CommentAction(),
        scroll_actions=types.SimpleNamespace(scroll_down=lambda: served.__setitem__('i', served['i'] + 1)),
        _is_comments_view_open=lambda: served['i'] < len(screens),
        _human_like_delay=lambda _kind: None,
        session_manager=(types.SimpleNamespace(should_continue=should_continue)
                         if should_continue else None),
    )
    wf._read = _read
    return wf


def _run(wf, monkeypatch, config):
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.common.comment_reading.read_visible_comments",
        wf._read,
    )
    return engage_thread(wf, config, {}, config.pop('_writer', None))


def _c(username, text="un vrai commentaire"):
    return {'username': username, 'text': text}


# ── Doing nothing unless asked ──────────────────────────────────────────────

def test_nothing_runs_when_no_in_thread_mode_is_on(monkeypatch):
    wf = _workflow([[_c("alice")]])
    out = _run(wf, monkeypatch, {})
    assert out == {'comment_likes': 0, 'replies': 0, 'seen': 0, 'skipped': 0}
    assert wf.comment_business.liked == []


# ── Liking ──────────────────────────────────────────────────────────────────

def test_visible_comments_are_liked_up_to_the_budget(monkeypatch):
    wf = _workflow([[_c("a"), _c("b"), _c("c"), _c("d")]])
    out = _run(wf, monkeypatch, {'like_comments': True, 'max_comment_likes': 2})
    assert out['comment_likes'] == 2
    assert wf.comment_business.liked == ["a", "b"]


def test_an_already_liked_comment_counts_as_skipped_not_as_a_like(monkeypatch):
    wf = _workflow([[_c("a")]], comment_action=_CommentAction(like_ok=False))
    out = _run(wf, monkeypatch, {'like_comments': True, 'max_comment_likes': 5})
    assert out['comment_likes'] == 0 and out['skipped'] == 1


def test_our_own_account_is_never_engaged(monkeypatch):
    """The operated account is usually the post author, or already in its own thread."""
    wf = _workflow([[_c("own.account"), _c("alice")]])
    out = _run(wf, monkeypatch, {
        'like_comments': True, 'max_comment_likes': 9, 'own_username': '@Own.Account',
    })
    assert wf.comment_business.liked == ["alice"]
    assert out['comment_likes'] == 1


def test_the_same_comment_is_never_handled_twice_across_screens(monkeypatch):
    """Scrolling re-shows rows; a person can also leave several comments, so identity is
    who + what, not who alone."""
    screens = [
        [_c("alice", "premier"), _c("bob", "hello")],
        [_c("bob", "hello"), _c("alice", "deuxieme")],  # bob repeated, alice's SECOND comment
    ]
    wf = _workflow(screens)
    out = _run(wf, monkeypatch, {'like_comments': True, 'max_comment_likes': 9})
    assert wf.comment_business.liked == ["alice", "bob", "alice"]
    assert out['comment_likes'] == 3


# ── Replying ────────────────────────────────────────────────────────────────

def test_a_reply_is_published_with_what_it_answers(monkeypatch):
    wf = _workflow([[_c("alice", "Ca marche en 1 mois ?")]])
    writer = lambda _u, _t: {'comment': 'oui carrement', 'model': 'm', 'cost_usd': 0.0002,
                             'reasoning': 'answers their question'}
    out = _run(wf, monkeypatch, {
        'reply_to_comments': True, 'max_comment_replies': 1, '_writer': writer,
        'source': 'https://instagram.com/p/x', 'post_author': 'own.account',
    })
    assert out['replies'] == 1
    published = wf.comment_business.replied[0]
    assert published['text'] == 'oui carrement'
    assert published['reply_to_text'] == 'Ca marche en 1 mois ?'
    assert published['meta']['model'] == 'm'
    assert published['meta']['post_url'] == 'https://instagram.com/p/x'
    assert published['meta']['post_author'] == 'own.account'


def test_a_comment_the_ai_declined_is_not_answered(monkeypatch):
    wf = _workflow([[_c("alice", "🔥🔥")]])
    out = _run(wf, monkeypatch, {
        'reply_to_comments': True, 'max_comment_replies': 3, '_writer': lambda _u, _t: None,
    })
    assert wf.comment_business.replied == []
    assert out['replies'] == 0 and out['skipped'] == 1


def test_no_ai_writer_means_no_text_is_ever_invented(monkeypatch):
    """Standalone, or AI off: the mode degrades to liking rather than publishing something."""
    wf = _workflow([[_c("alice")]])
    out = _run(wf, monkeypatch, {'reply_to_comments': True, 'like_comments': True,
                                 'max_comment_likes': 5})
    assert wf.comment_business.replied == []
    assert out['comment_likes'] == 1


def test_a_generator_that_raises_does_not_break_the_run(monkeypatch):
    def _boom(_u, _t):
        raise RuntimeError("provider down")

    wf = _workflow([[_c("alice")]])
    out = _run(wf, monkeypatch, {'reply_to_comments': True, 'max_comment_replies': 2,
                                 '_writer': _boom})
    assert out['replies'] == 0 and out['skipped'] == 1


def test_replies_stop_at_their_own_budget(monkeypatch):
    screens = [[_c("a", "1")], [_c("b", "2")], [_c("c", "3")], [_c("d", "4")]]
    wf = _workflow(screens)
    out = _run(wf, monkeypatch, {
        'reply_to_comments': True, 'max_comment_replies': 2,
        '_writer': lambda _u, _t: {'comment': 'merci'},
    })
    assert out['replies'] == 2
    assert len(wf.comment_business.replied) == 2


# ── Stopping ────────────────────────────────────────────────────────────────

def test_a_stopped_session_ends_the_thread_work_immediately(monkeypatch):
    wf = _workflow([[_c("a"), _c("b"), _c("c")]],
                   should_continue=lambda: (False, "Daily action budget reached"))
    out = _run(wf, monkeypatch, {'like_comments': True, 'max_comment_likes': 9})
    assert out['comment_likes'] == 0
    assert wf.comment_business.liked == []


def test_a_thread_that_closes_ends_the_loop_instead_of_scrolling_blind(monkeypatch):
    wf = _workflow([[]])
    wf._is_comments_view_open = lambda: False
    out = _run(wf, monkeypatch, {'like_comments': True, 'max_comment_likes': 5})
    assert out['seen'] == 0
