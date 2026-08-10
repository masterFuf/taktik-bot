from typing import Dict, Any
from dataclasses import dataclass

from loguru import logger
from taktik.core.shared.config import resolve_filter_criteria


_EXECUTION_CONFIG_KEYS = (
    'min_likes_per_profile',
    'max_likes_per_profile',
    'max_comments_per_profile',
    'max_stories_per_profile',
    'max_story_likes_per_profile',
    'ai_decision_mode',
    'ai_decision_dry_run',
    'ai_decision_capabilities',
)


def _copy_execution_config(action: Dict[str, Any], config: Dict[str, Any]) -> None:
    """Preserve hard bounds and decision guards across compatibility config rebuilds."""
    for key in _EXECUTION_CONFIG_KEYS:
        if key in action:
            config[key] = action[key]


@dataclass
class ActionProbabilities:
    """Probabilities for different action types (0.0 to 1.0)"""
    like: float = 0.7
    follow: float = 0.15
    comment: float = 0.05
    story: float = 0.1
    story_like: float = 0.1

    @classmethod
    def from_percentages(cls, probabilities: Dict[str, float]) -> 'ActionProbabilities':
        """Convert percentage dict to decimal probabilities"""
        return cls(
            like=probabilities.get('like_percentage', 70) / 100.0,
            follow=probabilities.get('follow_percentage', 15) / 100.0,
            comment=probabilities.get('comment_percentage', 5) / 100.0,
            story=probabilities.get('story_percentage', 10) / 100.0,
            # story_like (front "likeStories") was previously dropped here, so it never
            # reached the interaction engine — keep it wired through to_dict() below.
            story_like=probabilities.get('story_like_percentage', 10) / 100.0
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dict format for compatibility"""
        return {
            'like_probability': self.like,
            'follow_probability': self.follow,
            'comment_probability': self.comment,
            'story_probability': self.story,
            'story_like_probability': self.story_like
        }


@dataclass
class FilterCriteria:
    """Filter criteria for profile selection"""
    min_followers: int = 0
    max_followers: int = 100000
    min_posts: int = 3
    max_following: int = 10000
    allow_private: bool = False
    max_followers_following_ratio: float = 10.0
    # Existing relationship, read on the profile header button. Opt-in, so false leaves
    skip_follows_us: bool = False
    skip_already_following: bool = False

    @classmethod
    def from_action(cls, action: Dict[str, Any]) -> 'FilterCriteria':
        """Extract filter criteria from an action, whichever shape it carries them in."""
        criteria = resolve_filter_criteria(action)
        return cls(
            min_followers=criteria.get('min_followers', 0),
            max_followers=criteria.get('max_followers', 100000),
            min_posts=criteria.get('min_posts', 3),
            max_following=criteria.get('max_following', 10000),
            allow_private=criteria.get('allow_private', False),
            max_followers_following_ratio=criteria.get('max_followers_following_ratio', 10.0),
            skip_follows_us=bool(criteria.get('skip_follows_us', False)),
            skip_already_following=bool(criteria.get('skip_already_following', False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format for compatibility"""
        return {
            'min_followers': self.min_followers,
            'max_followers': self.max_followers,
            'min_posts': self.min_posts,
            'max_following': self.max_following,
            'allow_private': self.allow_private,
            'max_followers_following_ratio': self.max_followers_following_ratio,
            'skip_follows_us': self.skip_follows_us,
            'skip_already_following': self.skip_already_following,
        }


class WorkflowConfigBuilder:
    """Centralized config builder for all workflows"""
    
    @staticmethod
    def build_interaction_config(action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build standardized config for follower interactions.
        Eliminates duplication in run_workflow().
        
        Args:
            action: Action dict from workflow config
            
        Returns:
            Standardized config dict
        """
        max_interactions = action.get('max_interactions', 10)
        probabilities = ActionProbabilities.from_percentages(action.get('probabilities', {}))
        filters = FilterCriteria.from_action(action)
        
        # Get custom comments from comment_settings
        comment_settings = action.get('comment_settings', {})
        custom_comments = comment_settings.get('custom_comments', [])
        
        config = {
            'max_interactions': max_interactions,
            'max_interactions_per_session': max_interactions,
            **probabilities.to_dict(),
            'filter_criteria': filters.to_dict(),
            'custom_comments': custom_comments,
            'interaction_type': action.get('interaction_type', 'followers')  # 'followers' or 'following'
        }

        # Concrete execution bounds and decision-mode guards must survive this compatibility
        # rebuild. Dropping them would restore stale defaults (notably max likes) and could let a
        # missing premium response fall back to the 100/0 capability probabilities.
        _copy_execution_config(action, config)

        if action.get('max_consecutive_known_usernames') is not None:
            config['max_consecutive_known_usernames'] = action.get('max_consecutive_known_usernames')
        if action.get('max_no_new_usernames_scrolls') is not None:
            config['max_no_new_usernames_scrolls'] = action.get('max_no_new_usernames_scrolls')
        # Budget split across several targets (balanced / sequential / interleaved).
        if action.get('distribution'):
            config['distribution'] = action.get('distribution')

        return config

    @staticmethod
    def build_hashtag_config(action: Dict[str, Any]) -> Dict[str, Any]:
        """Build config for hashtag workflow"""
        max_interactions = action.get('max_interactions', 10)
        probabilities = ActionProbabilities.from_percentages(action.get('probabilities', {}))
        filters = FilterCriteria.from_action(action)
        
        config = {
            'max_interactions': max_interactions,
            **probabilities.to_dict(),
            'interaction_type': action.get('interaction_type', 'recent-likers'),
            'filter_criteria': filters.to_dict()
        }

        _copy_execution_config(action, config)

        if action.get('max_consecutive_known_usernames') is not None:
            config['max_consecutive_known_usernames'] = action.get('max_consecutive_known_usernames')
        if action.get('max_no_new_usernames_scrolls') is not None:
            config['max_no_new_usernames_scrolls'] = action.get('max_no_new_usernames_scrolls')

        return config
    
    @staticmethod
    def build_post_url_config(action: Dict[str, Any]) -> Dict[str, Any]:
        """Build config for post URL workflow"""
        max_interactions = action.get('max_interactions', 20)
        probabilities = ActionProbabilities.from_percentages(action.get('probabilities', {}))
        filters = FilterCriteria.from_action(action)
        
        config = {
            'max_interactions': max_interactions,
            'max_interactions_per_session': max_interactions,
            **probabilities.to_dict(),
            'filter_criteria': filters.to_dict()
        }

        _copy_execution_config(action, config)

        if action.get('max_consecutive_known_usernames') is not None:
            config['max_consecutive_known_usernames'] = action.get('max_consecutive_known_usernames')
        if action.get('max_no_new_usernames_scrolls') is not None:
            config['max_no_new_usernames_scrolls'] = action.get('max_no_new_usernames_scrolls')

        # Which population of the post to walk. This builder is a whitelist, so the key has to
        # be copied explicitly or the UI choice never reaches the workflow.
        source_mode = str(action.get('source_mode') or '').strip().lower()
        if source_mode:
            if source_mode not in ('likers', 'commenters'):
                logger.warning(
                    f"Unknown post_url source_mode '{source_mode}' — falling back to likers"
                )
                source_mode = 'likers'
            config['source_mode'] = source_mode

        # In-thread engagement: act ON the comments instead of on the people behind them.
        # Same whitelist rule — an unlisted key never reaches the workflow.
        for key in ('like_comments', 'reply_to_comments'):
            if action.get(key) is not None:
                config[key] = bool(action.get(key))
        for key in ('max_comment_likes', 'max_comment_replies'):
            if action.get(key) is not None:
                config[key] = int(action.get(key) or 0)
        # A run may ask for in-thread work ONLY, without walking any profile.
        if action.get('walk_profiles') is not None:
            config['walk_profiles'] = bool(action.get('walk_profiles'))

        return config

    @staticmethod
    def build_place_config(action: Dict[str, Any]) -> Dict[str, Any]:
        """Build config for place workflow"""
        probabilities = ActionProbabilities.from_percentages(action.get('probabilities', {}))
        filters = FilterCriteria.from_action(action)
        
        return {
            'max_users': action.get('max_users', 20),
            'max_posts_to_check': action.get('max_posts_to_check', 5),
            **probabilities.to_dict(),
            'filter_criteria': filters.to_dict()
        }
