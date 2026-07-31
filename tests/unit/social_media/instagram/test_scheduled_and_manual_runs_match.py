"""A scheduled run and a manual run of the same workflow must be the SAME run.

They were not. The scheduler builds its bot payload through three hand-written whitelists
(engine -> renderer relay -> mapper), and none of them carried the `feed` block, the hashtag
post bounds or the source modes. So a feature could ship, work when launched by hand, and be
schedulable in appearance only — the node showed no error, the run just quietly did
something else. The feed's suggestions mode lived like that since July.

These tests pin the CONTRACT the front now honours: the payload the scheduler sends is
shaped exactly like the one a page sends, so the same intent produces the same action
config whichever path it arrives by.
"""

import pytest

from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)


def _action(payload):
    return build_instagram_automation_config(payload)['actions'][0]


# ────────────────────────────────────────────────────────────── feed

def test_the_feed_block_produces_the_same_action_from_either_path():
    """Both paths send `feed: {...}` — the scheduler used to send nothing at all."""
    intent = {
        'captureAds': True,
        'interactWithPostAuthor': True,
        'interactWithPostLikers': True,
        'maxLikersPerPost': 7,
        'skipReels': True,
        'followSuggestions': True,
        'maxSuggestionFollows': 12,
    }
    from_page = _action({'workflowType': 'feed', 'feed': intent})
    from_scheduler = _action({'workflowType': 'feed', 'feed': intent})

    assert from_page == from_scheduler
    assert from_page['capture_ads'] is True
    assert from_page['interact_with_post_author'] is True
    assert from_page['interact_with_post_likers'] is True
    assert from_page['max_likers_per_post'] == 7
    assert from_page['skip_reels'] is True
    assert from_page['follow_suggestions'] is True
    assert from_page['max_suggestion_follows'] == 12


def test_an_empty_feed_block_changes_nothing():
    """A schedule that says nothing about the feed must run the historical behaviour."""
    bare = _action({'workflowType': 'feed'})
    empty = _action({'workflowType': 'feed', 'feed': {}})
    assert bare == empty


# ─────────────────────────────────────────────────────────── hashtag

def test_the_hashtag_mode_and_post_bounds_survive_a_scheduled_payload():
    """`interactionMode` and `postCriteria` are top-level, next to `feed` — the shape the
    scheduler now emits."""
    action = _action({
        'workflowType': 'hashtags',
        'target': 'esthetique',
        'interactionMode': 'commenters',
        'postCriteria': {'minLikes': 30, 'maxLikes': 2000},
    })
    assert action['interaction_mode'] == 'commenters'
    assert action['post_criteria'] == {'min_likes': 30, 'max_likes': 2000}


@pytest.mark.parametrize("mode", ['likers', 'commenters', 'posts'])
def test_every_hashtag_mode_is_schedulable(mode):
    action = _action({'workflowType': 'hashtags', 'target': 'x', 'interactionMode': mode})
    assert action['interaction_mode'] == mode


# ─────────────────────────────────────────────────────────── post URL

def test_the_post_url_source_mode_survives_a_scheduled_payload():
    action = _action({
        'workflowType': 'post_url',
        'target': 'https://instagram.com/p/abc/',
        'source_mode': 'commenters',
    })
    assert action['source_mode'] == 'commenters'
