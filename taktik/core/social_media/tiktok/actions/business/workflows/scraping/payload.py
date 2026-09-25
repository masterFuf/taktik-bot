"""One reading of a TikTok scraping payload, for the bridges and the Agent handler alike.

The wire form is the page's camelCase (`TikTokScraping.tsx` and the scheduler's scraping node,
both through the main process's `buildScrapingPayload`); the snake_case names an Agent plan or a
CLI call writes stay accepted. Every key is read by name, so the app's config contract test can
see which ones the bot reads.
"""

from __future__ import annotations

from typing import Any, Mapping

from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    as_bool,
    as_float,
    as_int,
    first_given,
)

from .models import ScrapingConfig


def _text(value: Any) -> str:
    return str(value or "").strip()


def _names(value: Any) -> list[str]:
    """Account names, one per item or comma-separated, without "#"."""
    if isinstance(value, str):
        value = value.split(",")
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
    return []


def _links(value: Any) -> list[str]:
    """Post links, one per item or separated by commas or spaces; a link keeps every character."""
    if isinstance(value, str):
        value = value.replace(",", " ").split()
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def scraping_config_from_payload(payload: Mapping[str, Any]) -> ScrapingConfig:
    """The config of one scraping run; an absent key keeps the page's default.

    Refuses, before anything touches the phone, a target run without an account and a hashtag run
    without a hashtag: both would restart TikTok and scrape nothing.
    """
    scrape_type = _text(first_given(payload.get("type"), payload.get("scrape_type")) or "target").lower()
    target_usernames = _names(first_given(payload.get("targetUsernames"), payload.get("target_usernames")))
    hashtag = _text(payload.get("hashtag")).lstrip("#")

    if scrape_type == "target" and not target_usernames:
        raise ValueError("TikTok scraping requires targetUsernames for target scraping")
    if scrape_type == "hashtag" and not hashtag:
        raise ValueError("TikTok scraping requires a non-empty hashtag for hashtag scraping")

    return ScrapingConfig(
        scrape_type=scrape_type,
        target_usernames=target_usernames,
        target_scrape_type=_text(
            first_given(payload.get("scrapeType"), payload.get("target_scrape_type")) or "followers"
        ).lower(),
        hashtag=hashtag,
        post_urls=_links(first_given(payload.get("postUrls"), payload.get("post_urls"))),
        max_commenters_per_post=as_int(
            first_given(payload.get("maxCommentersPerPost"), payload.get("max_commenters_per_post")), 20
        ),
        sound_query=_text(first_given(payload.get("soundQuery"), payload.get("sound_query"))),
        min_sound_posts=as_int(first_given(payload.get("minSoundPosts"), payload.get("min_sound_posts")), 500),
        max_users_per_sound=as_int(
            first_given(payload.get("maxUsersPerSound"), payload.get("max_users_per_sound")), 10
        ),
        max_sounds_per_session=as_int(
            first_given(payload.get("maxSoundsPerSession"), payload.get("max_sounds_per_session")), 5
        ),
        max_posts_per_account=as_int(
            first_given(payload.get("maxPostsPerAccount"), payload.get("max_posts_per_account")), 20
        ),
        max_profiles=as_int(first_given(payload.get("maxProfiles"), payload.get("max_profiles")), 500),
        # The page and the node send `maxPosts`; an Agent plan may write `maxVideos` / `max_videos`.
        max_videos=as_int(
            first_given(payload.get("maxPosts"), payload.get("maxVideos"), payload.get("max_videos")), 50
        ),
        enrich_profiles=as_bool(first_given(payload.get("enrichProfiles"), payload.get("enrich_profiles")), True),
        max_profiles_to_enrich=as_int(
            first_given(payload.get("maxProfilesToEnrich"), payload.get("max_profiles_to_enrich")), 50
        ),
        # "Durée max. de la session" (page and node). Absent means no limit.
        session_duration_minutes=as_float(
            first_given(payload.get("sessionDurationMinutes"), payload.get("session_duration_minutes")), 0.0
        ),
    )


def save_to_db_from_payload(payload: Mapping[str, Any]) -> bool:
    """Whether the run files a scraping session and its profiles; yes unless told otherwise."""
    return as_bool(first_given(payload.get("saveToDb"), payload.get("save_to_db")), True)


def scraping_source(config: ScrapingConfig) -> tuple[str, str]:
    """What the session row names as its source: the kind of source, and which one.

    Named after what was actually scraped: a post-URL run filed under HASHTAG with an empty name
    described nothing anyone could trace back.
    """
    if config.scrape_type == "target":
        return config.target_scrape_type.upper(), _first(config.target_usernames)
    if config.scrape_type == "post_url":
        return "POST_COMMENTERS", _first(config.post_urls)
    if config.scrape_type == "account_posts":
        return "ACCOUNT_POSTS", _first(config.target_usernames)
    if config.scrape_type == "sound":
        return "SOUND", config.sound_query
    return "HASHTAG", config.hashtag


def _first(values: list[str]) -> str:
    return values[0] if values else ""


__all__ = [
    "save_to_db_from_payload",
    "scraping_config_from_payload",
    "scraping_source",
]
