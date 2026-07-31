"""Five feed settings that existed in the catalogue and were read by nobody.

`interact_with_post_author`, `interact_with_post_likers`, `skip_reels`,
`story_watch_percentage` and `follow_percentage` were all in FEED_DEFAULTS with zero usages
in the code: the page could send them and nothing happened. They act now.

The last two needed the first one to mean anything at all — a feed post carries no Follow
button and no story ring, the author's PROFILE does — which is why they had stayed dead:
the feed workflow never left the feed.

Every one is OFF (or 0) by default, so an untouched run behaves exactly as before. That is
the property the first test pins; the rest describe the new behaviour.
"""

import inspect

import pytest

from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import (
    FEED_DEFAULTS,
)
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import (
    FeedBusiness,
)
from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)


# ───────────────────────────────────────────────────────────── no regression

@pytest.mark.parametrize("key,expected", [
    ('interact_with_post_author', False),
    ('interact_with_post_likers', False),
    ('skip_reels', False),
])
def test_every_new_behaviour_is_off_by_default(key, expected):
    assert FEED_DEFAULTS[key] is expected


def test_an_untouched_page_turns_none_of_them_on():
    action = build_instagram_automation_config({'workflowType': 'feed'})['actions'][0]
    assert action['interact_with_post_author'] is False
    assert action['interact_with_post_likers'] is False
    assert action['skip_reels'] is False


# ──────────────────────────────────────────────────────── the settings arrive

def test_the_settings_survive_the_config_chain():
    """Each hop is a whitelist; a key missing from any one of them is dropped in silence —
    which is precisely how these five stayed dead while looking configurable."""
    action = build_instagram_automation_config({
        'workflowType': 'feed',
        'feed': {
            'interactWithPostAuthor': True,
            'interactWithPostLikers': True,
            'skipReels': True,
            'maxLikersPerPost': 8,
        },
    })['actions'][0]

    assert action['interact_with_post_author'] is True
    assert action['interact_with_post_likers'] is True
    assert action['skip_reels'] is True
    assert action['max_likers_per_post'] == 8


def test_the_loop_actually_reads_them():
    """The point of this lot: they are read, not merely carried."""
    source = inspect.getsource(FeedBusiness.interact_with_feed)
    assert "effective_config.get('skip_reels'" in source
    assert "effective_config.get('interact_with_post_author'" in source
    assert "effective_config.get('interact_with_post_likers'" in source


# ────────────────────────────────────────────────────────── shared machinery

def test_the_author_visit_delegates_to_the_shared_engine():
    """`follow_percentage` and `story_watch_percentage` are honoured because the profile
    engine honours them — re-deciding probabilities here would fork the rules."""
    source = inspect.getsource(FeedBusiness._engage_post_author)
    assert "_perform_interactions_on_profile" in source


def test_the_likers_walk_reuses_the_shared_loop():
    """Same loop as hashtag and post_url. A second "walk a likers sheet" implementation is
    exactly the duplication that keeps costing this project."""
    source = inspect.getsource(FeedBusiness._engage_post_likers)
    assert "_interact_with_likers_list" in source
    assert hasattr(FeedBusiness, '_interact_with_likers_list')


@pytest.mark.parametrize("method", ['_engage_post_author', '_engage_post_likers'])
def test_both_excursions_always_hand_the_feed_back(method):
    """The loop's next advance assumes it is standing on the feed: a crawl that resumes from
    a profile page walks somebody else's posts. Hence a `finally`, not a happy-path return."""
    source = inspect.getsource(getattr(FeedBusiness, method))
    tail = source[source.index('finally:'):]
    assert 'navigate_to_home' in tail


def test_swapping_the_base_class_added_methods_without_taking_any_away():
    """`LikersWorkflowBase` replaced `BaseBusinessAction` to reach the likers loop. It only
    extends it — but the feed mixins keep priority in the MRO, so this checks no feed method
    was shadowed by the swap."""
    from taktik.core.social_media.instagram.actions.business.workflows.common.likers_base import (
        LikersWorkflowBase,
    )
    from taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions import (
        FeedPostActionsMixin,
    )
    added = {n for n in vars(LikersWorkflowBase) if not n.startswith('__')}
    assert not (added & set(vars(FeedPostActionsMixin)))
    # and the feed's own behaviour still resolves to the feed mixin
    assert FeedBusiness._like_current_post is FeedPostActionsMixin._like_current_post


# ─────────────────────────────────────────────────────── reachable from the page

@pytest.mark.parametrize("camel,snake", [
    ('interactWithPostAuthor', 'interact_with_post_author'),
    ('interactWithPostLikers', 'interact_with_post_likers'),
    ('skipReels', 'skip_reels'),
])
def test_the_page_key_reaches_the_workflow_key(camel, snake):
    """These five spent their whole life reachable by nobody. The bot reading them is only
    half the fix: without the page sending them, they stay exactly as dead as before."""
    action = build_instagram_automation_config({
        'workflowType': 'feed', 'feed': {camel: True},
    })['actions'][0]
    assert action[snake] is True


def test_the_likers_budget_survives_the_chain_and_has_a_floor():
    action = build_instagram_automation_config({
        'workflowType': 'feed', 'feed': {'maxLikersPerPost': 12},
    })['actions'][0]
    assert action['max_likers_per_post'] == 12

    # 0 or missing must not mean "walk nobody" silently — it falls back to the default.
    zeroed = build_instagram_automation_config({
        'workflowType': 'feed', 'feed': {'maxLikersPerPost': 0},
    })['actions'][0]
    assert zeroed['max_likers_per_post'] == 5
