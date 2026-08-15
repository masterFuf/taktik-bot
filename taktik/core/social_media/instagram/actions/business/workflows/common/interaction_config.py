"""What the operator's config means once a workflow is about to interact.

Every Instagram interaction workflow reads the same fifteen keys out of the raw config and
applies the same defaults. Recopied per workflow, that block drifts silently: a default
changed in one place keeps its old value everywhere else, and nothing fails — the runs just
behave differently for no reason a reader can see.

It is a PURE translation of config to config: no device, no database, no side effect. The
sequencing stays in the workflow; only the reading of the operator's intent lives here.
"""

from typing import Any, Dict, Optional

from taktik.core.shared.config import resolve_filter_criteria


def build_interaction_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Translate a workflow config into the interaction settings a profile pass needs.

    Defaults are the historical ones and are deliberately spelled out here rather than
    spread across call sites: this function is the single place to answer "what happens
    when the operator sets nothing?".
    """
    config = config or {}
    return {
        'like_probability': config.get('like_probability', 0.8),
        'follow_probability': config.get('follow_probability', 0.2),
        'comment_probability': config.get('comment_probability', 0.1),
        'story_probability': config.get('story_probability', 0.2),
        'story_like_probability': config.get('story_like_probability', 0.0),
        'min_likes_per_profile': config.get('min_likes_per_profile', 1),
        'max_likes_per_profile': config.get('max_likes_per_profile', 3),
        'max_comments_per_profile': config.get('max_comments_per_profile', 1),
        'max_stories_per_profile': config.get('max_stories_per_profile', 3),
        'max_story_likes_per_profile': config.get('max_story_likes_per_profile', 1),
        'ai_decision_mode': config.get('ai_decision_mode'),
        'ai_decision_dry_run': config.get('ai_decision_dry_run', True),
        'ai_decision_capabilities': config.get('ai_decision_capabilities'),
        'filter_criteria': resolve_filter_criteria(config),
    }


__all__ = ["build_interaction_config"]
