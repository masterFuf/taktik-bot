"""TikTok scraping bridge stdout event helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from bridges.tiktok.runtime.ipc import send_message


def send_scraping_progress(scraped: int, total: int, current: str):
    """Send scraping progress to frontend."""
    send_message("scraping_progress", scraped=scraped, total=total, current=current)


def send_scraped_profile(profile: Dict[str, Any]):
    """Send a scraped profile to frontend."""
    send_message(
        "scraping_profile",
        username=profile.get("username", ""),
        followersCount=profile.get("followers_count", 0),
        followingCount=profile.get("following_count", 0),
        scrapedAt=datetime.now().isoformat(),
    )


def send_scraping_completed(total_scraped: int):
    """Send scraping completed event."""
    send_message("scraping_completed", totalScraped=total_scraped)


__all__ = [
    "send_scraping_progress",
    "send_scraped_profile",
    "send_scraping_completed",
]
