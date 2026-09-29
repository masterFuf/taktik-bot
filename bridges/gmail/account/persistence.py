"""Persistence adapters for the Gmail account bridge."""

from typing import Callable


def persist_gmail_account(email: str, device_id: str, send_log: Callable[[str, str], None]) -> None:
    """Persist a Gmail account through the core repository owner."""
    from taktik.core.database.repositories.gmail import GmailAccountRepository

    if not GmailAccountRepository().upsert(email, device_id):
        send_log("warning", f"Could not persist Gmail account {email}")


def unpersist_gmail_account(email: str, send_log: Callable[[str, str], None]) -> None:
    """Remove a Gmail account through the core repository owner."""
    from taktik.core.database.repositories.gmail import GmailAccountRepository

    if not GmailAccountRepository().delete(email):
        send_log("warning", f"Could not unpersist Gmail account {email}")
