"""Runtime dispatcher support for the TikTok bridge entrypoint."""

from __future__ import annotations

import json
from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error


class UnknownWorkflowError(RuntimeError):
    """Raised after emitting the historical unknown-workflow JSON error."""


def load_dispatcher_config(argv: list[str]) -> Dict[str, Any] | None:
    """Load the TikTok dispatcher config from CLI arguments."""
    if len(argv) < 2:
        send_error("No config file provided")
        logger.error("No config file provided")
        return None

    config_path = argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        logger.error(f"Failed to load config from {config_path}: {e}")
        return None


def reset_network_if_enabled(config: Dict[str, Any], device_id: str) -> None:
    """Perform the optional pre-session network reset requested by Electron."""
    network_reset = config.get("networkReset", {})
    if not network_reset.get("enabled", False):
        return

    from bridges.common.device.network import perform_network_reset

    perform_network_reset(device_id, method=network_reset.get("method", "data"), ipc=_ipc)


def dispatch_tiktok_workflow(config: Dict[str, Any]) -> tuple[bool, str]:
    """Dispatch a TikTok workflow config to its bridge runner."""
    workflow_type = config.get("workflowType", "for_you")

    if workflow_type == "for_you":
        from bridges.tiktok.workflows.automation.for_you import run_for_you_workflow

        return run_for_you_workflow(config), workflow_type

    if workflow_type == "search" or workflow_type == "hashtag":
        from bridges.tiktok.workflows.automation.search import run_search_workflow

        return run_search_workflow(config), workflow_type

    if workflow_type == "target" or workflow_type == "followers":
        from bridges.tiktok.workflows.automation.followers import run_followers_workflow

        return run_followers_workflow(config), workflow_type

    if workflow_type == "dm_read":
        from bridges.tiktok.workflows.engagement.dm_read import run_dm_read_workflow

        return run_dm_read_workflow(config), workflow_type

    if workflow_type == "dm_send":
        from bridges.tiktok.workflows.engagement.dm_send import run_dm_send_workflow

        return run_dm_send_workflow(config), workflow_type

    if workflow_type == "scraping":
        from bridges.tiktok.scraping.scraping import run_scraping_workflow

        return run_scraping_workflow(config), workflow_type

    send_error(f"Unknown workflow type: {workflow_type}")
    logger.error(f"Unknown workflow type: {workflow_type}")
    raise UnknownWorkflowError(workflow_type)


def force_stop_tiktok(device_id: str) -> None:
    """Best-effort cleanup after a dispatcher workflow run."""
    from bridges.common.device.app_manager import force_stop_app

    force_stop_app(device_id, "tiktok")


__all__ = [
    "dispatch_tiktok_workflow",
    "force_stop_tiktok",
    "load_dispatcher_config",
    "reset_network_if_enabled",
    "UnknownWorkflowError",
]
