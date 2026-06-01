"""CLI/config loading for the Instagram scraping bridge."""

from __future__ import annotations

import json


def load_scraping_bridge_config(argv: list[str]) -> dict | None:
    if len(argv) < 2:
        print(json.dumps({"success": False, "error": "No config file provided"}))
        return None

    config_path = argv[1]
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to load config: {e}"}))
        return None

    if not config.get('deviceId'):
        print(json.dumps({"success": False, "error": "No deviceId provided"}))
        return None

    return config
