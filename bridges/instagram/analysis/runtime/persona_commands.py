"""CLI command handling for the Instagram Persona Analysis bridge."""

from __future__ import annotations

import json
import sys
import traceback

from bridges.instagram.runtime.ipc import logger


def run_persona_analysis_cli(args: list[str]) -> None:
    """Load config, connect the bridge and emit the final JSON result."""
    if len(args) < 1:
        print(json.dumps({"success": False, "error": "Usage: persona_analysis_bridge.py <config.json>"}))
        sys.exit(1)

    config_path = args[0]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to read config: {e}"}))
        sys.exit(1)

    device_id = config.get("deviceId")
    package_name = config.get("packageName")

    if not device_id:
        print(json.dumps({"success": False, "error": "deviceId is required"}))
        sys.exit(1)

    try:
        from taktik.core.database import configure_db_service

        configure_db_service()
        logger.info("[PersonaAnalysis] Database service configured")
    except Exception as exc:
        logger.warning(f"[PersonaAnalysis] Could not configure DB service: {exc}")

    from bridges.instagram.analysis.persona import PersonaAnalysisBridge

    bridge = PersonaAnalysisBridge(device_id, config, package_name=package_name)

    if not bridge.connect():
        print(json.dumps({"success": False, "error": f"Failed to connect to device {device_id}"}), flush=True)
        sys.exit(1)

    try:
        result = bridge.run()
    except Exception as e:
        traceback.print_exc()
        result = {"success": False, "error": f"Bridge crashed: {e}"}
    print(json.dumps(result), flush=True)
