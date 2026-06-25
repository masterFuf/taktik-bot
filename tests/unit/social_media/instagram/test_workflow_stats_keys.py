"""The followers_direct stats dict must carry every key the profile-processing
pipeline increments with `+=`.

Regression: `stories_viewed` was missing from the followers_direct factory, so
`stats['stories_viewed'] += result.stories` raised KeyError the moment a story
was actually watched (which only started happening after the story-ring open fix).
The exception aborted the direct workflow ("0 profiles processed") and made it
re-navigate to the target and re-scroll the followers list from the top.
"""

import pytest

from taktik.core.social_media.instagram.actions.core.stats.workflow_stats import (
    create_workflow_stats,
    sync_aliases,
)

# Keys that direct/main_loop.py + profile_processing.py mutate with `+=` (must be
# pre-initialized). Includes the pre-click DB-skip buckets `already_processed`
# (60-day cooldown) and `already_filtered` (filtered in a prior session): main_loop
# increments these instead of folding them into skipped/filtered, so the factory must
# provide them or `+=` raises KeyError on the first already-known follower.
_INCREMENTED_KEYS = [
    'already_filtered', 'already_processed', 'errors', 'filtered', 'followed',
    'interacted', 'liked', 'processed', 'skipped', 'stories_viewed', 'story_likes',
    'visited',
]


def test_followers_direct_stats_has_all_incremented_keys():
    stats = create_workflow_stats('followers_direct')
    for key in _INCREMENTED_KEYS:
        assert key in stats, f"followers_direct stats missing '{key}'"
        # The `+=` must not raise (the original KeyError).
        stats[key] += 1
        assert stats[key] == 1


def test_sync_aliases_preserves_incremented_counts():
    """Regression: profile_processing increments the alias keys (interacted, liked,
    ...). sync_aliases must NOT reset them to the never-touched canonical keys —
    that produced "Workflow completed (0 interactions)" despite real activity.
    """
    stats = create_workflow_stats('followers_direct')
    # Simulate a real run: 10 profiles interacted, 22 likes, 1 follow, 3 stories
    # watched, 1 story like, 2 filtered — all written to the ALIAS keys.
    stats['interacted'] = 10
    stats['visited'] = 10
    stats['liked'] = 22
    stats['followed'] = 1
    stats['stories_viewed'] = 3
    stats['story_likes'] = 1
    stats['filtered'] = 2

    sync_aliases(stats, 'followers_direct')

    # Aliases preserved (the completion message reads stats['interacted']).
    assert stats['interacted'] == 10
    assert stats['liked'] == 22
    assert stats['followed'] == 1
    assert stats['stories_viewed'] == 3
    assert stats['story_likes'] == 1
    assert stats['filtered'] == 2
    # ...and mirrored to the canonical keys.
    assert stats['users_interacted'] == 10
    assert stats['likes_made'] == 22
    assert stats['follows_made'] == 1
    assert stats['stories_watched'] == 3
    assert stats['stories_liked'] == 1
    assert stats['profiles_filtered'] == 2
