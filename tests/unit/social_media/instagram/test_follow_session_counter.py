"""A successful follow MUST feed the session counter, otherwise the per-session follow cap
is never enforced.

`SessionManager.should_continue()` gates `total_follows_limit` on `counters['follows']`, which
only `record_action('follow_user')` increments. The like and comment paths call it; the follow
path only called the DB/stats recorder, so real runs displayed `follows=0/7` for their whole
duration while four follows had actually landed. The cap was structurally
unenforceable — the run merely happened to stay under it.
"""

import types

from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
    InteractionEngineMixin,
)


class _Recorder:
    def __init__(self):
        self.actions = []

    def record_action(self, action_type, success=True, source=None):
        self.actions.append((action_type, success, source))


def _engine(follow_succeeds=True, session=None):
    """Minimal engine exposing only what _do_follow touches."""
    eng = object.__new__(InteractionEngineMixin)
    eng.logger = types.SimpleNamespace(
        info=lambda *a, **k: None, debug=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )
    eng.click_actions = types.SimpleNamespace(follow_user=lambda username: follow_succeeds)
    eng.session_manager = session
    eng._count_live = lambda *a, **k: None
    eng._record_action = lambda *a, **k: None
    eng._emit_follow_event = lambda *a, **k: None
    eng._handle_follow_suggestions_popup = lambda *a, **k: None
    return eng


def _plan(do_follow=True):
    return types.SimpleNamespace(do_follow=do_follow)


def test_successful_follow_increments_the_session_counter():
    session = _Recorder()
    eng = _engine(session=session)
    result = {}

    eng._do_follow("alice", _plan(), {"follow_button_state": "follow"}, result)

    assert result["follows"] == 1
    assert ("follow_user", True, "alice") in session.actions


def test_failed_follow_does_not_increment():
    session = _Recorder()
    eng = _engine(follow_succeeds=False, session=session)
    result = {}

    eng._do_follow("alice", _plan(), {"follow_button_state": "follow"}, result)

    assert not result.get("follows")
    assert session.actions == []


def test_already_following_does_not_increment():
    session = _Recorder()
    eng = _engine(session=session)
    result = {}

    eng._do_follow("alice", _plan(), {"follow_button_state": "following"}, result)

    assert not result.get("follows")
    assert session.actions == []


def test_follow_still_works_standalone_without_a_session_manager():
    # The open-source bot can run with no SessionManager injected: the counter call must be
    # best-effort and never break the follow itself.
    eng = _engine(session=None)
    result = {}

    eng._do_follow("alice", _plan(), {"follow_button_state": "follow"}, result)

    assert result["follows"] == 1
