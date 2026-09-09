"""Small shared account-identity helpers for social account workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


def normalize_account_username(value: object) -> str:
    """Normalize an account handle for comparison."""
    return str(value or "").strip().lstrip("@").lower()


def is_account_username(value: object, *, max_length: int = 30) -> bool:
    """Check whether *value* has the conservative shape of an account handle."""
    username = normalize_account_username(value)
    if max_length < 1:
        return False
    return bool(re.fullmatch(rf"(?=.*[a-z0-9])[a-z0-9._]{{1,{max_length}}}", username))


@dataclass(frozen=True)
class AccountCatalog:
    """Normalized account names plus names represented by multiple UI rows."""

    accounts: tuple[str, ...]
    ambiguous: tuple[str, ...] = ()

    @classmethod
    def from_values(
        cls,
        values: Iterable[object],
        *,
        max_length: int = 30,
    ) -> "AccountCatalog":
        accounts: list[str] = []
        duplicates: list[str] = []
        counts: dict[str, int] = {}
        for value in values:
            username = normalize_account_username(value)
            if not is_account_username(username, max_length=max_length):
                continue
            counts[username] = counts.get(username, 0) + 1
            if counts[username] == 1:
                accounts.append(username)
            elif counts[username] == 2:
                duplicates.append(username)
        return cls(tuple(accounts), tuple(duplicates))

    def contains(self, username: object) -> bool:
        return normalize_account_username(username) in self.accounts

    def is_ambiguous(self, username: object) -> bool:
        return normalize_account_username(username) in self.ambiguous


__all__ = [
    "AccountCatalog",
    "is_account_username",
    "normalize_account_username",
]
