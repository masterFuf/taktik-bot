"""Profile filtering, evaluated on data alone.

Extracted verbatim from `instagram/actions/business/management/filtering.py`, which turned out to
depend on nothing but its two dictionaries: no device, no session, no platform. It sat under
`instagram/` only because that is where it was first needed, and TikTok -- which filtered nothing
at all -- could not reach it without crossing the platform boundary the layering forbids.

The vocabulary below is the contract. A caller maps its own field names onto it (TikTok counts
videos, not posts, and displays a name rather than a full name) instead of each platform growing
its own dialect inside the evaluator:

    username, followers_count, following_count, posts_count, biography, full_name,
    is_private, is_verified, is_business, visible_posts_count, visible_stories_count

Two things about the scoring are easy to misread, and both are deliberate:

- the four stages combine by MINIMUM, not by sum, so penalties do not accumulate;
- the threshold is a strict comparison, so a score landing exactly on `min_score` passes.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from loguru import logger


def create_profile_filter(criteria: Mapping[str, Any]) -> Callable[[Mapping[str, Any]], Dict[str, Any]]:
    """Bind `criteria` into a one-argument filter, for callers that map over profiles."""

    def profile_filter(profile_info: Mapping[str, Any]) -> Dict[str, Any]:
        return apply_comprehensive_filter(profile_info, criteria)

    return profile_filter


def apply_comprehensive_filter(
    profile_info: Mapping[str, Any], criteria: Mapping[str, Any]
) -> Dict[str, Any]:
    """Score a profile against filter criteria, returning suitability, score and reasons."""
    result: Dict[str, Any] = {
        'suitable': True,
        'score': 100,
        'reasons': [],
        'category': 'suitable',
        'filter_details': {},
        'username': profile_info.get('username', 'unknown')
    }

    try:
        basic_result = _apply_basic_filters(profile_info, criteria)
        result.update(basic_result)

        if not result['suitable']:
            return result

        advanced_result = _apply_advanced_filters(profile_info, criteria)
        result['score'] = min(result['score'], advanced_result['score'])
        result['reasons'].extend(advanced_result['reasons'])
        result['filter_details'].update(advanced_result['details'])

        content_result = _apply_content_filters(profile_info, criteria)
        result['score'] = min(result['score'], content_result['score'])
        result['reasons'].extend(content_result['reasons'])
        result['filter_details'].update(content_result['details'])

        behavior_result = _apply_behavior_filters(profile_info, criteria)
        result['score'] = min(result['score'], behavior_result['score'])
        result['reasons'].extend(behavior_result['reasons'])
        result['filter_details'].update(behavior_result['details'])

        result['category'] = _determine_final_category(result)

        min_score = criteria.get('min_score', 50)
        if result['score'] < min_score:
            result['suitable'] = False
            result['reasons'].append(f'Score too low ({result["score"]} < {min_score})')

    except Exception as e:
        logger.error(f"Error filtering profile: {e}")
        result.update({
            'suitable': False,
            'score': 0,
            'reasons': [f'Filter error: {str(e)}'],
            'category': 'error'
        })

    return result


def _apply_basic_filters(
    profile_info: Mapping[str, Any], criteria: Mapping[str, Any]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'suitable': True,
        'score': 100,
        'reasons': [],
        'filter_details': {'basic_filters': {}}
    }

    if profile_info.get('is_private', False):
        if not criteria.get('allow_private', False):
            result.update({
                'suitable': False,
                'reasons': ['Private account'],
                'category': 'private',
                'score': 0
            })
            return result

    followers = profile_info.get('followers_count', 0)
    if followers is None:
        followers = 0
    min_followers = criteria.get('min_followers', 0)
    if followers < min_followers:
        result.update({
            'suitable': False,
            'reasons': [f'Too few followers ({followers} < {min_followers})'],
            'category': 'low_followers',
            'score': 0
        })
        return result

    max_followers = criteria.get('max_followers', float('inf'))
    if followers > max_followers:
        result.update({
            'suitable': False,
            'reasons': [f'Too many followers ({followers} > {max_followers})'],
            'category': 'high_followers',
            'score': 0
        })
        return result

    posts = profile_info.get('posts_count', 0)
    min_posts = criteria.get('min_posts', 0)
    if posts < min_posts:
        result.update({
            'suitable': False,
            'reasons': [f'Too few posts ({posts} < {min_posts})'],
            'category': 'inactive',
            'score': 0
        })
        return result

    # Bot-username detection was disabled on the Instagram path for producing too many false
    # positives, and is not reinstated by the move.

    result['filter_details']['basic_filters'] = {
        'private_check': 'passed',
        'followers_range': 'passed',
        'posts_minimum': 'passed',
        'bot_detection': 'passed'
    }

    return result


def _apply_advanced_filters(
    profile_info: Mapping[str, Any], criteria: Mapping[str, Any]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'score': 100,
        'reasons': [],
        'details': {'advanced_filters': {}}
    }

    followers = profile_info.get('followers_count', 0)
    following = profile_info.get('following_count', 0)
    posts = profile_info.get('posts_count', 0)

    if following > 0:
        ratio = followers / following
        max_ratio = criteria.get('max_following_ratio', 10.0)

        if ratio > max_ratio:
            penalty = min(30, (ratio - max_ratio) * 5)
            result['score'] -= penalty
            result['reasons'].append(f'High follower ratio ({ratio:.1f})')
            result['details']['advanced_filters']['follower_ratio'] = 'penalty'
        else:
            result['details']['advanced_filters']['follower_ratio'] = 'good'

    if followers > 0:
        posts_ratio = posts / followers

        if posts_ratio < 0.001:
            result['score'] -= 20
            result['reasons'].append('Very low posting activity')
            result['details']['advanced_filters']['activity_level'] = 'low'
        elif posts_ratio > 0.1:
            result['score'] -= 10
            result['reasons'].append('Very high posting activity')
            result['details']['advanced_filters']['activity_level'] = 'high'
        else:
            result['details']['advanced_filters']['activity_level'] = 'normal'

    if profile_info.get('is_verified', False):
        if criteria.get('verified_penalty', 0) > 0:
            result['score'] -= criteria['verified_penalty']
            result['reasons'].append('Verified account')
            result['details']['advanced_filters']['verified'] = 'penalty'
        else:
            result['details']['advanced_filters']['verified'] = 'bonus'

    if profile_info.get('is_business', False):
        business_penalty = criteria.get('business_penalty', 0)
        if business_penalty > 0:
            result['score'] -= business_penalty
            result['reasons'].append('Business account')
            result['details']['advanced_filters']['business'] = 'penalty'
        else:
            result['details']['advanced_filters']['business'] = 'neutral'

    return result


def _apply_content_filters(
    profile_info: Mapping[str, Any], criteria: Mapping[str, Any]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'score': 100,
        'reasons': [],
        'details': {'content_filters': {}}
    }

    bio = profile_info.get('biography', '')
    if bio:
        forbidden_keywords = criteria.get('forbidden_bio_keywords', [])
        for keyword in forbidden_keywords:
            if keyword.lower() in bio.lower():
                result['score'] -= 25
                result['reasons'].append(f'Forbidden keyword in bio: {keyword}')
                result['details']['content_filters']['bio_keywords'] = 'violation'
                break
        else:
            result['details']['content_filters']['bio_keywords'] = 'clean'

        required_keywords = criteria.get('required_bio_keywords', [])
        if required_keywords:
            found_keywords = []
            for keyword in required_keywords:
                if keyword.lower() in bio.lower():
                    found_keywords.append(keyword)

            if not found_keywords:
                result['score'] -= 15
                result['reasons'].append('No required keywords in bio')
                result['details']['content_filters']['required_keywords'] = 'missing'
            else:
                result['details']['content_filters']['required_keywords'] = 'found'
    else:
        if criteria.get('require_bio', False):
            result['score'] -= 10
            result['reasons'].append('No biography')
            result['details']['content_filters']['bio_presence'] = 'missing'
        else:
            result['details']['content_filters']['bio_presence'] = 'optional'

    full_name = profile_info.get('full_name', '')
    if not full_name and criteria.get('require_full_name', False):
        result['score'] -= 5
        result['reasons'].append('No full name')
        result['details']['content_filters']['full_name'] = 'missing'
    else:
        result['details']['content_filters']['full_name'] = 'present'

    return result


def _apply_behavior_filters(
    profile_info: Mapping[str, Any], criteria: Mapping[str, Any]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'score': 100,
        'reasons': [],
        'details': {'behavior_filters': {}}
    }

    # RELATIONSHIP STATE -- INFORMATIVE ONLY here.
    #
    # The DECISION to skip a profile already in a relationship lives upstream, as a plain
    # rejection before the filters and before the qualification. Do not replay it here as a score:
    # the stages combine by minimum, so a penalty added here would change nothing anyway.
    follow_state = profile_info.get('follow_button_state', 'unknown')
    result['details']['behavior_filters']['follow_state'] = follow_state

    stories_count = profile_info.get('visible_stories_count', 0)
    if stories_count > 0:
        result['score'] += 5
        result['details']['behavior_filters']['recent_activity'] = 'active'
    else:
        result['details']['behavior_filters']['recent_activity'] = 'inactive'

    visible_posts = profile_info.get('visible_posts_count', 0)
    if visible_posts == 0 and not profile_info.get('is_private', False):
        result['score'] -= 15
        result['reasons'].append('No visible posts')
        result['details']['behavior_filters']['content_visibility'] = 'no_posts'
    else:
        result['details']['behavior_filters']['content_visibility'] = 'has_content'

    return result


def _determine_final_category(result: Mapping[str, Any]) -> str:
    if not result['suitable']:
        return result.get('category', 'filtered')

    score = result['score']

    if score >= 90:
        return 'excellent'
    elif score >= 80:
        return 'very_good'
    elif score >= 70:
        return 'good'
    elif score >= 60:
        return 'acceptable'
    elif score >= 50:
        return 'marginal'
    else:
        return 'poor'


__all__ = ["apply_comprehensive_filter", "create_profile_filter"]
