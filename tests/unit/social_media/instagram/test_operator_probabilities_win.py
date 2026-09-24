"""The operator's probabilities beat the workflow's default percentages.

Measured on a phone, 2026-09-24, hashtag run asked like 100 %, follow 0 %, comment 0 %: the
workflow logged "Like 80%, Follow 15%" and posted a comment on a stranger's reel. The runner
sends PROBABILITIES (`like_probability`...), the hashtag and post URL defaults carry
PERCENTAGES (`like_percentage`...), and a plain `{**defaults, **config}` kept both -- while every
reader downstream takes the percentage first.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import (
    HASHTAG_DEFAULTS,
    POST_URL_DEFAULTS,
)
from taktik.core.social_media.instagram.actions.business.workflows.common.interaction_config import (
    merge_operator_config,
)
from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
    HashtagBusiness,
)
from taktik.core.social_media.instagram.actions.core.base_business.config_parsing import (
    ConfigParsingMixin,
)
from taktik.core.social_media.instagram.workflows.management.config import WorkflowConfigBuilder


def _runner_config(like=100, follow=0, comment=0, story=0, story_like=0):
    """The config the runner hands a workflow, built by the production builder."""
    return WorkflowConfigBuilder.build_interaction_config({
        'type': 'hashtag',
        'max_interactions': 3,
        'probabilities': {
            'like_percentage': like, 'follow_percentage': follow,
            'comment_percentage': comment, 'story_percentage': story,
            'story_like_percentage': story_like,
        },
    })


@pytest.fixture
def every_roll_succeeds(monkeypatch):
    """`randint(1, 100)` always returns 1: any intent above 0 % fires."""
    import taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow as hashtag_mod
    import taktik.core.social_media.instagram.actions.core.base_business.config_parsing as parsing_mod
    monkeypatch.setattr(hashtag_mod.random, 'randint', lambda a, b: a)
    monkeypatch.setattr(parsing_mod.random, 'randint', lambda a, b: a)


# ─────────────────────────────────────────────────────────────── the merge itself

def test_operator_probabilities_replace_the_default_percentages():
    merged = merge_operator_config(HASHTAG_DEFAULTS, _runner_config())

    assert merged['like_percentage'] == 100
    assert merged['follow_percentage'] == 0
    assert merged['comment_percentage'] == 0
    assert merged['story_watch_percentage'] == 0
    assert merged['story_like_percentage'] == 0


def test_operator_percentages_are_kept_and_mirrored():
    merged = merge_operator_config(HASHTAG_DEFAULTS, {'comment_percentage': 20})

    assert merged['comment_percentage'] == 20
    assert merged['comment_probability'] == pytest.approx(0.2)


def test_an_intent_the_operator_did_not_set_keeps_its_default():
    merged = merge_operator_config(HASHTAG_DEFAULTS, {'like_probability': 0.5})

    assert merged['like_percentage'] == 50
    assert merged['follow_percentage'] == HASHTAG_DEFAULTS['follow_percentage']
    assert 'follow_probability' not in merged


def test_probabilities_convert_without_float_drift():
    """`int(0.29 * 100)` is 28: the conversion rounds."""
    assert merge_operator_config({}, {'like_probability': 0.29})['like_percentage'] == 29


def test_the_defaults_are_not_modified():
    before = dict(HASHTAG_DEFAULTS)
    merge_operator_config(HASHTAG_DEFAULTS, _runner_config())
    assert HASHTAG_DEFAULTS == before


# ─────────────────────────────────────────────────────────────── hashtag, both passes

class _Log:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


class _Hashtag(HashtagBusiness):
    """Reaches the page, then hands the effective config to the test instead of a device."""

    def __init__(self):
        self.default_config = dict(HASHTAG_DEFAULTS)
        self.logger = _Log()
        self.session_manager = None
        self.automation = None
        self.seen_config = None
        self.likes = []
        self.comments = []
        host = self

        class _Nav:
            def navigate_to_hashtag(self, tag):
                return True

        class _Like:
            def like_current_post(self, record_as=None):
                host.likes.append(1)
                return True

        class _Comment:
            def comment_on_post(self, **kwargs):
                host.comments.append(kwargs.get('username'))
                return {'commented': True}

        class _Stats:
            def increment(self, *a, **k): pass

        self.nav_actions = _Nav()
        self.like_business = _Like()
        self.comment_business = _Comment()
        self.stats_manager = _Stats()

    def _run_interaction_plan(self, hashtag, plan, effective_config, stats, account_id,
                              finalize=True):
        self.seen_config = effective_config
        return stats


@pytest.fixture
def no_wait(monkeypatch):
    import taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_a, **_k: None)


def test_a_post_is_not_commented_when_the_operator_said_zero(every_roll_succeeds, no_wait):
    """The run of 2026-09-24: like 100 %, comment 0 %, and a comment went out."""
    workflow = _Hashtag()
    workflow.interact_with_hashtag_likers('videoproduction', _runner_config(), finalize=False)

    stats = {'likes_made': 0, 'comments_made': 0}
    workflow._engage_post_itself(workflow.seen_config, stats, 'someone')

    assert workflow.comments == []
    assert workflow.likes == [1]


def test_a_liker_is_not_followed_when_the_operator_said_zero(every_roll_succeeds, no_wait):
    """The likers walk reads the same merged config, through the shared profile pass."""
    workflow = _Hashtag()
    workflow.interact_with_hashtag_likers('videoproduction', _runner_config(), finalize=False)

    assert ConfigParsingMixin()._determine_interactions_from_config(workflow.seen_config) == ['like']


# ─────────────────────────────────────────────────────────────── post URL

def test_the_post_url_workflow_merges_the_same_way(monkeypatch):
    import taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow as mod

    merged = []

    def _spy(defaults, config):
        result = merge_operator_config(defaults, config)
        merged.append(result)
        return result

    monkeypatch.setattr(mod, 'merge_operator_config', _spy)

    workflow = object.__new__(mod.PostUrlBusiness)
    workflow.default_config = dict(POST_URL_DEFAULTS)
    workflow.logger = _Log()
    workflow._validate_instagram_url = lambda url: False  # stop right after the merge

    workflow.interact_with_post_likers('not-a-url', _runner_config(), finalize=False)

    assert merged and merged[0]['comment_percentage'] == 0
    assert merged[0]['follow_percentage'] == 0
    assert merged[0]['like_percentage'] == 100
