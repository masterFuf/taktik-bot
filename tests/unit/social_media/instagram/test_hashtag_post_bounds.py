"""Hashtag — which post is worth opening: the operator's bounds must actually reach the run.

The setting existed nowhere: the desktop page sent `0, 0` on a key the hashtag workflow never
read, and the workflow applied its catalogue defaults (100-50000) whatever the page said. So a
hashtag whose posts get twenty likes could never yield anything, and nothing said why.
"""

from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
    DEFAULT_MAX_POST_LIKES,
    DEFAULT_MIN_POST_LIKES,
    NO_LIKES_CEILING,
    resolve_post_like_bounds,
)
from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)


def test_catalogue_defaults_when_nothing_is_specified():
    assert resolve_post_like_bounds({}) == (DEFAULT_MIN_POST_LIKES, DEFAULT_MAX_POST_LIKES)


def test_nested_criteria_win_over_the_flat_defaults():
    """The two halves of the workflow read two shapes; whoever sets a threshold must win."""
    config = {'min_likes': 100, 'max_likes': 50000, 'post_criteria': {'min_likes': 10, 'max_likes': 900}}

    assert resolve_post_like_bounds(config) == (10, 900)


def test_zero_means_no_bound_not_zero_likes():
    """Same convention as the Feed workflow — otherwise "no minimum" cannot be expressed."""
    assert resolve_post_like_bounds({'post_criteria': {'min_likes': 0, 'max_likes': 0}}) == (0, NO_LIKES_CEILING)


def test_a_zero_ceiling_never_rejects_every_post():
    """0-0 read literally is an empty range: no post has between 0 and 0 likes."""
    low, high = resolve_post_like_bounds({'post_criteria': {'min_likes': 0, 'max_likes': 0}})

    assert low <= 20 <= high
    assert low <= 250000 <= high


def test_flat_shape_still_honoured():
    """The CLI and the workflow defaults speak flat; they must keep working."""
    assert resolve_post_like_bounds({'min_likes': 42, 'max_likes': 4242}) == (42, 4242)


def _desktop_hashtag_run(**extra):
    """The payload the Hashtag page actually sends to `bot:start-session`."""
    return build_instagram_automation_config({
        'workflowType': 'hashtags',
        'target': 'agencevideo',
        'limits': {'maxProfiles': 30, 'minLikesPerProfile': 1, 'maxLikesPerProfile': 3},
        'probabilities': {'like': 70, 'follow': 30},
        'filters': {'minFollowers': 100, 'maxFollowers': 50000},
        'session': {'durationMinutes': 60},
        **extra,
    })


def test_builder_carries_the_operator_bounds_to_the_workflow():
    """The builder is a whitelist: an unlisted key never reaches the run — this one was unlisted."""
    action = _desktop_hashtag_run(postCriteria={'minLikes': 10, 'maxLikes': 900})['actions'][0]

    assert action['post_criteria'] == {'min_likes': 10, 'max_likes': 900}
    assert resolve_post_like_bounds(action) == (10, 900)


def test_operator_can_ask_for_every_post_of_the_hashtag():
    """0/0 from the page must mean "no bound", all the way down to the workflow."""
    action = _desktop_hashtag_run(postCriteria={'minLikes': 0, 'maxLikes': 0})['actions'][0]
    low, high = resolve_post_like_bounds(action)

    assert low == 0 and high == NO_LIKES_CEILING


def test_builder_stays_silent_when_the_page_says_nothing():
    """No `postCriteria` = not specified; the workflow keeps its catalogue defaults."""
    action = _desktop_hashtag_run()['actions'][0]

    assert action['post_criteria'] is None
    assert resolve_post_like_bounds(action) == (DEFAULT_MIN_POST_LIKES, DEFAULT_MAX_POST_LIKES)
