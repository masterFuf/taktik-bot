"""A hashtag page that was never reached ends the run as a failure, not as a dry hashtag.

Measured on a phone (IG 447, French), 2026-09-24: the search bar was not found, the workflow
returned without a motive, the runner saw zero interactions, and the session loop concluded
"sources exhausted" -- filed COMPLETED. The operator read a clean run that never left the
search screen.
"""

from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import (
    HASHTAG_DEFAULTS,
)
from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
    HashtagBusiness,
)
from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


class _Log:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def success(self, *a, **k): pass


class _Navigation:
    """Reaches the hashtags listed in `reachable`, fails on every other one."""

    def __init__(self, reachable=()):
        self.reachable = set(reachable)
        self.calls = []

    def navigate_to_hashtag(self, hashtag):
        self.calls.append(hashtag)
        return hashtag in self.reachable


class _Hashtag(HashtagBusiness):
    """The workflow with its navigation stubbed and its post loop replaced by a recorder."""

    def __init__(self, reachable=()):
        self.default_config = dict(HASHTAG_DEFAULTS)
        self.logger = _Log()
        self.nav_actions = _Navigation(reachable)
        self.session_manager = None
        self.automation = None
        self.plans_run = []

    def _run_interaction_plan(self, hashtag, plan, effective_config, stats, account_id,
                              finalize=True):
        self.plans_run.append(hashtag)
        stats['users_interacted'] = 1
        stats['stop_reason'] = stop_reasons.posts_cap(1, 1)
        return stats


class _Helpers:
    def __init__(self, automation):
        self.automation = automation
        self.finalized = []

    def initialize_session(self):
        return 1585

    def finalize_session(self, status='COMPLETED', reason=''):
        self.finalized.append((status, reason))
        self.automation.session_finalized = True


class _SessionManager:
    def should_continue(self):
        return True, ''

    def get_delay_between_actions(self):
        return 0


def _automation(workflow, hashtags=('videoproduction',)):
    """InstagramAutomation without a device: the real run loop and the real runner."""
    automation = object.__new__(InstagramAutomation)
    automation.logger = _Log()
    automation.config = {'actions': [{
        'type': 'hashtag', 'hashtags': list(hashtags), 'max_interactions': 3,
    }]}
    automation.session_manager = _SessionManager()
    automation.update_session_manager_config = lambda: None
    automation.helpers = _Helpers(automation)
    automation.workflow_runner = WorkflowRunner(automation)
    automation.hashtag_interaction_manager = workflow
    automation.session_finalized = False
    return automation


def test_the_workflow_says_why_it_stopped_when_the_page_is_never_reached():
    workflow = _Hashtag(reachable=())

    stats = workflow.interact_with_hashtag_likers('videoproduction', {}, finalize=False)

    assert getattr(stats['stop_reason'], 'code', None) == 'navigation_lost'
    assert stop_reasons.terminal_status(stats['stop_reason']) == 'INTERRUPTED'
    assert workflow.plans_run == []


def test_the_session_is_filed_as_a_failure_not_as_sources_exhausted():
    """The whole chain: workflow -> runner -> session loop. It used to end COMPLETED."""
    automation = _automation(_Hashtag(reachable=()))

    automation.run_workflow()

    assert len(automation.helpers.finalized) == 1
    status, reason = automation.helpers.finalized[0]
    assert status == 'INTERRUPTED'
    assert getattr(reason, 'code', None) == 'navigation_lost'


def test_an_unreachable_hashtag_ends_the_run_instead_of_trying_the_next_one():
    """A lost navigation is a session motive (`ends_the_session`), like the target workflow's:
    the app is on a screen nobody identified, so the next hashtag would start from there."""
    workflow = _Hashtag(reachable=('second',))
    automation = _automation(workflow, hashtags=('first', 'second'))

    automation.run_workflow()

    assert workflow.nav_actions.calls == ['first']
    assert workflow.plans_run == []


def test_a_reached_hashtag_still_runs_its_plan():
    workflow = _Hashtag(reachable=('videoproduction',))

    stats = workflow.interact_with_hashtag_likers('videoproduction', {}, finalize=False)

    assert workflow.plans_run == ['videoproduction']
    assert getattr(stats['stop_reason'], 'code', None) == 'posts_cap'


def test_a_workflow_that_owns_the_finalisation_files_the_failure_itself():
    workflow = _Hashtag(reachable=())
    workflow.automation = type('A', (), {})()
    workflow.automation.helpers = _Helpers(workflow.automation)

    workflow.interact_with_hashtag_likers('videoproduction', {}, finalize=True)

    status, reason = workflow.automation.helpers.finalized[0]
    assert (status, getattr(reason, 'code', None)) == ('INTERRUPTED', 'navigation_lost')
