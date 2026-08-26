"""Workflow config mapping for the Instagram scraping bridge."""

from __future__ import annotations

import re

from taktik.core.social_media.instagram.workflows.scraping.profile_posts_scraping import (
    DEFAULT_MAX_POSTS_PER_TARGET,
)


#: Profile filters read by ScrapingListMixin._get_profile_filter_reason. They stay in camelCase
#: on purpose: that is exactly what the workflow reads (list_scraping.py). Renaming them here
#: without renaming the reader would silently disable them again.
_FILTER_MIN_KEYS = ('minFollowers', 'minFollowing', 'minPosts')
_FILTER_MAX_KEYS = ('maxFollowers', 'maxFollowing')


def build_scraping_config(config: dict) -> dict:
    scraping_config = {
        'type': config.get('type', 'target'),
        'session_duration_minutes': config.get('sessionDurationMinutes', 60),
        'max_profiles': config.get('maxProfiles', 500),
        'export_csv': config.get('exportCsv', True),
        'save_to_db': config.get('saveToDb', True),
        'enrich_profiles': config.get('enrichProfiles', False),
        # Opt-in "About this account" navigation (country/city, date joined) — only meaningful
        # when enrich_profiles is on. Off by default: the profile visit already yields stats/bio,
        # and the location screen is slow + its back-press can overshoot.
        'fetchLocation': bool(config.get('fetchLocation', False)),
    }

    # Profile filters. This mapper is a WHITELIST: anything not copied here never reaches the
    # workflow. The filter keys were missing, so `_get_profile_filter_reason` read them from an
    # empty config and EVERY filter evaluated to "disabled" — no min followers, no min posts, no
    # skip-private. Profiles the operator meant to exclude were scraped, saved AND paid for in AI
    # deep-qualification (device report: a 0-post profile scraped with minPosts=1).
    #
    # `is not None`, never `or`: the front sends null for an empty field, and 0 is a meaningful
    # lower bound — `int(x or 0)` would both re-enable a disabled filter and hide a real 0.
    for key in _FILTER_MIN_KEYS:
        value = config.get(key)
        if value is not None:
            scraping_config[key] = int(value)

    # UPPER bounds: 0 means NO LIMIT, not "at most zero followers".
    # The UI lets 0 sit in a max field (real config seen on a run: "Max followers: 0"), and every
    # operator reads that as "no maximum". Forwarding it literally would filter out every profile
    # with a single follower and scrape NOTHING — a far worse bug than the one being fixed.
    for key in _FILTER_MAX_KEYS:
        value = config.get(key)
        if value is not None and int(value) > 0:
            scraping_config[key] = int(value)

    scraping_config['requireProfilePicture'] = bool(config.get('requireProfilePicture', False))
    scraping_config['skipPrivateProfiles'] = bool(config.get('skipPrivateProfiles', True))

    # Dedup filter:
    #   rescrapeAfterDays not set: Python defaults to skip all known profiles.
    #   rescrapeAfterDays = 0: always re-scrape (dedup disabled).
    #   rescrapeAfterDays = N > 0: skip profiles created within N days.
    rescrape_after_days = config.get('rescrapeAfterDays')
    if rescrape_after_days is not None:
        scraping_config['rescrape_after_days'] = int(rescrape_after_days)

    if config.get('deepQualify'):
        scraping_config['deep_qualify'] = True
        dq_max = config.get('deepQualifyMaxFollowing')
        if dq_max is not None:
            scraping_config['deep_qualify_max_following'] = int(dq_max)

    scraping_config['response_language'] = config.get('appLanguage', 'en')

    if config.get('type') == 'target':
        scraping_config['target_usernames'] = config.get('targetUsernames', [])
        scraping_config['scrape_type'] = config.get('scrapeType', 'followers')
        scraping_config['scrape_post_likers'] = config.get('scrapePostLikers', True)
        scraping_config['scrape_post_commenters'] = config.get('scrapePostCommenters', False)
    elif config.get('type') == 'hashtag':
        hashtags = config.get('hashtags') or []
        if not hashtags and config.get('hashtag'):
            hashtags = [config.get('hashtag')]
        scraping_config['hashtags'] = hashtags
        scraping_config['hashtag'] = hashtags[0] if hashtags else ''
        scraping_config['scrape_likers'] = config.get('scrapeHashtagLikers', True)
        scraping_config['scrape_commenters'] = config.get('scrapeHashtagCommenters', False)
        scraping_config['max_posts'] = config.get('maxPosts', 50)
    elif config.get('type') == 'post_url':
        post_urls = config.get('postUrls') or []
        if not post_urls and config.get('postUrl'):
            post_urls = [config.get('postUrl')]
        scraping_config['post_urls'] = post_urls
        scraping_config['post_url'] = post_urls[0] if post_urls else ''
        scraping_config['scrape_likers'] = config.get('scrapePostUrlLikers', True)
        scraping_config['scrape_commenters'] = config.get('scrapePostUrlCommenters', False)
        scraping_config['post_id'] = _extract_post_id(post_urls[0] if post_urls else '')
    elif config.get('type') == 'usernames':
        # No source screen to walk: the operator hands over the profiles by name and each one is
        # reached by navigating to it. `source_name` is free text kept for the scraping session row.
        scraping_config['usernames'] = config.get('usernames', [])
        scraping_config['source_name'] = config.get('sourceName', 'manual selection')
    elif config.get('type') == 'profile_posts':
        # Collect the POSTS of these accounts (url + counters); no profile is scraped.
        scraping_config['target_usernames'] = config.get('targetUsernames', [])
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
        scraping_config['ai_rescrape_mode'] = config.get('aiRescrapeMode', 'full')
    else:
        scraping_config['ai_mode'] = False

    return scraping_config


def _extract_post_id(first_url: str) -> str:
    match = re.search(r'/p/([^/]+)/', first_url)
    if match:
        return match.group(1)

    match = re.search(r'/reel/([^/]+)/', first_url)
    return match.group(1) if match else 'unknown'
