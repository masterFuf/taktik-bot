"""TikTok scraping sessions: the run's row in `scraping_sessions`, and each profile it collects.

Best-effort: a scrape that cannot store is still worth running (the desktop gets its profiles on
stdout), so every write logs its failure and carries on. Written by `run_tiktok_scraping`, from
the desktop bridge and the CLI alike; until then only the bridge wrote, and a CLI scrape left no
trace in the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.database.repositories import get_repository
from taktik.core.database.repositories.instagram.session.session_repository import SessionRepository
from taktik.core.database.repositories.tiktok.tiktok_repository import TikTokRepository

_PLATFORM = "tiktok"


def open_scraping_session(source_type: str, source_name: str) -> Optional[int]:
    """Create the session row of a scraping run; its id, or None when it cannot be written."""
    try:
        session_id = get_repository(SessionRepository).create_scraping(
            scraping_type=source_type,
            source_type=source_type,
            source_name=source_name,
            platform=_PLATFORM,
        )
        logger.info(f"Saved scraping session {session_id} to database")
        return session_id
    except Exception as e:
        logger.warning(f"Error saving scraping session: {e}")
        return None


def save_scraped_profile(session_id: int, profile: Dict[str, Any]) -> None:
    """File one collected profile under its session."""
    try:
        get_repository(TikTokRepository).save_scraped_profile(session_id, profile)
        logger.debug(f"Saved TikTok profile @{profile.get('username', '?')} to session {session_id}")
    except Exception as e:
        logger.warning(f"Error saving scraped profile: {e}")


def close_scraping_session(session_id: int, total_scraped: int, status: str, duration_seconds: int) -> None:
    """Close the session row: how many profiles, how it ended, how long it took."""
    try:
        get_repository(SessionRepository).update_scraping(
            scraping_id=session_id,
            total_scraped=total_scraped,
            status=status,
            duration_seconds=duration_seconds,
            end_time=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.warning(f"Error updating scraping session: {e}")


__all__ = ["close_scraping_session", "open_scraping_session", "save_scraped_profile"]
