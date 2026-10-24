"""Config validation for compat selector diagnostics."""

from dataclasses import dataclass
import sys


@dataclass
class SelectorTestRequest:
    device_id: str
    app_name: str
    version: str
    domain_filter: list


def load_selector_test_request(ipc, config: dict) -> SelectorTestRequest:
    """Validate a selector-test config and emit legacy IPC errors on failure."""
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

