"""The Feed step reaches the workflow whole: the operator's settings, not the defaults.

`config_builder` builds the feed step from the page (feed stories, suggestions mode, ad
capture, crawl toggles, likers budget). The runner then listed a dozen keys again, with
defaults of its own, and dropped the rest: a feed run asked to watch the stories of the tray
and like 40 % of them watched none, the workflow's `FEED_DEFAULTS` (`view_feed_stories: False`,
`story_like_percentage: 0`) applying in place of the operator's settings. Same family as the
hashtag defect of 2026-09-24, where default percentages overrode the operator's probabilities.
"""

import types

import pytest

import taktik.core.social_media.instagram.actions.business.workflows.feed.workflow as feed_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import FEED_DEFAULTS
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner


def _log():
    return types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )


_PAGE = {
    'workflowType': 'feed',
    'limits': {'maxProfiles': 4},
    'probabilities': {'like': 100, 'comment': 0, 'follow': 0, 'watchStories': 0, 'likeStories': 40},
    'feedStories': {'enabled': True, 'maxProfiles': 3},
    'feed': {
        'followSuggestions': True, 'captureAds': True, 'maxLikersPerPost': 12,
        'readCaptions': False, 'skipSuggested': False,
    },
}


def _feed_step():
    return build_instagram_automation_config(_PAGE)['actions'][0]


class _Recorder:
    def __init__(self):
        self.config = None

    def interact_with_feed(self, config):
        self.config = config
        return {'success': True}


def _automation(feed_business):
    return types.SimpleNamespace(
        feed_business=feed_business,
        stats={'likes': 0, 'follows': 0, 'comments': 0, 'interactions': 0},
    )


@pytest.mark.parametrize("key,expected", [
    ('view_feed_stories', True),
    ('story_like_percentage', 40),
    ('max_feed_story_profiles', 3),
    ('follow_suggestions', True),
    ('capture_ads', True),
    ('max_likers_per_post', 12),
    ('read_captions', False),
    ('skip_suggested', False),
])
def test_each_setting_of_the_step_reaches_the_workflow(key, expected):
    recorder = _Recorder()

    WorkflowRunner(_automation(recorder))._run_feed_workflow(_feed_step())

    assert recorder.config[key] == expected


def test_the_runner_adds_no_percentage_of_its_own():
    """A key the step does not carry is left to `FEED_DEFAULTS`, not to a second table."""
    recorder = _Recorder()

    WorkflowRunner(_automation(recorder))._run_feed_workflow({'type': 'feed'})

    assert 'follow_percentage' not in recorder.config
    assert 'type' not in recorder.config


# ─────────────────────────────────────────────── through the real workflow

def _feed():
    feed = object.__new__(FeedBusiness)
    feed.logger = _log()
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = None
    feed.automation = None
    feed.stats_manager = types.SimpleNamespace(increment=lambda *a, **k: None)
    feed.nav_actions = types.SimpleNamespace(navigate_to_home=lambda: True)
    feed.scroll_actions = types.SimpleNamespace(
        human_reading_pause=lambda **k: None,
        scroll_feed_to_next_post=lambda **k: {"on_feed": True},
    )
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: "bob"
    feed.has_feed_suggestions_carousel = lambda: False
    feed._stop_if_action_blocked = lambda username, action: False
    feed.likes = []
    feed._like_current_post = lambda record_as=None: feed.likes.append(record_as) or True
    feed.stories = []
    feed.story_business = types.SimpleNamespace(
        view_feed_stories=lambda cfg: feed.stories.append(cfg) or {})
    return feed


@pytest.fixture
def quiet(monkeypatch):
    run_halt.reinitialiser()
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision", lambda *a, **k: None)
    yield
    run_halt.reinitialiser()


def test_the_tray_stories_run_with_the_operators_like_rate(quiet):
    feed = _feed()

    WorkflowRunner(_automation(feed))._run_feed_workflow(_feed_step())

    assert len(feed.stories) == 1
    assert feed.stories[0]['like_probability'] == pytest.approx(0.40)
    assert feed.stories[0]['max_feed_profiles'] == 3


def test_an_operator_probability_beats_the_default_percentage(quiet):
    """`FEED_DEFAULTS` carries `like_percentage: 100`; an operator who sends the probability
    spelling and asks for no like gets no like."""
    feed = _feed()

    feed.interact_with_feed({'like_probability': 0.0, 'max_interactions': 2, 'max_posts_to_check': 2})

    assert feed.likes == []
