"""CLI/config command handling for the Instagram Cold DM bridge."""

from __future__ import annotations

import json
import sys

from bridges.instagram.runtime.ipc import logger
from bridges.instagram.engagement.runtime.cold_dm_workflow import ColdDMWorkflow


def run_cold_dm_cli(args: list[str]) -> None:
    """Load Cold DM config from file and run the workflow."""
    if len(args) < 1:
        logger.error("Usage: cold_dm_bridge.py <config_file>")
        sys.exit(1)

    config_file = args[0]

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        device_id = config["deviceId"]
        package_name = config.get("packageName")
        logger.info(
            f"Starting Cold DM workflow for device: {device_id}"
            + (f" (package: {package_name})" if package_name else "")
        )

        workflow = ColdDMWorkflow(device_id, package_name=package_name)

        if not workflow.connect():
            logger.error(f"Failed to connect to device {device_id}")
            print(json.dumps({"success": False, "error": "Failed to connect to device"}))
            sys.exit(1)

        recipients = config.get("recipients", [])
        messages = config.get("messages", [])
        delay_min = config.get("delayMin", 30)
        delay_max = config.get("delayMax", 60)
        max_dms = config.get("maxDmsPerSession", 50)
        account_id = config.get("accountId", 1)
        session_id = config.get("sessionId", device_id)
        ai_prompt = config.get("aiPrompt", "")
        openrouter_api_key = config.get("openrouterApiKey", "")

        message_mode = config.get("messageMode", "manual")
        if message_mode == "ai" and not openrouter_api_key:
            logger.warning("AI mode requested but no OpenRouter API key provided, falling back to manual messages")

        logger.info(f"Cold DM config: {len(recipients)} recipients, {len(messages)} messages, mode: {message_mode}")

        result = workflow.run(
            recipients,
            messages,
            delay_min,
            delay_max,
            max_dms,
            account_id,
            session_id,
            ai_prompt,
            openrouter_api_key,
        )

        print(json.dumps({
            "success": result.get("success", False),
            "dmsSent": result.get("dms_sent", 0),
            "dmsSuccess": result.get("dms_success", 0),
            "dmsFailed": result.get("dms_failed", 0),
            "error": result.get("error"),
        }))

    except Exception as e:
        logger.error(f"Cold DM workflow error: {e}", exc_info=True)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
