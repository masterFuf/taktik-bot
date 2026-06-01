"""Workflow config mapping for the Instagram scraping bridge."""

from __future__ import annotations

import re


def build_scraping_config(config: dict) -> dict:
    scraping_config = {
        'type': config.get('type', 'target'),
        'session_duration_minutes': config.get('sessionDurationMinutes', 60),
        'max_profiles': config.get('maxProfiles', 500),
        'export_csv': config.get('exportCsv', True),
        'save_to_db': config.get('saveToDb', True),
        'enrich_profiles': config.get('enrichProfiles', False),
    }

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

    ai_config = config.get('ai', {})
    if ai_config and ai_config.get('enabled'):
        scraping_config['ai_mode'] = True
        scraping_config['ai_profile_analysis'] = ai_config.get('profileAnalysis', True)
        scraping_config['ai_niche'] = ai_config.get('niche', '')
        scraping_config['ai_qualification_prompt'] = ai_config.get('qualificationPrompt', '')
        scraping_config['openrouter_api_key'] = ai_config.get('openrouterApiKey', '')
        scraping_config['vision_model'] = ai_config.get('visionModel', '')
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
