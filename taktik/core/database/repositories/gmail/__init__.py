"""Gmail repositories.

Gmail and YouTube bridges share the `gmail_accounts` table because both use the
same Google account identity.
"""

from taktik.core.database.repositories.gmail.gmail_account_repository import (
    GmailAccountRepository,
)

__all__ = ["GmailAccountRepository"]
