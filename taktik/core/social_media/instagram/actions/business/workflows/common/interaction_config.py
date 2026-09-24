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


#: The same five intents in the two spellings a workflow receives: percentages (0-100, the
#: workflow defaults and the CLI) and probabilities (0.0-1.0, what the runner sends through
#: `ActionProbabilities.to_dict`).
_PERCENTAGE_AND_PROBABILITY_KEYS = (
    ('like_percentage', 'like_probability'),
    ('follow_percentage', 'follow_probability'),
    ('comment_percentage', 'comment_probability'),
    ('story_watch_percentage', 'story_probability'),
    ('story_like_percentage', 'story_like_probability'),
)


def merge_operator_config(defaults: Dict[str, Any],
                          config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The workflow defaults overlaid with the operator's config, the operator winning in
    EITHER spelling.

    A plain ``{**defaults, **config}`` keeps a default percentage next to the operator's
    probability, and both readers downstream take the percentage: the hashtag posts pass reads
    ``*_percentage`` only, and `_determine_interactions_from_config` prefers it. Measured on a
    phone (2026-09-24): asked like 100 %, comment 0 %, the hashtag run applied the defaults --
    like 80 %, comment 5 % -- and posted a comment on a stranger's reel. Each intent the operator
    set is therefore written in both spellings.
    """
    config = config or {}
    merged = {**defaults, **config}
    for percentage_key, probability_key in _PERCENTAGE_AND_PROBABILITY_KEYS:
        probability = config.get(probability_key)
        percentage = config.get(percentage_key)
        if percentage is None and probability is not None:
            merged[percentage_key] = int(round(float(probability) * 100))
        elif probability is None and percentage is not None:
            merged[probability_key] = float(percentage) / 100.0
    return merged


__all__ = ["build_interaction_config", "merge_operator_config"]
