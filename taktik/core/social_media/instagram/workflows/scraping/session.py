"""Shared session helpers for scraping/discovery workflows."""

from datetime import datetime


def should_continue_session(start_time, session_duration_minutes: float) -> bool:
    """Check if a session should continue based on elapsed time.

    Args:
        start_time: datetime when the session started (or None)
        session_duration_minutes: max duration in minutes

    Returns:
        True if session should continue, False if time limit reached
    """
    if not start_time:
        return True
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    return elapsed < session_duration_minutes
