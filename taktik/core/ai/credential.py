"""The key a run calls the AI with, and the provider that key belongs to: one value, `AICredential`.

A run's payload used to carry one key, `openrouterApiKey`, because OpenRouter was the only
provider. It now carries the provider and the key side by side (in the `ai` block: `provider` and
`apiKey`; in a flat payload: `aiProvider` and `aiApiKey`; in the Taktik Agent's snake_case file:
`ai_provider` and `ai_api_key`). The old names are still read, and only as what they always were:
an OpenRouter key. `read_credential` is the one reader; each payload reader names its own keys, as
its contract declares them.

A key is never sent to a provider whose key it is not: an Anthropic key posted to OpenRouter would
hand it to a third party, and the call would fail anyway. Both providers mark their keys with a
prefix; a key carrying the OTHER provider's prefix is refused before any request. A key with no
known prefix (a test key, a gateway's) is left to its provider to accept or refuse.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from taktik.core.ai.openrouter_policy import (
    AI_PROVIDERS,
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENROUTER,
    RUN_PROVIDER_ORDER,
)

#: How each provider's keys begin (`sk-or-v1-…`, `sk-ant-api03-…`).
KEY_PREFIXES = {PROVIDER_OPENROUTER: "sk-or-", PROVIDER_ANTHROPIC: "sk-ant-"}

#: The environment variable each provider's key is read from, by the CLI and the Agent.
KEY_ENV = {PROVIDER_OPENROUTER: "OPENROUTER_API_KEY", PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY"}

#: A key this short is no key (the rule the hosts already applied: more than 5 characters).
MIN_KEY_LENGTH = 5


@dataclass(frozen=True)
class AICredential:
    """A provider and its key. Never printed: its text says the provider and the key's last four."""

    provider: str = PROVIDER_OPENROUTER
    api_key: str = field(default="", repr=False)

    @property
    def usable(self) -> bool:
        """A key long enough to be one."""
        return len(self.api_key) > MIN_KEY_LENGTH

    def __str__(self) -> str:
        return f"{self.provider} key …{self.api_key[-4:]}" if self.api_key else f"{self.provider}, no key"


#: What a host injects for a run that brings no key (the CLI's environment, typed or saved key).
AICredentialProvider = Callable[[], Optional[AICredential]]


class ForeignKeyError(ValueError):
    """A key handed to a provider is another provider's key; nothing was sent."""


class MissingAIKeyError(RuntimeError):
    """A run that asks for the AI (`contract/ai_request.py`) has no usable key, and nobody can be asked for one.

    `error_code` is the code the app's launch gate gives the same refusal (`contract/error_codes.py`,
    an expected refusal: the remedy is the operator's); the message names it first, so a host that prints
    the exception (the CLI) says the same code.
    """

    error_code = "missing_ai_key"

    def __init__(self, message: str):
        super().__init__(f"{self.error_code}: {message}")


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


def _first_text(payload: Mapping[str, Any], names: Sequence[str]) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def read_credential(
    payload: Mapping[str, Any],
    *,
    provider_names: Sequence[str],
    key_names: Sequence[str],
    openrouter_key_names: Sequence[str] = (),
) -> AICredential:
    """The credential a payload carries, under the names its contract declares.

    `provider_names` and `key_names`: the wire name first, then its aliases. `openrouter_key_names`:
    the old key names, read only when the provider is OpenRouter (absent, it is), since an
    `openrouterApiKey` never held anything else. No key is an empty one, never a guess: the caller
    decides what a run without a key does. An unknown provider is refused (`ValueError`).
    """
    provider = _first_text(payload, provider_names) or PROVIDER_OPENROUTER
    if provider not in AI_PROVIDERS:
        raise ValueError(f"unknown AI provider {provider!r} (expected one of {', '.join(AI_PROVIDERS)})")
    key = _first_text(payload, key_names)
    if not key and provider == PROVIDER_OPENROUTER:
        key = _first_text(payload, openrouter_key_names)
    return AICredential(provider=provider, api_key=key)


def credential_from_env(environ: Optional[Mapping[str, str]] = None) -> Optional[AICredential]:
    """The first provider of `RUN_PROVIDER_ORDER` whose key the environment holds, else None."""
    environ = os.environ if environ is None else environ
    for provider in RUN_PROVIDER_ORDER:
        key = (environ.get(KEY_ENV[provider]) or "").strip()
        if key:
            return AICredential(provider=provider, api_key=key)
    return None


__all__ = [
    "AICredential",
    "AICredentialProvider",
    "ForeignKeyError",
    "KEY_ENV",
    "KEY_PREFIXES",
    "MIN_KEY_LENGTH",
    "MissingAIKeyError",
    "check_key_for",
    "credential_from_env",
    "provider_of_prefix",
    "read_credential",
]
