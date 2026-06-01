"""Shared action-test runner for compat diagnostics bridges."""

import json
import sys
import traceback

from loguru import logger

from bridges.compat.diagnostics.runtime.events import emit
from bridges.compat.diagnostics.runtime.tracing import SelectorTracer, TracedSelector


def run_action_test_bridge(action_registry: dict, create_device_facade, build_action_bundle) -> None:
    """Run one compat diagnostics action while preserving the JSON stdout protocol."""
    if len(sys.argv) < 2:
        emit({"type": "result", "success": False, "message": "No config file provided"})
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8-sig") as file_obj:
            config = json.load(file_obj)
    except Exception as exc:
        emit({"type": "result", "success": False, "message": f"Failed to read config: {exc}"})
        sys.exit(1)

    device_id = config.get("device_id", "")
    action_id = config.get("action_id", "")
    params = config.get("params", {})

    if not device_id:
        emit({"type": "result", "success": False, "message": "Missing device_id"})
        sys.exit(1)

    if not action_id:
        emit({"type": "result", "success": False, "message": "Missing action_id"})
        sys.exit(1)

    if action_id not in action_registry:
        emit({"type": "result", "success": False, "message": f"Unknown action: '{action_id}'. Available: {sorted(action_registry.keys())}"})
        sys.exit(1)

    logger.info(f"Connecting to device: {device_id}")
    try:
        from taktik.core.shared.device.manager import DeviceManager

        device_manager = DeviceManager(device_id=device_id)
        if not device_manager.connect(verify_atx=False):
            emit({"type": "result", "success": False, "message": f"Could not connect to device {device_id}"})
            sys.exit(1)
        raw_device = device_manager.device

        logger.info(f"Connected to {device_id}")
    except Exception as exc:
        emit({"type": "result", "success": False, "message": f"Device connection failed: {exc}"})
        sys.exit(1)

    logger.info(f"Building bundle for action: {action_id}")
    try:
        device_facade = create_device_facade(raw_device)
        bundle = build_action_bundle(device_facade)
    except Exception as exc:
        emit({"type": "result", "success": False, "message": f"Action init failed: {exc}\n{traceback.format_exc()}"})
        sys.exit(1)

    tracer = _install_selector_tracer(device_facade)
    _execute_action(action_registry, action_id, bundle, params, tracer)


def _install_selector_tracer(device_facade):
    tracer = SelectorTracer()
    original_xpath = device_facade._device.xpath

    def traced_xpath(expr, *args, **kwargs):
        return TracedSelector(original_xpath(expr, *args, **kwargs), expr, tracer)

    device_facade._device.xpath = traced_xpath
    return tracer


def _execute_action(action_registry: dict, action_id: str, bundle, params: dict, tracer: SelectorTracer) -> None:
    try:
        fn = action_registry[action_id]
        result = fn(bundle, params)
        success = bool(result)
        message = f"Action '{action_id}' {'succeeded' if success else 'failed'}"
        matched = sum(1 for trace in tracer.traces if trace["found"])
        logger.info(f"{'✅' if success else '❌'} {message} — selectors: {matched}/{len(tracer.traces)} matched")
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
        logger.error(f"Action '{action_id}' raised exception: {exc}\n{tb}")
        emit(
            {
                "type": "result",
                "success": False,
                "message": f"Exception: {exc}",
                "selector_traces": tracer.traces,
            }
        )
        sys.exit(1)


__all__ = ["run_action_test_bridge"]
