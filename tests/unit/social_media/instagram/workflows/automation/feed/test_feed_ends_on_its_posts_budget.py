"""A Feed run ends when its posts are browsed, not at its duration cap.

Pixel 3, 2026-09-28, a Feed node of 2 posts with no like: « Post 2/2 », « Feed workflow completed »,
then the step ran again, five times, until the 5-minute cap (`duration_cap`, 332 s for 2 posts).
The Feed's budget is counted in posts (`max_posts_to_check`, and `max_interactions` for the likes),
which the session's limits do not know (`total_profiles_limit` is 0 for a Feed run): the step
reported progress, and the run's loop relaunched it while the session allowed. The step now says
why it stopped (`posts_cap` when its budget is spent) and the runner ends the session on it, as the
hashtag step does.

The run's loop (`InstagramAutomation.run_workflow`), its runner and the Feed's own loop are the real
ones; the phone is played by the answers the Feed reads (no screen is parsed here: an on-feed post
by « bob » at each advance), and the session allows forty checks before its duration cap.
"""

import types

import pytest

import taktik.core.social_media.instagram.workflows.automation.automation as automation_module
import taktik.core.social_media.instagram.workflows.automation.feed.workflow as feed_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.workflows.automation.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.automation.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.workflows.automation.workflow_defaults import FEED_DEFAULTS
from taktik.core.social_media.instagram.workflows.automation.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.common.session import stop_reasons

_QUIET = types.SimpleNamespace(**{level: (lambda *a, **k: None)
                                   for level in ("debug", "info", "success", "warning", "error")})


class _Session:
    """The session as the run's loop and the Feed read it: allowed until its duration cap."""

    def __init__(self, checks_before_cap=40):
        self.checks_left = checks_before_cap

    def should_continue(self):
        self.checks_left -= 1
        if self.checks_left < 0:
            return False, stop_reasons.duration_cap(5)
        return True, None

    def get_delay_between_actions(self):
        return 0

    def start_interaction_phase(self):
        pass

    def exhausted_intents(self):
        return set()


def _feed(session):
    feed = object.__new__(FeedBusiness)
    feed.logger = _QUIET
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = session
    feed.automation = None
    feed.stats_manager = types.SimpleNamespace(increment=lambda *a, **k: None)
    feed.nav_actions = types.SimpleNamespace(navigate_to_home=lambda: True)
    feed.scroll_actions = types.SimpleNamespace(human_reading_pause=lambda **k: None)
    feed._advance_to_next_post = lambda *a, **k: {"on_feed": True}
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: "bob"
    feed.has_feed_suggestions_carousel = lambda: False
    feed._stop_if_action_blocked = lambda username, action: False
    feed._like_current_post = lambda record_as=None: True
    feed.passes = 0
    real = feed.interact_with_feed

    def counted(config=None):
        feed.passes += 1
        return real(config)

    feed.interact_with_feed = counted
    return feed


def _automation(step):
    automation = object.__new__(InstagramAutomation)
    automation.logger = _QUIET
    automation.config = {"actions": [step]}
    automation.session_manager = _Session()
    automation.stats = {"likes": 0, "follows": 0, "comments": 0, "interactions": 0}
    automation.update_session_manager_config = lambda: None
    automation._install_health_witness = lambda: None
    automation.feed_business = _feed(automation.session_manager)
    automation.workflow_runner = WorkflowRunner(automation)
    automation.ends = []

    def finalize(status="COMPLETED", reason=None):
        automation.ends.append((status, getattr(reason, "code", reason)))
        automation.session_finalized = True

    automation.helpers = types.SimpleNamespace(initialize_session=lambda: 1, finalize_session=finalize)
    return automation


# The Pixel 3's node: 2 posts, no like (the page sends the posts in `maxProfiles`, read as both).
_STEP = {
    "type": "feed", "max_interactions": 2, "max_posts_to_check": 2, "like_percentage": 0,
    "comment_percentage": 0, "view_feed_stories": False, "follow_suggestions": False,
    "capture_ads": False, "interact_with_post_author": False, "interact_with_post_likers": False,
}


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    run_halt.reinitialiser()
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(automation_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision", lambda *a, **k: None)
    yield
    run_halt.reinitialiser()


def test_the_feed_step_says_its_posts_budget_is_spent():
    feed = _feed(_Session())

    stats = feed.interact_with_feed(dict(_STEP))

    assert stats["posts_checked"] == 2
    assert getattr(stats.get("stop_reason"), "code", None) == "posts_cap"


def test_a_feed_run_ends_once_its_posts_are_browsed():
    automation = _automation(dict(_STEP))

    automation.run_workflow()

    assert automation.feed_business.passes == 1
    assert automation.ends == [("COMPLETED", "posts_cap")]


def test_a_feed_left_before_its_budget_still_goes_on_as_before():
    """Leaving the feed (a reel, a profile) is not the end of the budget: the step comes back to the
    feed on the next pass, as it did; the session's own limits end the run."""
    automation = _automation(dict(_STEP))
    automation.feed_business._advance_to_next_post = lambda *a, **k: {"on_feed": False}

    automation.run_workflow()

    assert automation.feed_business.passes > 1
    assert automation.ends == [("COMPLETED", "duration_cap")]
