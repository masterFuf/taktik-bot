"""Account-level repositories (Gmail/YouTube share the `gmail_accounts` table)."""

from taktik.core.database.repositories.accounts.gmail_account_repository import (
    GmailAccountRepository,
)

__all__ = ["GmailAccountRepository"]
