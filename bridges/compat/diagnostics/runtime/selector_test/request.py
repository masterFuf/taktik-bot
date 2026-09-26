"""Config validation for compat selector diagnostics."""

from dataclasses import dataclass
import sys

from bridges.common.runtime.entrypoint import MISSING_CONFIG


@dataclass
class SelectorTestRequest:
    device_id: str
    app_name: str
    version: str
    domain_filter: list


def report_selector_test_entry_error(ipc):
    """Entry failures (no file, unreadable file) as the Lab's error events."""

    def report(message: str, reason: str) -> None:
        code = "MISSING_CONFIG" if reason == MISSING_CONFIG else "CONFIG_ERROR"
        ipc.send("error", error=message, error_code=code)

    return report


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


__all__ = ["SelectorTestRequest", "load_selector_test_request", "report_selector_test_entry_error"]

