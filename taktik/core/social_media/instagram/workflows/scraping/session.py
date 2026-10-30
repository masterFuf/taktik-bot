"""Shared session helpers for scraping/discovery workflows."""

from datetime import datetime

from loguru import logger

from taktik.core.shared.diagnostics import run_halt


def should_continue_session(start_time, session_duration_minutes: float) -> bool:
    """Check if a session should continue: the stop latch first, then the elapsed time.

    Args:
        start_time: datetime when the session started (or None)
        session_duration_minutes: max duration in minutes

    Returns:
        True if session should continue, False once the latch is set or the time limit reached
    """
    halt = run_halt.arret_demande()
    if halt:
        logger.warning(f"Scraping stops: {halt['code']}")
        return False
    if not start_time:
        return True
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    return elapsed < session_duration_minutes
