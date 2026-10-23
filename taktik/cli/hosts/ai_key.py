"""The AI key of a CLI run, and its provider: asked for at launch when the run uses AI, never otherwise.

A manual run needs no key and never reaches an AI client. Which runs ask for the AI is not decided
here: it is the engine's declaration of the workflow (`WorkflowContract.ai_request`, read by
`asks_for_ai`: the `ai` block switched on, the messages written by an AI, the Taktik Agent). A run that
uses AI finds its key, in this order: the run's own
config, the environment (`OPENROUTER_API_KEY`, then `ANTHROPIC_API_KEY`: OpenRouter first, where the
measured models are), the key typed earlier in this process, the key saved in the bot's settings
file (`~/.taktik/api_config.json`, the file the API url already lives in). When none is found:

- at a terminal, the key is asked for (hidden input), with the option to save it in that file; an
  Anthropic key (`sk-ant-…`) is kept as one, any other as an OpenRouter key;
- without one (`--json`, a pipe, `CI` set), the run is refused before the phone is touched, with
  `missing_ai_key` (the code of the app's launch gate, `MissingAIKeyError`), a message saying how to give
  the key, and the exit code `MISSING_KEY_EXIT`.

A key is a key when it is long enough to be one (`AICredential.usable`): a shorter one is no key, and the AI
service would go on without AI where the run asked for it.

The key is never read from a flag: it would land in the shell history and the process list.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Mapping, NoReturn, Optional

import click

from taktik.core.ai.credential import (
    KEY_ENV,
    AICredential,
    MissingAIKeyError,
    credential_from_env,
    provider_of_prefix,
    read_credential,
)
from taktik.core.contract.ai_request import asks_for_ai
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

_typed_credential: Optional[AICredential] = None


def _payload_credential(payload: Mapping[str, Any]) -> Optional[AICredential]:
    """The key a run's config brings, under any of the names its family's contract declares: the
    `ai` block's, a flat payload's, the Agent's snake_case ones, and the old OpenRouter names. One that is
    no key (too short) is not returned: the CLI's own is looked for instead."""
    ai_block = payload.get("ai")
    sources = [ai_block, payload] if isinstance(ai_block, Mapping) else [payload]
    for source in sources:
        credential = read_credential(
            source,
            provider_names=("provider", "aiProvider", "ai_provider"),
            key_names=("apiKey", "aiApiKey", "ai_api_key"),
            openrouter_key_names=("openrouterApiKey", "openrouter_api_key"),
        )
        if credential.usable:
            return credential
    return None


def resolve_cli_credential() -> Optional[AICredential]:
    """The key a CLI run uses when its config brings none: environment, typed, then saved; the first
    that is a key (`AICredential.usable`)."""
    from_env = credential_from_env()
    if from_env is not None and from_env.usable:
        return from_env
    if _typed_credential is not None and _typed_credential.usable:
        return _typed_credential
    for provider in RUN_PROVIDER_ORDER:
        saved = read_user_setting(SAVED_KEY_SETTINGS[provider])
        if saved and AICredential(provider=provider, api_key=saved).usable:
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


def missing_key_error(workflow_id: str) -> MissingAIKeyError:
    """The refusal of a run that asks for the AI and has no key: `missing_ai_key`, and how to give one."""
    return MissingAIKeyError(missing_key_message(workflow_id))


def exit_without_key(error: MissingAIKeyError, console: Any) -> NoReturn:
    """Say the refusal of a run that asks for the AI and has no key, and leave with `MISSING_KEY_EXIT`: the
    one way every command that starts a run ends it (`workflows run`, the Agent, `automation`)."""
    console.print(f"[red]{error}[/red]")
    raise SystemExit(MISSING_KEY_EXIT)


def require_cli_credential() -> AICredential:
    """The CLI's key for a run that asks for the AI without bringing one: the environment's, the one typed,
    the saved one. A run behind the door (`ensure_ai_key`) always finds it; one that does not is refused
    here, `missing_ai_key`, instead of going on without the AI it asked for."""
    credential = resolve_cli_credential()
    if credential is None:
        raise missing_key_error("this run")
    return credential


def ai_block_with_key(ai_config: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """The run's `ai` block with a key, the CLI's when the run brings none (or one too short to be a key);
    None when the AI is off. The AI on without any key is refused (`missing_ai_key`)."""
    block = dict(ai_config or {})
    if not block.get("enabled"):
        return None
    brought = read_credential(block, provider_names=("provider",), key_names=("apiKey",),
                              openrouter_key_names=("openrouterApiKey",))
    if not brought.usable:
        credential = require_cli_credential()
        block["provider"] = credential.provider
        block["apiKey"] = credential.api_key
    return block


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
    (or the prompt is left empty, or holds no key).
    """
    global _typed_credential
    if not asks_for_ai(workflow_id, payload):
        return None
    credential = _payload_credential(payload) or resolve_cli_credential()
    if credential is not None:
        return credential
    if not interactive:
        raise missing_key_error(workflow_id)

    prompt = prompt or click.prompt
    confirm = confirm or click.confirm
    echo(f"{workflow_id} uses AI: it needs an OpenRouter key (https://openrouter.ai/keys) "
         f"or an Anthropic key (https://console.anthropic.com).")
    typed = (prompt("OpenRouter or Anthropic API key", hide_input=True, default="", show_default=False) or "").strip()
    provider = PROVIDER_ANTHROPIC if provider_of_prefix(typed) == PROVIDER_ANTHROPIC else PROVIDER_OPENROUTER
    if not AICredential(provider=provider, api_key=typed).usable:
        raise missing_key_error(workflow_id)
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
    "MISSING_KEY_EXIT",
    "MissingAIKeyError",
    "SAVED_KEY_SETTINGS",
    "ai_block_with_key",
    "ensure_ai_key",
    "exit_without_key",
    "forget_typed_key",
    "is_interactive",
    "missing_key_error",
    "missing_key_message",
    "require_cli_credential",
    "resolve_cli_credential",
]
