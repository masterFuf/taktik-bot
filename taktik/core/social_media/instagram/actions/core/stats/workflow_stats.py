"""Standardized workflow statistics — factory + helpers.

Eliminates duplicated stats dict initialization across all workflows.
Each workflow type gets the same base keys + type-specific keys.
"""

from typing import Dict, Any, Optional
from copy import deepcopy


# ── Base keys present in ALL workflow stats ──────────────────────────────────

_BASE_STATS = {
    'users_found': 0,
    'users_interacted': 0,
    'profiles_visited': 0,
    'profiles_filtered': 0,
    'skipped': 0,
    'likes_made': 0,
    'follows_made': 0,
    'comments_made': 0,
    'stories_watched': 0,
    'stories_liked': 0,
    'errors': 0,
    'success': False,
}

# ── Type-specific extra keys ─────────────────────────────────────────────────

_TYPE_EXTRAS: Dict[str, Dict[str, Any]] = {
    'hashtag': {
        'hashtag': '',
        'posts_analyzed': 0,
        'posts_selected': 0,
    },
    'post_url': {
        'post_url': '',
    },
    'followers_direct': {
        # Aliases kept for backward compatibility with existing callers
        'interacted': 0,    # alias of users_interacted
        'visited': 0,       # alias of profiles_visited
        'liked': 0,         # alias of likes_made
        'followed': 0,      # alias of follows_made
        'story_likes': 0,   # alias of stories_liked
        'filtered': 0,      # alias of profiles_filtered
        'already_processed': 0,
        'processed': 0,     # alias of interacted (legacy compat)
    },
    'followers_legacy': {
        'processed': 0,
        'liked': 0,
        'followed': 0,
        'stories_viewed': 0,  # alias of stories_watched
        'resumed_from_checkpoint': False,
    },
    'followers_multi': {
        'targets_processed': 0,
        'total_extracted': 0,
    },
    'feed': {
        'posts_checked': 0,
        'posts_skipped_reels': 0,
        'posts_skipped_ads': 0,
    },
    'notifications': {
        'notifications_processed': 0,
    },
    'unfollow': {
        'accounts_checked': 0,
        'unfollows_made': 0,
        'skipped_verified': 0,
        'skipped_business': 0,
        'skipped_recent': 0,
        'skipped_followers': 0,
    },
}


def create_workflow_stats(workflow_type: str, source: str = '') -> Dict[str, Any]:
    """Create a standardized stats dict for a workflow.
    
    Args:
        workflow_type: One of 'hashtag', 'post_url', 'followers_direct',
                       'followers_legacy', 'followers_multi', 'feed',
                       'notifications', 'unfollow'
        source: Source identifier (hashtag name, URL, target username, etc.)
    
    Returns:
        Dict with all required keys initialized to zero/False/empty.
    """
    stats = deepcopy(_BASE_STATS)
    
    # Add type-specific keys
    extras = _TYPE_EXTRAS.get(workflow_type, {})
    stats.update(deepcopy(extras))
    
    # Set source in the appropriate key
    if workflow_type == 'hashtag' and source:
        stats['hashtag'] = source
    elif workflow_type == 'post_url' and source:
        stats['post_url'] = source
    
    return stats


def sync_aliases(stats: Dict[str, Any], workflow_type: str) -> None:
    """Synchronize aliased keys so both old and new names are consistent.
    
    Call this before returning stats to callers that may read either key name.
    """
    if workflow_type == 'followers_direct':
        stats['interacted'] = stats.get('users_interacted', stats.get('interacted', 0))
        stats['users_interacted'] = stats['interacted']
        stats['visited'] = stats.get('profiles_visited', stats.get('visited', 0))
        stats['profiles_visited'] = stats['visited']
        stats['liked'] = stats.get('likes_made', stats.get('liked', 0))
        stats['likes_made'] = stats['liked']
        stats['followed'] = stats.get('follows_made', stats.get('followed', 0))
        stats['follows_made'] = stats['followed']
        stats['story_likes'] = stats.get('stories_liked', stats.get('story_likes', 0))
        stats['stories_liked'] = stats['story_likes']
        stats['filtered'] = stats.get('profiles_filtered', stats.get('filtered', 0))
        stats['profiles_filtered'] = stats['filtered']
        stats['processed'] = stats['interacted']
    
    elif workflow_type == 'followers_legacy':
        stats['processed'] = stats.get('users_interacted', stats.get('processed', 0))
        stats['users_interacted'] = stats['processed']
        stats['liked'] = stats.get('likes_made', stats.get('liked', 0))
        stats['likes_made'] = stats['liked']
        stats['followed'] = stats.get('follows_made', stats.get('followed', 0))
        stats['follows_made'] = stats['followed']
        stats['stories_viewed'] = stats.get('stories_watched', stats.get('stories_viewed', 0))
        stats['stories_watched'] = stats['stories_viewed']
