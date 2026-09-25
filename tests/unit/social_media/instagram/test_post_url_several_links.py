"""A post URL run over several links: each link fails on its own, and says why.

Kevin's rule: a link that cannot be worked is logged with its motive and the run goes on to the
next one, until the links run out. The run ends as `navigation_lost` only when NO link could be
reached.

Three defects this file pins down:
- a likers list (or comments thread) that did not open returned without a motive, and a run on
  that one link ended COMPLETED as "sources exhausted";
- the counts a post reported were the run's (one PostUrlBusiness serves every link), so the
  second link announced the first one's profiles as its own and the driver took them off the
  budget of the links still waiting;
- an unreachable link ended the whole run, whatever the links after it.
"""

import json

import pytest

import taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow as post_url_module
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import (
    POST_URL_DEFAULTS,
)
from taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow import (
    PostUrlBusiness,
)
from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons

URL_A = "https://www.instagram.com/p/DOxampleA/"
URL_B = "https://www.instagram.com/p/DOxampleB/"
URL_C = "https://www.instagram.com/p/DOxampleC/"


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(post_url_module.time, "sleep", lambda *_a, **_k: None)


class _Log:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def success(self, *a, **k): pass


class _Navigation:
    def __init__(self, reachable):
        self.reachable = set(reachable)
        self.calls = []

    def navigate_to_post_via_deep_link(self, url):
        self.calls.append(url)
        return url in self.reachable


class _StatsManager:
    """Counts the whole run, like the real one: nothing resets it between two links."""

    def __init__(self):
        self.counts = {'profiles_visited': 0, 'likes': 0, 'follows': 0, 'comments': 0,
                       'stories_watched': 0, 'errors': 0}

    def display_final_stats(self, **_k):
        pass

    def add_error(self, _message):
        self.counts['errors'] += 1

    def to_dict(self):
        return dict(self.counts)


class _PostUrl(PostUrlBusiness):
    """The workflow with its screen stubbed: `reachable` links open, `listless` ones open on a
    post whose likers list never opens, `authorless` ones on a screen without an author."""

    def __init__(self, reachable=(), listless=(), authorless=(), visits_per_post=2):
        self.default_config = dict(POST_URL_DEFAULTS)
        self.logger = _Log()
        self.nav_actions = _Navigation(reachable)
        self.session_manager = None
        self.automation = None
        self.stats_manager = _StatsManager()
        self.ui_extractors = type('U', (), {'extract_likes_count_from_ui': lambda self, is_reel: 120})()
        self.listless = set(listless)
        self.authorless = set(authorless)
        self.visits_per_post = visits_per_post
        self.current = None
        self.lists_walked = []

    def _validate_instagram_url(self, url):
        self.current = url
        return super()._validate_instagram_url(url)

    def _is_reel_post(self):
        return False

    def _extract_author_username(self):
        return None if self.current in self.authorless else "author_one"

    def _open_likers_popup(self, is_reel):
        return self.current not in self.listless

    def _open_comments_view(self):
        return self.current not in self.listless

    def _interact_with_likers_list(self, stats, effective_config, max_interactions,
                                   source_type, source_name, list_source=None):
        self.lists_walked.append(source_name)
        visits = min(self.visits_per_post, max_interactions)
        self.stats_manager.counts['profiles_visited'] += visits
        self.stats_manager.counts['likes'] += visits
        stats['users_interacted'] = visits


# ─────────────────────────────────────────────────────── one post, its own motive

def test_a_likers_list_that_does_not_open_is_a_failure_of_that_post():
    workflow = _PostUrl(reachable=(URL_A,), listless=(URL_A,))

    result = workflow.interact_with_post_likers(URL_A, {}, finalize=False)

    assert getattr(result['link_failure'], 'code', None) == 'list_unavailable'
    assert getattr(result['stop_reason'], 'code', None) == 'list_unavailable'
    assert result['post_reached'] is True
    assert workflow.lists_walked == []


def test_a_comments_thread_that_does_not_open_is_a_failure_of_that_post():
    workflow = _PostUrl(reachable=(URL_A,), listless=(URL_A,))

    result = workflow.interact_with_post_likers(URL_A, {'source_mode': 'commenters'}, finalize=False)

    assert getattr(result['link_failure'], 'code', None) == 'list_unavailable'


def test_a_post_whose_author_cannot_be_read_was_not_reached():
    workflow = _PostUrl(reachable=(URL_A,), authorless=(URL_A,))

    result = workflow.interact_with_post_likers(URL_A, {}, finalize=False)

    assert getattr(result['link_failure'], 'code', None) == 'navigation_lost'
    assert not result.get('post_reached')


def test_a_link_that_does_not_open_says_so_to_the_driver():
    workflow = _PostUrl(reachable=())

    result = workflow.interact_with_post_likers(URL_A, {}, finalize=False)

    assert getattr(result['link_failure'], 'code', None) == 'navigation_lost'
    assert not result.get('post_reached')


def test_a_worked_post_is_no_link_failure():
    workflow = _PostUrl(reachable=(URL_A,))

    result = workflow.interact_with_post_likers(URL_A, {}, finalize=False)

    assert not result['link_failure']
    assert result['post_reached'] is True


def test_a_single_post_run_that_finalises_files_the_list_failure():
    workflow = _PostUrl(reachable=(URL_A,), listless=(URL_A,))
    finalized = []
    workflow.automation = type('A', (), {})()
    workflow.automation.helpers = type('H', (), {
        'finalize_session': lambda self, status='COMPLETED', reason='': finalized.append((status, reason)),
    })()

    workflow.interact_with_post_likers(URL_A, {}, finalize=True)

    status, reason = finalized[0]
    assert (status, getattr(reason, 'code', None)) == ('INTERRUPTED', 'list_unavailable')


# ─────────────────────────────────────────────────────── each post reports its own counts

def test_the_second_post_reports_its_own_profiles_not_the_runs():
    workflow = _PostUrl(reachable=(URL_A, URL_B), visits_per_post=2)

    first = workflow.interact_with_post_likers(URL_A, {}, finalize=False)
    second = workflow.interact_with_post_likers(URL_B, {}, finalize=False)

    assert first['users_interacted'] == 2
    assert second['users_interacted'] == 2
    assert second['likes_made'] == 2


# ─────────────────────────────────────────────────────── the run over several links


class _Helpers:
    def __init__(self, automation):
        self.automation = automation
        self.finalized = []

    def initialize_session(self):
        return 1591

    def finalize_session(self, status='COMPLETED', reason=''):
        self.finalized.append((status, reason))
        self.automation.session_finalized = True


class _SessionManager:
    def should_continue(self):
        return True, ''

    def get_delay_between_actions(self):
        return 0


def _automation(workflow, urls, budget=6):
    """InstagramAutomation without a device: the real runner and, for `run_workflow`, the real
    session loop."""
    automation = object.__new__(InstagramAutomation)
    automation.logger = _Log()
    automation.config = {'actions': [_step(urls, budget)]}
    automation.session_manager = _SessionManager()
    automation.update_session_manager_config = lambda: None
    automation.helpers = _Helpers(automation)
    automation.workflow_runner = WorkflowRunner(automation)
    automation.actions = type('Actions', (), {})()
    automation.actions.post_url_business = workflow
    automation.stats = {'likes': 0, 'follows': 0, 'comments': 0, 'interactions': 0}
    automation.session_finalized = False
    automation.current_session_id = 1591
    return automation


def _step(urls, budget=6):
    return {'type': 'post_url', 'post_urls': list(urls), 'max_interactions': budget}


def _run_step(automation, urls, budget=6):
    return automation.workflow_runner.run_workflow_step(_step(urls, budget))


def _progress_events(capsys):
    events = []
    for line in capsys.readouterr().out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('type') == 'source_progress':
            events.append(event)
    return events


def test_an_unreachable_link_hands_over_to_the_next_one():
    workflow = _PostUrl(reachable=(URL_B,))
    automation = _automation(workflow, (URL_A, URL_B))

    progressed = _run_step(automation, (URL_A, URL_B))

    assert workflow.nav_actions.calls == [URL_A, URL_B]
    assert workflow.lists_walked == [URL_B]
    assert progressed is True
    assert automation.helpers.finalized == []


def test_a_closed_list_hands_over_to_the_next_link_too():
    workflow = _PostUrl(reachable=(URL_A, URL_B), listless=(URL_A,))
    automation = _automation(workflow, (URL_A, URL_B))

    _run_step(automation, (URL_A, URL_B))

    assert workflow.lists_walked == [URL_B]
    assert automation.helpers.finalized == []


def test_the_run_ends_as_navigation_lost_only_when_no_link_was_reached():
    """The whole chain: workflow -> runner -> session loop."""
    workflow = _PostUrl(reachable=())
    automation = _automation(workflow, (URL_A, URL_B, URL_C))

    automation.run_workflow()

    assert workflow.nav_actions.calls == [URL_A, URL_B, URL_C]
    assert len(automation.helpers.finalized) == 1
    status, reason = automation.helpers.finalized[0]
    assert (status, getattr(reason, 'code', None)) == ('INTERRUPTED', 'navigation_lost')


def test_reached_links_whose_lists_never_open_end_as_list_unavailable():
    workflow = _PostUrl(reachable=(URL_A, URL_B), listless=(URL_A, URL_B))
    automation = _automation(workflow, (URL_A, URL_B))

    _run_step(automation, (URL_A, URL_B))

    status, reason = automation.helpers.finalized[0]
    assert (status, getattr(reason, 'code', None)) == ('INTERRUPTED', 'list_unavailable')


def test_one_worked_link_is_enough_for_the_run_to_end_normally():
    workflow = _PostUrl(reachable=(URL_B, URL_C), listless=(URL_B,))
    automation = _automation(workflow, (URL_A, URL_B, URL_C))

    _run_step(automation, (URL_A, URL_B, URL_C))

    assert workflow.lists_walked == [URL_C]
    assert automation.helpers.finalized == []


def test_each_failed_link_reaches_the_panel_with_its_motive(capsys):
    workflow = _PostUrl(reachable=(URL_B, URL_C), listless=(URL_B,))
    automation = _automation(workflow, (URL_A, URL_B, URL_C))

    _run_step(automation, (URL_A, URL_B, URL_C))

    done = {e['source']: e for e in _progress_events(capsys) if e['status'] == 'done'}
    assert done[URL_A]['failure_code'] == 'navigation_lost'
    assert done[URL_B]['failure_code'] == 'list_unavailable'
    assert 'failure_code' not in done[URL_C]


def test_every_link_gets_its_share_of_the_budget(capsys):
    """Balanced over three links, budget 6: two profiles each. The second link used to report
    the first one's profiles as well (4), which left nothing for the third."""
    workflow = _PostUrl(reachable=(URL_A, URL_B, URL_C), visits_per_post=2)
    automation = _automation(workflow, (URL_A, URL_B, URL_C), budget=6)

    _run_step(automation, (URL_A, URL_B, URL_C), budget=6)

    assert workflow.lists_walked == [URL_A, URL_B, URL_C]
    done = [e for e in _progress_events(capsys) if e['status'] == 'done']
    assert [e['processed'] for e in done] == [2, 2, 2]


def test_a_failed_link_leaves_its_budget_to_the_next_ones(capsys):
    workflow = _PostUrl(reachable=(URL_B, URL_C), visits_per_post=10)
    automation = _automation(workflow, (URL_A, URL_B, URL_C), budget=6)

    _run_step(automation, (URL_A, URL_B, URL_C), budget=6)

    running = {e['source']: e['quota'] for e in _progress_events(capsys) if e['status'] == 'running'}
    assert running == {URL_A: 2, URL_B: 3, URL_C: 3}
