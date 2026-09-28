"""The OpenRouter key of a CLI run: asked for at launch when the run uses AI, never otherwise.

A manual run (no `ai` block enabled, no `messageMode: "ai"`, not the Taktik Agent) needs no key
and never reaches an AI client. A run that uses AI finds its key, in this order: the run's own
config, the `OPENROUTER_API_KEY` environment variable, the key typed earlier in this process, the
key saved in the bot's settings file (`~/.taktik/api_config.json`, the file the API url already
lives in). When none is found:

- at a terminal, the key is asked for (hidden input), with the option to save it in that file;
- without one (`--json`, a pipe, `CI` set), the run is refused before the phone is touched, with
  a message saying how to give the key, and the exit code `MISSING_KEY_EXIT`.

The key is never read from a flag: it would land in the shell history and the process list.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Mapping, Optional

import click

from taktik.core.app.config.runtime.user_config import (
    read_user_setting,
    user_config_path,
    write_user_setting,
)

OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"
#: Name of the key in the bot's settings file.
SAVED_KEY_SETTING = "openrouter_api_key"
#: Exit code of a run refused for want of a key (1 stays "the run failed").
MISSING_KEY_EXIT = 2
#: Runs that are AI by nature, whatever their config says.
AI_ONLY_WORKFLOWS = frozenset({"instagram.engagement.taktik_agent"})

#: Keys a run's config may carry its OpenRouter key under.
_PAYLOAD_KEY_FIELDS = ("openrouterApiKey", "openrouter_api_key")

_typed_key: Optional[str] = None


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


def _payload_key(payload: Mapping[str, Any]) -> Optional[str]:
    ai_block = payload.get("ai")
    sources = [payload, ai_block] if isinstance(ai_block, Mapping) else [payload]
    for source in sources:
        for field in _PAYLOAD_KEY_FIELDS:
            value = source.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def resolve_openrouter_key() -> Optional[str]:
    """The key a CLI run uses when its config brings none: environment, typed, then saved."""
    key = os.environ.get(OPENROUTER_KEY_ENV, "").strip()
    return key or _typed_key or read_user_setting(SAVED_KEY_SETTING)


def is_interactive(*, scripted: bool = False) -> bool:
    """Whether someone can be asked: not a scripted run, a terminal on stdin, not under CI."""
    if scripted or os.environ.get("CI", "").strip().lower() not in ("", "0", "false"):
        return False
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def missing_key_message(workflow_id: str) -> str:
    return (
        f"{workflow_id} uses AI and no OpenRouter key was found. Set {OPENROUTER_KEY_ENV}, "
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
) -> Optional[str]:
    """The key of a run that uses AI, asked for when missing; None for a run without AI.

    Raises `MissingAIKeyError` when the run needs a key, none is known and `interactive` is off
    (or the prompt is left empty).
    """
    global _typed_key
    if not run_uses_ai(workflow_id, payload):
        return None
    key = _payload_key(payload) or resolve_openrouter_key()
    if key:
        return key
    if not interactive:
        raise MissingAIKeyError(missing_key_message(workflow_id))

    prompt = prompt or click.prompt
    confirm = confirm or click.confirm
    echo(f"{workflow_id} uses AI: it needs an OpenRouter key (https://openrouter.ai/keys).")
    typed = (prompt("OpenRouter API key", hide_input=True, default="", show_default=False) or "").strip()
    if not typed:
        raise MissingAIKeyError(missing_key_message(workflow_id))
    _typed_key = typed
    if confirm(f"Save it in {user_config_path()} for the next runs?", default=False):
        saved = write_user_setting(SAVED_KEY_SETTING, typed)
        echo(f"Key saved in {saved}." if saved else "The key could not be saved; it is used for this run only.")
    return typed


def forget_typed_key() -> None:
    """Drop the key typed in this process (tests, a long-lived menu session)."""
    global _typed_key
    _typed_key = None


__all__ = [
    "AI_ONLY_WORKFLOWS",
    "MISSING_KEY_EXIT",
    "MissingAIKeyError",
    "OPENROUTER_KEY_ENV",
    "SAVED_KEY_SETTING",
    "ensure_ai_key",
    "forget_typed_key",
    "is_interactive",
    "missing_key_message",
    "resolve_openrouter_key",
    "run_uses_ai",
]
