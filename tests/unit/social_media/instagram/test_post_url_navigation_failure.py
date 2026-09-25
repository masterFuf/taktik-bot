"""A post that was never reached ends the run as a failure, not as a post that ran dry.

Same defect as the hashtag workflow (fixed on 2026-09-24): when the deep link to the post
failed, the post URL workflow returned without a motive, the runner saw zero interactions,
and the session loop concluded "sources exhausted" -- filed COMPLETED. The operator read a
clean run that never opened the post.

Over several links, one unreachable link no longer ends the run: only a run where no link
could be reached ends on `navigation_lost` (see `test_post_url_several_links.py`).
"""

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

URL = "https://www.instagram.com/p/DOxample1/"
OTHER_URL = "https://www.instagram.com/p/DOxample2/"


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
    """Reaches the posts listed in `reachable`, fails on every other one."""

    def __init__(self, reachable=()):
        self.reachable = set(reachable)
        self.calls = []

    def navigate_to_post_via_deep_link(self, url):
        self.calls.append(url)
        return url in self.reachable


class _StatsManager:
    def display_final_stats(self, **_k):
        pass

    def to_dict(self):
        return {'profiles_visited': 1}


class _PostUrl(PostUrlBusiness):
    """The workflow with its screen reads stubbed and its likers loop replaced by a recorder."""

    def __init__(self, reachable=()):
        self.default_config = dict(POST_URL_DEFAULTS)
        self.logger = _Log()
        self.nav_actions = _Navigation(reachable)
        self.session_manager = None
        self.automation = None
        self.stats_manager = _StatsManager()
        self.ui_extractors = type('U', (), {'extract_likes_count_from_ui': lambda self, is_reel: 120})()
        self.lists_walked = []

    def _is_reel_post(self):
        return False

    def _extract_author_username(self):
        return "author_one"

    def _open_likers_popup(self, is_reel):
        return True

    def _interact_with_likers_list(self, stats, effective_config, max_interactions,
                                   source_type, source_name, list_source=None):
        self.lists_walked.append(source_name)
        stats['users_interacted'] = 1
        stats['stop_reason'] = stop_reasons.completed(1)


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


def _automation(workflow, urls=(URL,)):
    """InstagramAutomation without a device: the real run loop and the real runner."""
    automation = object.__new__(InstagramAutomation)
    automation.logger = _Log()
    automation.config = {'actions': [{
        'type': 'post_url', 'post_urls': list(urls), 'max_interactions': 3,
    }]}
    automation.session_manager = _SessionManager()
    automation.update_session_manager_config = lambda: None
    automation.helpers = _Helpers(automation)
    automation.workflow_runner = WorkflowRunner(automation)
    automation.actions = type('Actions', (), {})()
    automation.actions.post_url_business = workflow
    automation.stats = {'likes': 0, 'follows': 0, 'comments': 0, 'interactions': 0}
    automation.session_finalized = False
    return automation


def test_the_workflow_says_why_it_stopped_when_the_post_is_never_reached():
    workflow = _PostUrl(reachable=())

    stats = workflow.interact_with_post_likers(URL, {}, finalize=False)

    assert getattr(stats['stop_reason'], 'code', None) == 'navigation_lost'
    assert stop_reasons.terminal_status(stats['stop_reason']) == 'INTERRUPTED'
    assert workflow.lists_walked == []


def test_the_session_is_filed_as_a_failure_not_as_sources_exhausted():
    """The whole chain: workflow -> runner -> session loop. It used to end COMPLETED."""
    automation = _automation(_PostUrl(reachable=()))

    automation.run_workflow()

    assert len(automation.helpers.finalized) == 1
    status, reason = automation.helpers.finalized[0]
    assert status == 'INTERRUPTED'
    assert getattr(reason, 'code', None) == 'navigation_lost'


def test_an_unreachable_post_hands_over_to_the_next_one():
    """A link that cannot be reached is logged and the run goes on to the next link; each link
    opens by its own deep link, whatever screen the previous one left. The run over several
    links: `test_post_url_several_links.py`."""
    workflow = _PostUrl(reachable=(OTHER_URL,))
    automation = _automation(workflow, urls=(URL, OTHER_URL))

    automation.workflow_runner.run_workflow_step(automation.config['actions'][0])

    assert workflow.nav_actions.calls == [URL, OTHER_URL]
    assert workflow.lists_walked == [OTHER_URL]


def test_a_reached_post_still_walks_its_likers():
    workflow = _PostUrl(reachable=(URL,))

    result = workflow.interact_with_post_likers(URL, {}, finalize=False)

    assert workflow.lists_walked == [URL]
    assert getattr(result['stop_reason'], 'code', None) == 'completed'


def test_a_workflow_that_owns_the_finalisation_files_the_failure_itself():
    workflow = _PostUrl(reachable=())
    workflow.automation = type('A', (), {})()
    workflow.automation.helpers = _Helpers(workflow.automation)

    workflow.interact_with_post_likers(URL, {}, finalize=True)

    status, reason = workflow.automation.helpers.finalized[0]
    assert (status, getattr(reason, 'code', None)) == ('INTERRUPTED', 'navigation_lost')


def test_a_finalised_post_run_takes_the_status_its_motive_deserves():
    """The end of a reached post used to write COMPLETED whatever the motive: a block met in
    the likers list was filed as a clean run."""
    workflow = _PostUrl(reachable=(URL,))
    workflow.automation = type('A', (), {})()
    workflow.automation.helpers = _Helpers(workflow.automation)

    def _blocked(stats, effective_config, max_interactions, source_type, source_name,
                 list_source=None):
        stats['stop_reason'] = stop_reasons.action_blocked()

    workflow._interact_with_likers_list = _blocked
    workflow.interact_with_post_likers(URL, {}, finalize=True)

    status, reason = workflow.automation.helpers.finalized[0]
    assert (status, getattr(reason, 'code', None)) == ('INTERRUPTED', 'action_blocked')
