"""Config loading and validation for compat selector diagnostics."""

from dataclasses import dataclass
import json
import sys


@dataclass
class SelectorTestRequest:
    device_id: str
    app_name: str
    version: str
    domain_filter: list


def load_selector_test_request(ipc, argv: list[str]) -> SelectorTestRequest:
    """Load a selector-test config file and emit legacy IPC errors on failure."""
    if len(argv) < 2:
        ipc.send("error", error="No config file provided", error_code="MISSING_CONFIG")
        sys.exit(1)

    config_path = argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as file_obj:
            config = json.load(file_obj)
    except Exception as exc:
        ipc.send("error", error=f"Failed to read config: {exc}", error_code="CONFIG_ERROR")
        sys.exit(1)

    device_id = config.get("device_id", "")
    if not device_id:
        ipc.send("error", error="No device_id provided", error_code="MISSING_DEVICE")
        sys.exit(1)

    return SelectorTestRequest(
        device_id=device_id,
        app_name=config.get("app", "instagram"),
        version=config.get("version", ""),
        domain_filter=config.get("domains", []),
    )


__all__ = ["SelectorTestRequest", "load_selector_test_request"]

