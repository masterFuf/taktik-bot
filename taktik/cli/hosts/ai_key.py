"""The AI key of a CLI run, and its provider: asked for at launch when the run uses AI, never otherwise.

A manual run (no `ai` block enabled, no `messageMode: "ai"`, not the Taktik Agent) needs no key
and never reaches an AI client. A run that uses AI finds its key, in this order: the run's own
config, the environment (`OPENROUTER_API_KEY`, then `ANTHROPIC_API_KEY`: OpenRouter first, where the
measured models are), the key typed earlier in this process, the key saved in the bot's settings
file (`~/.taktik/api_config.json`, the file the API url already lives in). When none is found:

- at a terminal, the key is asked for (hidden input), with the option to save it in that file; an
  Anthropic key (`sk-ant-…`) is kept as one, any other as an OpenRouter key;
- without one (`--json`, a pipe, `CI` set), the run is refused before the phone is touched, with
  a message saying how to give the key, and the exit code `MISSING_KEY_EXIT`.

The key is never read from a flag: it would land in the shell history and the process list.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Mapping, Optional

import click

from taktik.core.ai.credential import (
    KEY_ENV,
    AICredential,
    credential_from_env,
    provider_of_prefix,
    read_credential,
)
from taktik.core.ai.openrouter_policy import PROVIDER_ANTHROPIC, PROVIDER_OPENROUTER, RUN_PROVIDER_ORDER
from taktik.core.shared.config.user_config import (
    read_user_setting,
    user_config_path,
    write_user_setting,
)

#: Name of each provider's key in the bot's settings file.
SAVED_KEY_SETTINGS = {PROVIDER_OPENROUTER: "openrouter_api_key", PROVIDER_ANTHROPIC: "anthropic_api_key"}
#: Exit code of a run refused for want of a key (1 stays "the run failed").
MISSING_KEY_EXIT = 2
#: Runs that are AI by nature, whatever their config says.
AI_ONLY_WORKFLOWS = frozenset({"instagram.engagement.taktik_agent"})

_typed_credential: Optional[AICredential] = None


class MissingAIKeyError(RuntimeError):
    """A run that uses AI has no key, and nobody can be asked for one."""


def run_uses_ai(workflow_id: str, payload: Mapping[str, Any]) -> bool:
    """True when the run asks for AI: the Agent, an enabled `ai` block, or AI-written messages."""
    if workflow_id in AI_ONLY_WORKFLOWS:
        return True
    ai_block = payload.get("ai")
    if isinstance(ai_block, Mapping) and ai_block.get("enabled"):
        return True
    return (payload.get("messageMode") or payload.get("message_mode")) == "ai"


def _payload_credential(payload: Mapping[str, Any]) -> Optional[AICredential]:
    """The key a run's config brings, under any of the names its family's contract declares: the
    `ai` block's, a flat payload's, the Agent's snake_case ones, and the old OpenRouter names."""
    ai_block = payload.get("ai")
    sources = [ai_block, payload] if isinstance(ai_block, Mapping) else [payload]
    for source in sources:
        credential = read_credential(
            source,
            provider_names=("provider", "aiProvider", "ai_provider"),
            key_names=("apiKey", "aiApiKey", "ai_api_key"),
            openrouter_key_names=("openrouterApiKey", "openrouter_api_key"),
        )
        if credential.api_key:
            return credential
    return None


def resolve_cli_credential() -> Optional[AICredential]:
    """The key a CLI run uses when its config brings none: environment, typed, then saved."""
    from_env = credential_from_env()
    if from_env is not None:
        return from_env
    if _typed_credential is not None:
        return _typed_credential
    for provider in RUN_PROVIDER_ORDER:
        saved = read_user_setting(SAVED_KEY_SETTINGS[provider])
        if saved:
            return AICredential(provider=provider, api_key=saved)
    return None


def is_interactive(*, scripted: bool = False) -> bool:
    """Whether someone can be asked: not a scripted run, a terminal on stdin, not under CI."""
    if scripted or os.environ.get("CI", "").strip().lower() not in ("", "0", "false"):
        return False
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def missing_key_message(workflow_id: str) -> str:
    variables = " or ".join(KEY_ENV[provider] for provider in RUN_PROVIDER_ORDER)
    return (
        f"{workflow_id} uses AI and no AI key was found. Set {variables}, "
        f"or run it once at a terminal (without --json) to type the key and save it in "
        f"{user_config_path()}, or turn AI off in the run's config."
    )


def ensure_ai_key(
    workflow_id: str,
    payload: Mapping[str, Any],
    *,
    interactive: bool,
    prompt: Optional[Callable[..., str]] = None,
    confirm: Optional[Callable[..., bool]] = None,
    echo: Callable[[str], None] = print,
) -> Optional[AICredential]:
    """The key of a run that uses AI, asked for when missing; None for a run without AI.

    Raises `MissingAIKeyError` when the run needs a key, none is known and `interactive` is off
    (or the prompt is left empty).
    """
    global _typed_credential
    if not run_uses_ai(workflow_id, payload):
        return None
    credential = _payload_credential(payload) or resolve_cli_credential()
    if credential is not None:
        return credential
    if not interactive:
        raise MissingAIKeyError(missing_key_message(workflow_id))

    prompt = prompt or click.prompt
    confirm = confirm or click.confirm
    echo(f"{workflow_id} uses AI: it needs an OpenRouter key (https://openrouter.ai/keys) "
         f"or an Anthropic key (https://console.anthropic.com).")
    typed = (prompt("OpenRouter or Anthropic API key", hide_input=True, default="", show_default=False) or "").strip()
    if not typed:
        raise MissingAIKeyError(missing_key_message(workflow_id))
    provider = PROVIDER_ANTHROPIC if provider_of_prefix(typed) == PROVIDER_ANTHROPIC else PROVIDER_OPENROUTER
    _typed_credential = AICredential(provider=provider, api_key=typed)
    if confirm(f"Save it in {user_config_path()} for the next runs?", default=False):
        saved = write_user_setting(SAVED_KEY_SETTINGS[provider], typed)
        echo(f"Key saved in {saved}." if saved else "The key could not be saved; it is used for this run only.")
    return _typed_credential


def forget_typed_key() -> None:
    """Drop the key typed in this process (tests, a long-lived menu session)."""
    global _typed_credential
    _typed_credential = None


__all__ = [
    "AI_ONLY_WORKFLOWS",
    "MISSING_KEY_EXIT",
    "MissingAIKeyError",
    "SAVED_KEY_SETTINGS",
    "ensure_ai_key",
    "forget_typed_key",
    "is_interactive",
    "missing_key_message",
    "resolve_cli_credential",
    "run_uses_ai",
]
