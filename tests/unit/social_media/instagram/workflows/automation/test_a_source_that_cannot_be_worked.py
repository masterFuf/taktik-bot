"""A source of a Target run that cannot be worked hands over to the next one.

Before: a private source, or one whose list did not open, ended its setup on `list_unavailable`, a
motive of the session, and the driver ended the whole run on it: the sources after it were never
opened. A source that cannot be worked now says so, in the log and on its line of the panel
(`source_progress`, `failure_code`), and the run goes on to the next source, which takes over its
budget as it would from a source run dry. A run none of whose sources could be worked ends on that
failure, never as a success. A source the search does not find (its answered results list it nowhere)
is one of these too. A navigation that fails otherwise (the app itself lost, a search still loading)
still ends the run, and so does a source that fails while the run's stop latch is up.

The real driver (`InstagramAutomation.interact_with_followers`) and the real opening of each source
(`_setup_direct_workflow`) run here, on a phone described account by account; only the walk of an
opened list is scripted.
"""

import json
from types import SimpleNamespace

import pytest
from loguru import logger

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.atomic.navigation.search_results import (
    ProfileNavigationFailure,
    ProfileNavigationFailureReason,
)
from taktik.core.social_media.instagram.actions.base.stats import create_workflow_stats
from taktik.core.social_media.instagram.workflows.automation.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.automation.followers.workflows.direct.navigation_helpers import (
    DirectNavigationMixin,
)
from taktik.core.social_media.instagram.workflows.common.session import stop_reasons

PUBLIC, PRIVATE, LIST_CLOSED, UNREACHABLE = 'public', 'private', 'list_closed', 'unreachable'
#: The search answered and lists the account nowhere; the search was still loading.
NOT_FOUND, SLOW = 'not_found', 'slow'
_FAILURES = {
    NOT_FOUND: ProfileNavigationFailure('search', ProfileNavigationFailureReason.NOT_LISTED),
    SLOW: ProfileNavigationFailure('search', ProfileNavigationFailureReason.SEARCH_SLOW),
}


@pytest.fixture(autouse=True)
def _latch_lifted():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


class _Phone:
    """The accounts as the phone answers them, one state each."""

    def __init__(self, accounts):
        self.accounts = accounts
        self.on = None

    def navigate_to_profile(self, username, **kwargs):
        self.on = username
        self.nav.last_profile_navigation_failure = _FAILURES.get(self.accounts[username])
        return self.accounts[username] not in (UNREACHABLE, NOT_FOUND, SLOW)

    def open_list(self):
        return self.accounts[self.on] != LIST_CLOSED

    def profile_info(self, username, **kwargs):
        return {'is_private': self.accounts[username] == PRIVATE,
                'followers_count': 1200, 'following_count': 300, 'media_count': 40}


class _Sources(DirectNavigationMixin):
    """The real opening of each source on that phone; an opened list gives its whole quota."""

    def __init__(self, phone):
        self.logger = logger
        self.device = None
        self._human_like_delay = lambda kind: None
        self.walked = []
        self.nav_actions = SimpleNamespace(navigate_to_profile=phone.navigate_to_profile,
                                           open_followers_list=phone.open_list,
                                           open_following_list=phone.open_list,
                                           last_profile_navigation_failure=None)
        phone.nav = self.nav_actions
        self.profile_business = SimpleNamespace(get_complete_profile_info=phone.profile_info)

    def interact_with_followers_direct(self, target_username, max_interactions, config, account_id, finalize):
        stats = create_workflow_stats('followers_direct')
        followers_count, _ = self._setup_direct_workflow(target_username, stats, config or {}, 0, False)
        if followers_count is None:
            return stats
        self.walked.append((target_username, max_interactions))
        stats['processed'] = max_interactions
        return stats


class _Driver(InstagramAutomation):
    """The real driver method, on an object built only from what it touches."""

    def __init__(self, accounts):
        self.logger = logger
        self.active_account_id = 1
        self.session_finalized = False
        self.finalised = []
        self.sources = _Sources(_Phone(accounts))
        self.actions = SimpleNamespace(follower_business=self.sources)

    def _finalize_session(self, status='COMPLETED', reason=''):
        self.finalised.append((status, reason))


def _run(accounts, budget=20):
    driver = _Driver(accounts)
    driver.interact_with_followers(target_usernames=list(accounts), max_interactions=budget,
                                   config={'distribution': 'balanced'})
    return driver


def _source_lines(capsys):
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    return [line for line in lines if line.get('type') == 'source_progress' and line.get('status') == 'done']


@pytest.mark.parametrize('state', [PRIVATE, LIST_CLOSED])
def test_a_source_that_cannot_be_worked_hands_over_to_the_next(state, capsys):
    driver = _run({'first': state, 'second': PUBLIC})

    assert driver.sources.walked == [('second', 20)], "the next source never ran, or did not get the budget left"
    assert [(status, getattr(reason, 'code', reason)) for status, reason in driver.finalised] == [('COMPLETED', 'completed')]
    done = {line['source']: line.get('failure_code') for line in _source_lines(capsys)}
    assert done == {'first': 'list_unavailable', 'second': None}, done


def test_a_run_none_of_whose_sources_could_be_worked_ends_on_that_failure():
    driver = _run({'first': PRIVATE, 'second': LIST_CLOSED})

    assert driver.sources.walked == []
    assert [(status, getattr(reason, 'code', reason)) for status, reason in driver.finalised] == [
        ('INTERRUPTED', 'list_unavailable')]


def test_a_lost_navigation_still_ends_the_run():
    driver = _run({'first': UNREACHABLE, 'second': PUBLIC})

    assert driver.sources.walked == [], "a navigation lost by the app must not move on to the next source"
    assert [(status, getattr(reason, 'code', reason)) for status, reason in driver.finalised] == [
        ('INTERRUPTED', 'navigation_lost')]


def test_a_source_that_fails_under_a_raised_halt_ends_the_run():
    run_halt.demander_arret(run_halt.NETWORK_LOST, 'no route to the Internet')

    driver = _run({'first': PRIVATE, 'second': PUBLIC})

    assert driver.sources.walked == [], "the run went on while its stop latch was up"
    assert driver.finalised and driver.finalised[0][0] == stop_reasons.STATUS_INTERRUPTED


def test_a_source_the_search_does_not_find_hands_over_to_the_next(capsys):
    """Decision Q3 of the direct lot: an account not found is this source's failure, not the app's."""
    driver = _run({'first': NOT_FOUND, 'second': PUBLIC})

    assert driver.sources.walked == [('second', 20)]
    done = {line['source']: line.get('failure_code') for line in _source_lines(capsys)}
    assert done == {'first': 'source_not_found', 'second': None}, done


def test_a_slow_search_is_no_source_not_found_and_still_ends_the_run():
    driver = _run({'first': SLOW, 'second': PUBLIC})

    assert driver.sources.walked == []
    assert [(status, getattr(reason, 'code', reason)) for status, reason in driver.finalised] == [
        ('INTERRUPTED', 'navigation_lost')]
