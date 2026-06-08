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
)

# Keys that direct/profile_processing.py mutates with `+=` (must be pre-initialized).
_INCREMENTED_KEYS = [
    'errors', 'filtered', 'followed', 'interacted', 'liked',
    'processed', 'skipped', 'stories_viewed', 'story_likes', 'visited',
]


def test_followers_direct_stats_has_all_incremented_keys():
    stats = create_workflow_stats('followers_direct')
    for key in _INCREMENTED_KEYS:
        assert key in stats, f"followers_direct stats missing '{key}'"
        # The `+=` must not raise (the original KeyError).
        stats[key] += 1
        assert stats[key] == 1
