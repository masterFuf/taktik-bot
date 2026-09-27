"""The one reading of an Instagram cold DM payload, for the desktop bridge and the CLI.

The payload is the file the app's main process writes from the Cold DM page or the DM node
(camelCase, recipients already resolved); the CLI and an Agent plan send the same keys. Each key
is read by a plain `.get`, which the app's config contract test can follow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional

from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import ColdDmRecipientPolicy
from taktik.core.social_media.instagram.workflows.cold_dm.session import session_account_id


@dataclass
class ColdDmRequest:
    """What one cold DM run is asked to do."""

    recipients: List[Any]
    messages: List[Any]
    delay_min: Any = 30
    delay_max: Any = 60
    max_dms: Any = 50
    account_id: Any = 1
    session_id: Optional[str] = None
    message_mode: str = "manual"
    ai_prompt: str = ""
    openrouter_api_key: str = ""
    skip_private: bool = True
    skip_verified: bool = False
    session_account_id: Optional[int] = None

    @property
    def recipient_policy(self) -> ColdDmRecipientPolicy:
        return ColdDmRecipientPolicy(skip_private=self.skip_private, skip_verified=self.skip_verified)


def cold_dm_request_from_payload(config: Mapping[str, Any], *,
                                 default_session_id: Optional[str] = None) -> ColdDmRequest:
    """The run a cold DM payload describes; `default_session_id` tags it when the payload does not."""
    return ColdDmRequest(
        recipients=config.get("recipients", []),
        messages=config.get("messages", []),
        delay_min=config.get("delayMin", 30),
        delay_max=config.get("delayMax", 60),
        max_dms=config.get("maxDmsPerSession", 50),
        account_id=config.get("accountId", 1),
        session_id=config.get("sessionId", default_session_id),
        message_mode=config.get("messageMode", "manual"),
        ai_prompt=config.get("aiPrompt", ""),
        openrouter_api_key=config.get("openrouterApiKey", ""),
        # The page's and the scheduler node's « Ignorer les comptes privés / certifiés ». Absent
        # -> the behaviour the engine always had: private profiles skipped, certified ones not.
        skip_private=config.get("skipPrivateAccounts", True) is not False,
        skip_verified=bool(config.get("skipVerifiedAccounts", False)),
        session_account_id=session_account_id(config),
    )


__all__ = ["ColdDmRequest", "cold_dm_request_from_payload"]
