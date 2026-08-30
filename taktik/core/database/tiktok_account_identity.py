"""Which account row a TikTok run belongs to.

One function because it was wrong in two places, the same way, for the same reason.

`get_db_service().get_or_create_account(...)` LOOKS platform-neutral and is not: it delegates to
the Instagram account repository, whose query is `WHERE platform = 'instagram'`. Called for a
TikTok run it therefore returns -- or creates -- the INSTAGRAM account row that happens to carry
the same handle.

`accounts.legacy_account_id` is numbered per platform, so the id that comes back is a perfectly
valid number belonging to a different account. Nothing errors. Everything written under it simply
never joins to anything TikTok, and the reader sees an account that did nothing.

Measured on 2026-08-30: five TikTok DMs were filed under 6590, the INSTAGRAM id of
@marvin.ndiaye.extraits, while that account's TikTok interactions sit under 4982. The follower
attribution -- "did we engage this person before they followed us?" -- joins notifications to
interactions on `account_id`, so it could only ever have answered no.
"""

from __future__ import annotations

import re
from typing import Optional

from taktik.core.database import configure_db_service, get_db_service

#: A real TikTok handle. Tested on the RAW value: handles are lowercase by construction, so a
#: capital proves a string is a display name.
#:
#: At least one letter or digit is REQUIRED. Without that, `..........` matched -- and that is not
#: a hypothetical string: it is what an emoji-only display name looks like after the XML dump has
#: eaten it. Filed as a handle it would join to nothing, which is the one thing this test exists
#: to prevent.
_HANDLE_RE = re.compile(r"^(?=.*[a-z0-9])[a-z0-9._]{1,24}$")


def looks_like_tiktok_handle(value: Optional[str]) -> bool:
    """True only for something that could be a TikTok @handle."""
    return bool(value) and bool(_HANDLE_RE.match(value.strip()))


def resolve_tiktok_account_id(username: Optional[str], *, logger=None) -> Optional[int]:
    """The `accounts` id of a TikTok account, created if it does not exist yet.

    Goes through the TikTok repository (`platform = 'tiktok'`), which is the whole point.
    Returns None rather than guessing when the handle is unreadable: a run filed under the wrong
    account is worse than a run filed under none, because it looks filed.
    """
    handle = (username or "").strip().lower().lstrip("@")
    if not looks_like_tiktok_handle(handle):
        return None
    try:
        configure_db_service()
        service = get_db_service()
        inner = getattr(service, "local_db", service)
        account_id, _created = inner.tiktok.get_or_create_account(handle, is_bot=True)
        return account_id
    except Exception as exc:
        if logger is not None:
            logger.warning(f"Could not resolve TikTok account @{handle}: {exc}")
        return None


__all__ = ["looks_like_tiktok_handle", "resolve_tiktok_account_id"]
