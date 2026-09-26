"""The bot's own settings file, `~/.taktik/api_config.json`.

One file for what a standalone user keeps between runs: the API url (`api_url`) and, when the CLI
user chose to save it, the OpenRouter key (`openrouter_api_key`). The desktop app does not use
it: it sends its settings in each run's config.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from loguru import logger

CONFIG_DIR_NAME = ".taktik"
CONFIG_FILE_NAME = "api_config.json"


def user_config_path() -> str:
    """Where the file lives, resolved at call time."""
    return os.path.join(os.path.expanduser("~"), CONFIG_DIR_NAME, CONFIG_FILE_NAME)


def read_user_config() -> dict[str, Any]:
    """The whole file, or an empty dict when it is absent or unreadable."""
    path = user_config_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
            return config if isinstance(config, dict) else {}
    except Exception as exc:  # noqa: BLE001 - an unreadable file means "no setting"
        logger.debug(f"Unreadable {path}: {exc}")
    return {}


def read_user_setting(key: str) -> Optional[str]:
    """One setting, stripped; None when absent or empty."""
    value = read_user_config().get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def write_user_setting(key: str, value: str) -> Optional[str]:
    """Write one setting, keeping the others. Returns the file's path, None when it failed."""
    path = user_config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        config = read_user_config()
        config[key] = value
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return path
    except Exception as exc:  # noqa: BLE001 - the caller reports a failed save
        logger.error(f"Could not write {path}: {exc}")
        return None


__all__ = ["read_user_config", "read_user_setting", "user_config_path", "write_user_setting"]
