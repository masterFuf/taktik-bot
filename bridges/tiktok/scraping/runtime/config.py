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
    source_name = target_usernames[0] if target_usernames else config.get("hashtag", "")

    return save_scraping_session(
        source_type=target_scrape_type.upper() if scrape_type == "target" else "HASHTAG",
        source_name=source_name,
        total_scraped=0,
        status="RUNNING",
        duration_seconds=0,
        platform="tiktok",
    )


__all__ = ["build_scraping_config", "create_scraping_session"]
