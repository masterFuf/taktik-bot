"""The one reading of an Instagram scraping payload, for the desktop bridge and the CLI.

The payload is what the Scraping page sends (camelCase); the result is the config
`ScrapingWorkflow` reads. The bridge's reading was the one kept up to date (profile filters,
`fetchLocation`, the premium taxonomy, the `usernames` and `profile_posts` sources) while the Agent
handler, which the CLI runs, kept an older one. The snake_case names the handler accepted are still
read, after the page's names, so a terminal user may type either. Each key is read by a plain
`.get` (the page's name, then the alias), which the app's config contract test can follow.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from taktik.core.social_media.instagram.workflows.scraping.profile_posts_scraping import (
    DEFAULT_MAX_POSTS_PER_TARGET,
)

INSTAGRAM_SCRAPING_TYPES = ("target", "hashtag", "post_url", "usernames", "profile_posts")

#: Profile filters read by ScrapingListMixin._get_profile_filter_reason. They stay in camelCase
#: on purpose: that is exactly what the workflow reads (list_scraping.py). Renaming them here
#: without renaming the reader would silently disable them again.
_FILTER_MIN_KEYS = ('minFollowers', 'minFollowing', 'minPosts')
_FILTER_MAX_KEYS = ('maxFollowers', 'maxFollowing')


def _as_list(value: Any) -> list:
    """A list as the page sends it, or a single text as typed in a terminal; texts trimmed."""
    if value is None:
        return []
    items = [value] if isinstance(value, str) else list(value)
    return [item.strip() if isinstance(item, str) else item
            for item in items if not (isinstance(item, str) and not item.strip())]


def _number(value: Any) -> Any:
    """A count written as text (an Agent plan's parameter) read as the number it is."""
    if isinstance(value, str) and value.strip().lstrip('-').isdigit():
        return int(value.strip())
    return value


def scraping_config_from_payload(config: Mapping[str, Any]) -> dict:
    """The workflow config a scraping payload describes."""
    scraping_config = {
        'type': config.get('type', 'target'),
        'session_duration_minutes': _number(
            config.get('sessionDurationMinutes', config.get('session_duration_minutes', 60))),
        'max_profiles': _number(config.get('maxProfiles', config.get('max_profiles', 500))),
        'export_csv': config.get('exportCsv', config.get('export_csv', True)),
        'save_to_db': config.get('saveToDb', config.get('save_to_db', True)),
        'enrich_profiles': config.get('enrichProfiles', config.get('enrich_profiles', False)),
        # Opt-in "About this account" navigation (country/city, date joined) — only meaningful
        # when enrich_profiles is on. Off by default: the profile visit already yields stats/bio,
        # and the location screen is slow + its back-press can overshoot.
        'fetchLocation': bool(config.get('fetchLocation', config.get('fetch_location', False))),
    }

    # Profile filters. This mapper is a WHITELIST: anything not copied here never reaches the
    # workflow, which then evaluates every filter to "disabled".
    #
    # `is not None`, never `or`: the front sends null for an empty field, and 0 is a meaningful
    # lower bound — `int(x or 0)` would both re-enable a disabled filter and hide a real 0.
    for key in _FILTER_MIN_KEYS:
        value = config.get(key)
        if value is not None:
            scraping_config[key] = int(value)

    # UPPER bounds: 0 means NO LIMIT, not "at most zero followers". Forwarding it literally would
    # filter out every profile with a single follower and scrape nothing.
    for key in _FILTER_MAX_KEYS:
        value = config.get(key)
        if value is not None and int(value) > 0:
            scraping_config[key] = int(value)

    scraping_config['requireProfilePicture'] = bool(config.get('requireProfilePicture', False))
    scraping_config['skipPrivateProfiles'] = bool(config.get('skipPrivateProfiles', True))

    # Dedup filter:
    #   rescrapeAfterDays not set: the workflow skips all known profiles.
    #   rescrapeAfterDays = 0: always re-scrape (dedup disabled).
    #   rescrapeAfterDays = N > 0: skip profiles created within N days.
    rescrape_after_days = config.get('rescrapeAfterDays', config.get('rescrape_after_days'))
    if rescrape_after_days is not None:
        scraping_config['rescrape_after_days'] = int(rescrape_after_days)

    if config.get('deepQualify', config.get('deep_qualify')):
        scraping_config['deep_qualify'] = True
        dq_max = config.get('deepQualifyMaxFollowing', config.get('deep_qualify_max_following'))
        if dq_max is not None:
            scraping_config['deep_qualify_max_following'] = int(dq_max)

    scraping_config['response_language'] = config.get('appLanguage', config.get('response_language', 'en'))

    # The source settings follow the type the payload names; a payload that names none gets the
    # default type and no source settings, as the bridge always did.
    scraping_type = config.get('type')
    if scraping_type == 'target':
        scraping_config['target_usernames'] = _as_list(config.get(
            'targetUsernames',
            config.get('target_usernames', config.get('targets', config.get('targetAccounts', []))),
        ))
        scraping_config['scrape_type'] = config.get('scrapeType', config.get('scrape_type', 'followers'))
        scraping_config['scrape_post_likers'] = config.get(
            'scrapePostLikers', config.get('scrape_post_likers', True))
        scraping_config['scrape_post_commenters'] = config.get(
            'scrapePostCommenters', config.get('scrape_post_commenters', False))
    elif scraping_type == 'hashtag':
        hashtags = _as_list(config.get('hashtags')) or []
        if not hashtags and config.get('hashtag'):
            hashtags = _as_list(config.get('hashtag'))
        scraping_config['hashtags'] = hashtags
        scraping_config['hashtag'] = hashtags[0] if hashtags else ''
        scraping_config['scrape_likers'] = config.get('scrapeHashtagLikers', config.get('scrape_likers', True))
        scraping_config['scrape_commenters'] = config.get(
            'scrapeHashtagCommenters', config.get('scrape_commenters', False))
        scraping_config['max_posts'] = _number(config.get('maxPosts', config.get('max_posts', 50)))
    elif scraping_type == 'post_url':
        post_urls = _as_list(config.get('postUrls', config.get('post_urls'))) or []
        if not post_urls and config.get('postUrl'):
            post_urls = _as_list(config.get('postUrl'))
        scraping_config['post_urls'] = post_urls
        scraping_config['post_url'] = post_urls[0] if post_urls else ''
        scraping_config['scrape_likers'] = config.get('scrapePostUrlLikers', config.get('scrape_likers', True))
        scraping_config['scrape_commenters'] = config.get(
            'scrapePostUrlCommenters', config.get('scrape_commenters', False))
        scraping_config['post_id'] = post_id_from_url(post_urls[0] if post_urls else '')
    elif scraping_type == 'usernames':
        # No source screen to walk: the operator hands over the profiles by name and each one is
        # reached by navigating to it. `source_name` is free text kept for the scraping session row.
        scraping_config['usernames'] = _as_list(config.get('usernames', []))
        scraping_config['source_name'] = config.get('sourceName', 'manual selection')
    elif scraping_type == 'profile_posts':
        # Collect the POSTS of these accounts (url + counters); no profile is scraped.
        scraping_config['target_usernames'] = _as_list(config.get(
            'targetUsernames',
            config.get('target_usernames', config.get('targets', config.get('targetAccounts', []))),
        ))
        scraping_config['scrape_type'] = 'profile_posts'
        max_posts = config.get('maxPostsPerTarget')
        scraping_config['max_posts_per_target'] = (
            int(max_posts) if max_posts is not None and int(max_posts) > 0 else DEFAULT_MAX_POSTS_PER_TARGET
        )

    ai_config = config.get('ai', {})
    if ai_config and ai_config.get('enabled'):
        scraping_config['ai_mode'] = True
        scraping_config['ai_profile_analysis'] = ai_config.get('profileAnalysis', True)
        scraping_config['ai_niche'] = ai_config.get('niche', '')
        scraping_config['ai_qualification_prompt'] = ai_config.get('qualificationPrompt', '')
        scraping_config['openrouter_api_key'] = ai_config.get('openrouterApiKey', '')
        scraping_config['vision_model'] = ai_config.get('visionModel', '')
        # Premium niche taxonomy injected by the desktop app (slug -> [sub-niche labels]).
        scraping_config['niche_taxonomy'] = ai_config.get('nicheTaxonomy') or {}
        scraping_config['ai_rescrape_mode'] = config.get('aiRescrapeMode', config.get('ai_rescrape_mode', 'full'))
    else:
        scraping_config['ai_mode'] = False

    return scraping_config


def scraping_source_error(scraping_config: Mapping[str, Any]) -> Optional[str]:
    """Why a run has nothing to scrape, or None. Checked before the phone is touched."""
    scraping_type = scraping_config.get('type')
    if scraping_type in ('target', 'profile_posts') and not scraping_config.get('target_usernames'):
        return f"Instagram {scraping_type} scraping requires targetUsernames"
    if scraping_type == 'hashtag' and not scraping_config.get('hashtags'):
        return "Instagram hashtag scraping requires hashtags"
    if scraping_type == 'post_url' and not scraping_config.get('post_urls'):
        return "Instagram post_url scraping requires postUrls"
    if scraping_type == 'usernames' and not scraping_config.get('usernames'):
        return "Instagram usernames scraping requires usernames"
    return None


def post_id_from_url(first_url: str) -> str:
    """The post's short code, from a /p/ or /reel/ link."""
    match = re.search(r'/p/([^/]+)/', first_url)
    if match:
        return match.group(1)

    match = re.search(r'/reel/([^/]+)/', first_url)
    return match.group(1) if match else 'unknown'


__all__ = [
    "INSTAGRAM_SCRAPING_TYPES",
    "post_id_from_url",
    "scraping_config_from_payload",
    "scraping_source_error",
]
