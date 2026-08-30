"""Config helpers for the TikTok scraping bridge workflow."""

from typing import Any

from bridges.tiktok.scraping.runtime.persistence import save_scraping_session


def build_scraping_config(config: dict[str, Any]):
    """Build the core ScrapingConfig from a bridge payload."""
    from taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow import ScrapingConfig

    return ScrapingConfig(
        scrape_type=config.get("type", "target"),
        target_usernames=config.get("targetUsernames", []),
        target_scrape_type=config.get("scrapeType", "followers"),
        hashtag=config.get("hashtag", ""),
        post_urls=config.get("postUrls", []),
        max_commenters_per_post=config.get("maxCommentersPerPost", 20),
        sound_query=config.get("soundQuery", ""),
        min_sound_posts=config.get("minSoundPosts", 500),
        max_users_per_sound=config.get("maxUsersPerSound", 10),
        max_sounds_per_session=config.get("maxSoundsPerSession", 5),
        max_posts_per_account=config.get("maxPostsPerAccount", 20),
        max_profiles=config.get("maxProfiles", 500),
        max_videos=config.get("maxPosts", 50),
        enrich_profiles=config.get("enrichProfiles", True),
        max_profiles_to_enrich=config.get("maxProfilesToEnrich", 50),
    )


def create_scraping_session(config: dict[str, Any]) -> int | None:
    """Create the optional DB scraping session for a bridge payload."""
    if not config.get("saveToDb", True):
        return None

    scrape_type = config.get("type", "target")
    target_scrape_type = config.get("scrapeType", "followers")
    target_usernames = config.get("targetUsernames", [])
    post_urls = config.get("postUrls", [])

    # The source has to name what was actually scraped. `HASHTAG` for everything that was not a
    # target was fine while those were the only two modes; a post-URL run filed under HASHTAG
    # with an empty name describes nothing anyone can trace back.
    if scrape_type == "target":
        source_type = target_scrape_type.upper()
        source_name = target_usernames[0] if target_usernames else ""
    elif scrape_type == "post_url":
        source_type = "POST_COMMENTERS"
        source_name = post_urls[0] if post_urls else ""
    elif scrape_type == "account_posts":
        source_type = "ACCOUNT_POSTS"
        source_name = target_usernames[0] if target_usernames else ""
    elif scrape_type == "sound":
        source_type = "SOUND"
        source_name = config.get("soundQuery", "")
    else:
        source_type = "HASHTAG"
        source_name = config.get("hashtag", "")

    return save_scraping_session(
        source_type=source_type,
        source_name=source_name,
        total_scraped=0,
        status="RUNNING",
        duration_seconds=0,
        platform="tiktok",
    )


__all__ = ["build_scraping_config", "create_scraping_session"]
