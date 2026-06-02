"""Shared action-test runner for compat diagnostics bridges."""

import json
import sys
import time
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
        emit(
            {
                "type": "result",
                "success": False,
                "message": f"Unknown action: '{action_id}'. Available: {sorted(action_registry.keys())}",
            }
        )
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
    tracer.set_action_context(action_id)
    screen_probe_start = len(tracer.traces)
    screen_before = _detect_screen(bundle)
    tracer.set_screen_for_traces_since(screen_probe_start, screen_before)
    tracer.set_screen(screen_before)
    started_at = time.perf_counter()

    try:
        fn = action_registry[action_id]
        result = fn(bundle, params)
        success = bool(result)
        timing_ms = round((time.perf_counter() - started_at) * 1000, 2)
        screen_probe_start = len(tracer.traces)
        screen_after = _detect_screen(bundle)
        tracer.set_screen_for_traces_since(screen_probe_start, screen_after)
        tracer.set_screen(screen_after)
        message = f"Action '{action_id}' {'succeeded' if success else 'failed'}"
        matched = sum(1 for trace in tracer.traces if trace["found"])
        logger.info(f"{message} - selectors: {matched}/{len(tracer.traces)} matched")
        emit(
            {
                "type": "result",
                "success": success,
                "message": message,
                "selector_traces": tracer.traces,
                "ui_action_trace": _build_ui_action_trace(
                    action_id=action_id,
                    success=success,
                    screen_before=screen_before,
                    screen_after=screen_after,
                    selector_traces=tracer.traces,
                    timing_ms=timing_ms,
                ),
            }
        )
    except Exception as exc:
        timing_ms = round((time.perf_counter() - started_at) * 1000, 2)
        screen_probe_start = len(tracer.traces)
        screen_after = _detect_screen(bundle)
        tracer.set_screen_for_traces_since(screen_probe_start, screen_after)
        tracer.set_screen(screen_after)
        tb = traceback.format_exc()
        logger.error(f"Action '{action_id}' raised exception: {exc}\n{tb}")
        emit(
            {
                "type": "result",
                "success": False,
                "message": f"Exception: {exc}",
                "selector_traces": tracer.traces,
                "ui_action_trace": _build_ui_action_trace(
                    action_id=action_id,
                    success=False,
                    screen_before=screen_before,
                    screen_after=screen_after,
                    selector_traces=tracer.traces,
                    timing_ms=timing_ms,
                ),
            }
        )
        sys.exit(1)


def _build_ui_action_trace(
    *,
    action_id: str,
    success: bool,
    screen_before: str | None,
    screen_after: str | None,
    selector_traces: list[dict],
    timing_ms: float,
) -> dict:
    return {
        "actionId": action_id,
        "intent": _intent_from_action_id(action_id),
        "screenBefore": screen_before,
        "screenAfter": screen_after,
        "fallbackUsed": any((trace.get("fallbackIndex") or 0) > 0 for trace in selector_traces),
        "timingMs": timing_ms,
        "success": success,
    }


def _intent_from_action_id(action_id: str) -> str:
    parts = [part for part in action_id.split(".") if part]
    if not parts:
        return "unknown"
    if parts[0] == "tt" and len(parts) > 1:
        return parts[1]
    return parts[0]


def _detect_screen(bundle) -> str:
    detection = getattr(bundle, "detection", None)
    checks = [
        ("instagram.story_viewer", "is_story_viewer_open"),
        ("instagram.post", "is_on_post_screen"),
        ("instagram.profile", "is_on_profile_screen"),
        ("instagram.search", "is_on_search_screen"),
        ("instagram.home", "is_on_home_screen"),
        ("tiktok.inbox", "is_on_inbox_page"),
        ("tiktok.feed.for_you", "is_on_for_you_page"),
    ]

    if detection is not None:
        for screen, method_name in checks:
            method = getattr(detection, method_name, None)
            if not callable(method):
                continue
            try:
                if method():
                    return screen
            except Exception as exc:
                logger.debug(f"Screen probe {method_name} failed: {exc}")

    current_app = _get_current_app(bundle)
    if current_app:
        package = current_app.get("package") or "unknown_package"
        activity = current_app.get("activity") or "unknown_activity"
        return f"android.{package}:{activity}"

    return "unknown"


def _get_current_app(bundle) -> dict | None:
    try:
        device = getattr(bundle, "device", None)
        raw_device = getattr(device, "_device", None)
        if raw_device is not None and hasattr(raw_device, "app_current"):
            app = raw_device.app_current()
            return app if isinstance(app, dict) else None
    except Exception:
        return None

    return None


__all__ = ["run_action_test_bridge"]
