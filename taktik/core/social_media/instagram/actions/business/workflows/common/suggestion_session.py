"""Automation session wrapped around a suggestions pass.

What this module solves, and why writing the follows was not enough.

A follow recorded without a session id does exist in the interactions table, but it
belongs to no session — so it surfaces neither in the session history, nor in the
statistics snapshot that finalisation aggregates, nor in what is shown. "The bot won us
that many followers" is read from the sessions; an orphan action is invisible there.

That case was the norm everywhere there is no full automation object: the session id
comes from it, and it existed neither for the diagnostics bench nor for the
notifications bridge. This module therefore opens a REAL session around the pass and
closes it with its statistics snapshot.

It is deliberately tiny and device-free: a suggestions pass does not need the full
automation lifecycle, only a beginning and an end.
fin et d'un identifiant.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from loguru import logger

# Target type written to the database. The front maps this field to a label; an unknown
# value falls into "Other" there, which stays readable but poor.
SUGGESTION_TARGET_TYPE = "SUGGESTIONS"

log = logger.bind(module="instagram-suggestion-session")


def open_suggestion_session(account_id: Optional[int], *, source: str,
                            config: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """Open the session and return its id, or None when impossible.

    Without a resolved account there is no possible session: creating one under the
    default id would attribute the work to someone else, which is worse than having no
    session at all.
    """
    if not account_id:
        log.warning("Pas de compte resolu : la passe de suggestions n'aura pas de session")
        return None
    try:
        from taktik.core.database.local.service import get_local_database

        session_id = get_local_database().create_session(
            account_id=account_id,
            session_name=f"Suggestions ({source})",
            target_type=SUGGESTION_TARGET_TYPE,
            target=source,
            config_used=config,
        )
        if session_id:
            log.info(f"Session de suggestions {session_id} ouverte (source: {source})")
        return session_id
    except Exception as exc:  # noqa: BLE001 — never fatal for the pass
        log.warning(f"Impossible d'ouvrir une session de suggestions: {exc}")
        return None


def close_suggestion_session(session_id: Optional[int], *, status: str = "COMPLETED",
                             duration_seconds: Optional[int] = None,
                             error_message: Optional[str] = None) -> None:
    """Close the session AND write its statistics snapshot.

    Finalisation, not a plain update, because only finalisation aggregates the session
    interactions into its statistics columns. Without that call the session would stay
    active, with no end time and zeroed counters while the follows sit in the database —
    exactly the kind of gap that casts doubt on every other figure.
    """
    if not session_id:
        return
    try:
        from taktik.core.database.local.service import get_local_database

        get_local_database().finalize_session(
            session_id, status,
            duration_seconds=duration_seconds,
            error_message=error_message,
        )
        log.info(f"Session de suggestions {session_id} cloturee ({status})")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Impossible de cloturer la session {session_id}: {exc}")


@contextmanager
def suggestion_session(account_id: Optional[int], *, source: str,
                       config: Optional[Dict[str, Any]] = None):
    """Open the session, hand it to the caller, close it whatever happens.

    A pass interrupted by an exception is closed in error rather than left active: a
    session that never ends skews the averages as much as a missing one.
    manquante.
    """
    session_id = open_suggestion_session(account_id, source=source, config=config)
    started = time.time()
    status, error = "COMPLETED", None
    try:
        yield session_id
    except BaseException as exc:  # noqa: BLE001 — on requalifie puis on relaie
        status, error = "ERROR", str(exc)[:200]
        raise
    finally:
        close_suggestion_session(
            session_id, status=status,
            duration_seconds=int(time.time() - started),
            error_message=error,
        )


__all__ = [
    "SUGGESTION_TARGET_TYPE",
    "close_suggestion_session",
    "open_suggestion_session",
    "suggestion_session",
]
