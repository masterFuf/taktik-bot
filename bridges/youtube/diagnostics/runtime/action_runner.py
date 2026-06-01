"""Runtime runner for the YouTube action-test diagnostic bridge."""

import sys
import traceback

from bridges.youtube.diagnostics.runtime.events import emit, log
from bridges.youtube.diagnostics.runtime.request import (
    load_youtube_action_test_config,
    validate_youtube_action_test_config,
)
from bridges.youtube.diagnostics.runtime.registry import ACTION_REGISTRY
from bridges.youtube.diagnostics.runtime.tracing import SelectorTracer, TracedSelector


def run_youtube_action_test(argv: list[str]) -> None:
    _bootstrap_bot_path()

    if len(argv) < 2:
        emit({"type": "result", "success": False, "message": "No config file provided"})
        sys.exit(1)

    try:
        config = load_youtube_action_test_config(argv[1])
    except Exception as exc:
        emit({"type": "result", "success": False, "message": f"Failed to read config: {exc}"})
        sys.exit(1)

    request = validate_youtube_action_test_config(config)
    if request is None:
        sys.exit(1)

    try:
        raw_device = _connect_device(request.device_id)
    except Exception as exc:
        emit({"type": "result", "success": False, "message": f"Device connection failed: {exc}"})
        sys.exit(1)

    try:
        selectors = _load_selectors()
    except Exception as exc:
        emit({"type": "result", "success": False, "message": f"Failed to load YouTube selectors: {exc}"})
        sys.exit(1)

    tracer = _install_selector_tracer(raw_device)
    _run_action(raw_device, selectors, request.action_id, request.params, tracer)


def _bootstrap_bot_path() -> None:
    """Bootstrap sys.path so direct script launches can import `taktik`."""
    import os

    bot_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    )
    if bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)


def _connect_device(device_id: str):
    log("info", f"Connecting to device: {device_id}")
    from taktik.core.shared.device.manager import DeviceManager

    device_manager = DeviceManager(device_id=device_id)
    if not device_manager.connect(verify_atx=False):
        emit({"type": "result", "success": False, "message": f"Could not connect to device {device_id}"})
        sys.exit(1)

    log("info", f"Connected to {device_id}")
    return device_manager.device


def _load_selectors():
    from taktik.core.social_media.youtube.ui.selectors.upload import UPLOAD_SELECTORS

    return UPLOAD_SELECTORS


def _install_selector_tracer(raw_device):
    tracer = SelectorTracer()
    original_xpath = raw_device.xpath

    def traced_xpath(expr, *args, **kwargs):
        return TracedSelector(original_xpath(expr, *args, **kwargs), expr, tracer)

    raw_device.xpath = traced_xpath
    return tracer


def _run_action(raw_device, selectors, action_id: str, params: dict, tracer: SelectorTracer) -> None:
    try:
        result = ACTION_REGISTRY[action_id](raw_device, params, selectors)
        success = bool(result)
        message = f"Action '{action_id}' {'succeeded' if success else 'failed'}"
        matched = sum(1 for trace in tracer.traces if trace["found"])
        log("info", f"{message}; selectors: {matched}/{len(tracer.traces)} matched")
        emit(
            {
                "type": "result",
                "success": success,
                "message": message,
                "selector_traces": tracer.traces,
            }
        )
    except Exception as exc:
        tb = traceback.format_exc()
        log("error", f"Action '{action_id}' raised exception: {exc}\n{tb}")
        emit(
            {
                "type": "result",
                "success": False,
                "message": f"Exception: {exc}",
                "selector_traces": tracer.traces,
            }
        )
        sys.exit(1)


__all__ = ["run_youtube_action_test"]
