#!/usr/bin/env python3
"""
Compat Bridge — Electron-spawnable bridge for the App Compatibility Framework.

Follows the same stdout JSON protocol as all other bridges.
Spawned by electron/handlers/compat/compat.ts via ProcessManager.

Commands:
  - "get_registry": Return the full selector registry for an app/version
  - "list_actions": List all known selector action names for an app
  - "get_selector": Get a specific selector for app/version/action
  - "check_selectors": Validate that selectors exist for an app/version

Config JSON (passed as argv[1] temp file):
  {
    "command": "get_registry",
    "app": "instagram",
    "version": "410.0.0.53.71",
    "action": "feed.like_button"   // only for get_selector
  }
"""

import sys
import os
import json

# Bootstrap: ensure bot root is in sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.ipc import IPC
from loguru import logger
from taktik.core.compat import create_registry, SelectorNotFound


def main():
    ipc = IPC()

    # Parse config from temp file (argv[1])
    if len(sys.argv) < 2:
        ipc.send("error", error="No config file provided", error_code="MISSING_CONFIG")
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        ipc.send("error", error=f"Failed to read config: {e}", error_code="CONFIG_ERROR")
        sys.exit(1)

    command = config.get("command", "")
    app_name = config.get("app", "")
    version = config.get("version", "")

    logger.info(f"[CompatBridge] command={command} app={app_name} version={version}")

    # Initialize the registry (loads all existing selectors + YAML overrides)
    try:
        registry = create_registry()
    except Exception as e:
        ipc.send("error", error=f"Failed to create registry: {e}", error_code="REGISTRY_INIT_ERROR")
        sys.exit(1)

    ipc.send("status", status="ready", message="Registry initialized")

    # Dispatch command
    if command == "get_registry":
        handle_get_registry(ipc, registry, app_name, version)
    elif command == "list_actions":
        handle_list_actions(ipc, registry, app_name)
    elif command == "get_selector":
        action = config.get("action", "")
        handle_get_selector(ipc, registry, app_name, version, action)
    elif command == "check_selectors":
        handle_check_selectors(ipc, registry, app_name, version)
    else:
        ipc.send("error", error=f"Unknown command: {command}", error_code="UNKNOWN_COMMAND")
        sys.exit(1)


def handle_get_registry(ipc: IPC, registry, app_name: str, version: str):
    """Return the full selector registry as JSON."""
    try:
        data = registry.to_dict(app_name, version)
        ipc.send("registry_data", **data)
    except Exception as e:
        ipc.send("error", error=str(e), error_code="REGISTRY_ERROR")


def handle_list_actions(ipc: IPC, registry, app_name: str):
    """List all known action names for an app."""
    try:
        actions = registry.list_actions(app_name)
        ipc.send("actions_list", app=app_name, actions=actions, count=len(actions))
    except Exception as e:
        ipc.send("error", error=str(e), error_code="LIST_ERROR")


def handle_get_selector(ipc: IPC, registry, app_name: str, version: str, action: str):
    """Get a specific selector."""
    try:
        entry = registry.get(app_name, version, action)
        ipc.send(
            "selector",
            app=app_name,
            version=version,
            action=action,
            xpaths=entry.xpaths,
            source=entry.source,
        )
    except SelectorNotFound as e:
        ipc.send(
            "selector_not_found",
            app=e.app,
            version=e.version,
            action=e.action,
        )
    except Exception as e:
        ipc.send("error", error=str(e), error_code="SELECTOR_ERROR")


def handle_check_selectors(ipc: IPC, registry, app_name: str, version: str):
    """Validate all selectors exist for a version, report any missing."""
    try:
        all_selectors = registry.get_all(app_name, version)
        current_version = registry.get_current_version(app_name)
        override_versions = registry.get_override_versions(app_name)

        # Count sources
        python_count = sum(1 for e in all_selectors.values() if e.source == "python")
        yaml_count = sum(1 for e in all_selectors.values() if e.source == "yaml")

        ipc.send(
            "check_result",
            app=app_name,
            version=version,
            current_version=current_version,
            override_versions=override_versions,
            total_selectors=len(all_selectors),
            python_selectors=python_count,
            yaml_selectors=yaml_count,
            is_current_version=(version == current_version),
            status="OK",
        )
    except Exception as e:
        ipc.send("error", error=str(e), error_code="CHECK_ERROR")


if __name__ == "__main__":
    main()
