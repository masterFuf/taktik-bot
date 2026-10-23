"""The key a run calls the AI with, and the provider that key belongs to.

A key is never sent to a provider whose key it is not: an Anthropic key posted to OpenRouter would
hand it to a third party, and the call would fail anyway. Both providers mark their keys with a
prefix; a key carrying the OTHER provider's prefix is refused before any request. A key with no
known prefix (a test key, a gateway's) is left to its provider to accept or refuse.
"""

from __future__ import annotations

from typing import Optional

from taktik.core.ai.openrouter_policy import AI_PROVIDERS, PROVIDER_ANTHROPIC, PROVIDER_OPENROUTER

#: How each provider's keys begin (`sk-or-v1-…`, `sk-ant-api03-…`).
KEY_PREFIXES = {PROVIDER_OPENROUTER: "sk-or-", PROVIDER_ANTHROPIC: "sk-ant-"}


class ForeignKeyError(ValueError):
    """A key handed to a provider is another provider's key; nothing was sent."""


def provider_of_prefix(api_key: str) -> Optional[str]:
    """The provider whose prefix the key carries, None when it carries none of them."""
    for provider, prefix in KEY_PREFIXES.items():
        if (api_key or "").strip().startswith(prefix):
            return provider
    return None


def check_key_for(provider: str, api_key: str) -> None:
    """Raise when `provider` is unknown, or when the key is visibly another provider's."""
    if provider not in AI_PROVIDERS:
        raise ValueError(f"unknown AI provider {provider!r} (expected one of {', '.join(AI_PROVIDERS)})")
    owner = provider_of_prefix(api_key)
    if owner is not None and owner != provider:
        raise ForeignKeyError(f"the key given for {provider} is a {owner} key: it was not sent")


__all__ = ["ForeignKeyError", "KEY_PREFIXES", "check_key_for", "provider_of_prefix"]
