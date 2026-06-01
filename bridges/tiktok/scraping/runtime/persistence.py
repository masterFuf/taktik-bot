"""TikTok scraping bridge persistence adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from bridges.common.persistence.database import get_repository
from bridges.tiktok.runtime.ipc import logger
from taktik.core.database.repositories.instagram.session.session_repository import SessionRepository
from taktik.core.database.repositories.tiktok.tiktok_repository import TikTokRepository


def save_scraping_session(
    source_type: str,
    source_name: str,
    total_scraped: int,
    status: str,
    duration_seconds: int,
    platform: str = "tiktok",
) -> Optional[int]:
    """Save scraping session to database and return session ID."""
    try:
        session_repo = get_repository(SessionRepository)
        session_id = session_repo.create_scraping(
            scraping_type=source_type,
            source_type=source_type,
            source_name=source_name,
            platform=platform,
        )
        logger.info(f"Saved scraping session {session_id} to database")
        return session_id
    except Exception as e:
        logger.warning(f"Error saving scraping session: {e}")
        return None


def save_scraped_profile(session_id: int, profile: Dict[str, Any], platform: str = "tiktok"):
    """Save a scraped profile to database via TikTokRepository."""
    try:
        tiktok_repo = get_repository(TikTokRepository)
        tiktok_repo.save_scraped_profile(session_id, profile)
        logger.debug(f"Saved TikTok profile @{profile.get('username', '?')} to session {session_id}")
    except Exception as e:
        logger.warning(f"Error saving scraped profile: {e}")


def update_scraping_session(session_id: int, total_scraped: int, status: str, duration_seconds: int):
    """Update scraping session in database."""
    try:
        session_repo = get_repository(SessionRepository)
        session_repo.update_scraping(
            scraping_id=session_id,
            total_scraped=total_scraped,
            status=status,
            duration_seconds=duration_seconds,
            end_time=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.warning(f"Error updating scraping session: {e}")


__all__ = [
    "save_scraping_session",
    "save_scraped_profile",
    "update_scraping_session",
]
