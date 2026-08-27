"""What a spent source is allowed to stop.

A run over several targets splits its budget between them. When target 1 runs out of
followers, the run must move to target 2 — the list ending says something about THAT list,
nothing about the session. Only a session-wide motive (the duration, a global cap, a lost
navigation) may cancel what the remaining targets were allotted.

Reproduced from a real run, 2026-08-21, `emergingartistsswitzerland` + `ernsttheproducer`:
two targets, the first ended on `end_of_list_repeated` after 25 minutes, the second was never
opened, and the session was filed COMPLETED with half its budget unspent.
"""

import pytest

from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


class _Logger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


class _FollowerBusiness:
    """Scripted per-target outcomes, in the shape the real workflow returns."""

    def __init__(self, outcomes):
        self.outcomes = dict(outcomes)
        self.targets_run = []

    def interact_with_followers_direct(self, target_username, max_interactions, config,
                                       account_id, finalize):
        self.targets_run.append(target_username)
        processed, stop_reason = self.outcomes.get(target_username, (0, ''))
        return {'processed': processed, 'stop_reason': stop_reason}


class _Driver(InstagramAutomation):
    """The real driver method, on an object built only from what it touches."""

    def __init__(self, outcomes):
        self.logger = _Logger()
        self.active_account_id = 1
        self.session_finalized = False
        self.finalised = []
        self.follower_business = _FollowerBusiness(outcomes)
        self.actions = type('_A', (), {'follower_business': self.follower_business})()

    def _finalize_session(self, status='COMPLETED', reason=''):
        self.finalised.append((status, reason))


@pytest.fixture(autouse=True)
def _no_ipc(monkeypatch):
    import taktik.core.social_media.instagram.workflows.core.automation as automation
    monkeypatch.setattr(automation, "ipc_source_progress", lambda kind: None)


def test_a_spent_source_hands_over_to_the_next_target():
    driver = _Driver({
        'first': (20, stop_reasons.end_of_list_repeated()),
        'second': (18, ''),
    })

    driver.interact_with_followers(
        target_usernames=['first', 'second'], max_interactions=60,
        config={'distribution': 'balanced'},
    )

    assert driver.follower_business.targets_run == ['first', 'second'], (
        "the first list ending cancelled the budget the second target was allotted"
    )


def test_a_session_motive_still_cancels_the_remaining_targets():
    """The other side: a duration cap means the SESSION is over, targets left or not."""
    driver = _Driver({
        'first': (20, stop_reasons.duration_cap(125)),
        'second': (18, ''),
    })

    driver.interact_with_followers(
        target_usernames=['first', 'second'], max_interactions=60,
        config={'distribution': 'balanced'},
    )

    assert driver.follower_business.targets_run == ['first'], (
        "the run kept spending budget after the session's own limit was reached"
    )
