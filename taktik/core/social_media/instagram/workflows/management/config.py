from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class ActionProbabilities:
    """Probabilities for different action types (0.0 to 1.0)"""
    like: float = 0.7
    follow: float = 0.15
    comment: float = 0.05
    story: float = 0.1
    
    @classmethod
    def from_percentages(cls, probabilities: Dict[str, float]) -> 'ActionProbabilities':
        """Convert percentage dict to decimal probabilities"""
        return cls(
            like=probabilities.get('like_percentage', 70) / 100.0,
            follow=probabilities.get('follow_percentage', 15) / 100.0,
            comment=probabilities.get('comment_percentage', 5) / 100.0,
            story=probabilities.get('story_percentage', 10) / 100.0
        )
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dict format for compatibility"""
        return {
            'like_probability': self.like,
            'follow_probability': self.follow,
            'comment_probability': self.comment,
            'story_probability': self.story
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
    
    @classmethod
    def from_action(cls, action: Dict[str, Any]) -> 'FilterCriteria':
        """Extract filter criteria from action config"""
        return cls(
            min_followers=action.get('min_followers', 0),
            max_followers=action.get('max_followers', 100000),
            min_posts=action.get('min_posts', 3),
            max_following=action.get('max_following', 10000),
            allow_private=action.get('allow_private', False),
            max_followers_following_ratio=action.get('max_followers_following_ratio', 10.0)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format for compatibility"""
        return {
            'min_followers': self.min_followers,
            'max_followers': self.max_followers,
            'min_posts': self.min_posts,
            'max_following': self.max_following,
            'allow_private': self.allow_private,
            'max_followers_following_ratio': self.max_followers_following_ratio
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
        
        config = {
            'max_interactions': max_interactions,
            'max_interactions_per_session': max_interactions,
            **probabilities.to_dict(),
            'filter_criteria': filters.to_dict()
        }
        
        return config
    
    @staticmethod
    def build_hashtag_config(action: Dict[str, Any]) -> Dict[str, Any]:
        """Build config for hashtag workflow"""
        max_interactions = action.get('max_interactions', 10)
        probabilities = ActionProbabilities.from_percentages(action.get('probabilities', {}))
        
        return {
            'max_interactions': max_interactions,
            **probabilities.to_dict(),
            'interaction_type': action.get('interaction_type', 'recent-likers')
        }
    
    @staticmethod
    def build_post_url_config(action: Dict[str, Any]) -> Dict[str, Any]:
        """Build config for post URL workflow"""
        max_interactions = action.get('max_interactions', 20)
        probabilities = ActionProbabilities.from_percentages(action.get('probabilities', {}))
        filters = FilterCriteria.from_action(action)
        
        return {
            'max_interactions': max_interactions,
            'max_interactions_per_session': max_interactions,
            **probabilities.to_dict(),
            'filter_criteria': filters.to_dict()
        }
    
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
