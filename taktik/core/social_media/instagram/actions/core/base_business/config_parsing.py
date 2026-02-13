"""Config parsing — extract filter criteria and determine interactions from workflow config."""

import random
from typing import Dict, Any, List


class ConfigParsingMixin:
    """Mixin: parsing config (filter criteria, détermination interactions par probabilité)."""

    def _get_filter_criteria_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        filter_criteria = config.get('filter_criteria', config.get('filters', {}))
        
        return {
            'min_followers': filter_criteria.get('min_followers', config.get('min_followers', 0)),
            'max_followers': filter_criteria.get('max_followers', config.get('max_followers', 100000)),
            'min_posts': filter_criteria.get('min_posts', config.get('min_posts', 3)),
            'max_following': filter_criteria.get('max_following', config.get('max_following', 10000)),
            'allow_private': not filter_criteria.get('skip_private', config.get('skip_private', True)),
            'max_followers_following_ratio': filter_criteria.get('max_followers_following_ratio', 
                                                                 config.get('max_followers_following_ratio', 10))
        }
    
    def _determine_interactions_from_config(self, config: Dict[str, Any]) -> List[str]:
        interactions = []
        
        # Support both percentage (0-100) and probability (0.0-1.0) formats
        def get_percentage(key_percentage: str, key_probability: str) -> float:
            """Get percentage value, supporting both formats"""
            if key_percentage in config:
                return config[key_percentage]
            if key_probability in config:
                # Convert probability (0.0-1.0) to percentage (0-100)
                return config[key_probability] * 100
            return 0
        
        like_pct = get_percentage('like_percentage', 'like_probability')
        follow_pct = get_percentage('follow_percentage', 'follow_probability')
        comment_pct = get_percentage('comment_percentage', 'comment_probability')
        story_pct = get_percentage('story_watch_percentage', 'story_probability')
        story_like_pct = get_percentage('story_like_percentage', 'story_like_probability')
        
        if random.randint(1, 100) <= like_pct:
            interactions.append('like')
        
        if random.randint(1, 100) <= follow_pct:
            interactions.append('follow')
        
        if random.randint(1, 100) <= comment_pct:
            interactions.append('comment')
        
        if random.randint(1, 100) <= story_pct:
            interactions.append('story')
        
        if random.randint(1, 100) <= story_like_pct:
            interactions.append('story_like')
        
        return interactions
