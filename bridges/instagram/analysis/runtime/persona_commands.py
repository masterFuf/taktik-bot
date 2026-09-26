"""Run of the Instagram Persona Analysis bridge, from the config `run_bridge_main` read."""

from __future__ import annotations

import json
import sys
import traceback

from bridges.instagram.runtime.ipc import logger


def report_persona_entry_error(message: str, _reason: str) -> None:
    """An entry failure (no file, unreadable file), in the bridge's own final JSON."""
    print(json.dumps({"success": False, "error": message}))


class PersonaAnalysisRun:
    """One persona analysis, from its config file (read by `run_bridge_main`)."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        run_persona_analysis(self.config)
        return 0


def run_persona_analysis(config: dict) -> None:
    """Connect the bridge and emit the final JSON result."""
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

    from bridges.instagram.analysis.runtime.persona_bridge import PersonaAnalysisBridge

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
