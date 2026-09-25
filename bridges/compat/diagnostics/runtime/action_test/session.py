"""Persistent action-test session bridge for Cartography Lab."""

import json
import sys
import traceback

from loguru import logger

from bridges.compat.diagnostics.runtime.action_test.action_bundle import attach_device_id
from bridges.compat.diagnostics.runtime.action_test.language import LabLanguage
from bridges.compat.diagnostics.runtime.action_test.runner import (
    _detect_and_optimize_selectors,
    _execute_action,
    _install_selector_tracer,
)
from bridges.compat.diagnostics.runtime.events import emit


class _SessionContextCache:
    """Per-session holder for the session-invariant device/app artifact context.

    The session owns this cache: it is resolved once (lazily, on the first
    capturing run) and reused for every following run of the same persistent
    connection, so device metadata / app version / package are not re-queried at
    each action. The runner populates and reads ``value``.
    """

    def __init__(self) -> None:
        self.value = None


def _register_step_telemetry() -> None:
    """Forward the step telemetry of the actions (taps, scrolls, device io...) as `step_metric`
    lines, like the workflow bridges do. The session bridge did not, so a Lab session measured
    nothing (M1)."""
    try:
        from taktik.core.shared.telemetry import configure_telemetry_sink

        configure_telemetry_sink(lambda metric: emit({
            "type": "step_metric",
            "category": metric.category,
            "action": metric.action,
            "target": metric.target,
            "detail": metric.detail,
            "ts": metric.ts,
        }))
    except Exception as exc:
        logger.debug(f"Could not register the telemetry sink: {exc}")


def _begin_action_run() -> None:
    """Each Lab action is a run of its own: lift the run's stop lock left by the previous one.

    A bridge process serves one run and starts with the lock lifted; this one serves an action
    after another. Without this, a block or a lost phone seen by one action would end every
    workflow action after it, in a session still open.
    """
    try:
        from taktik.core.shared.diagnostics import run_halt

        run_halt.reinitialiser()
    except Exception:
        # A diagnostic that stops an action from running would be worse than none.
        pass


def run_action_session_bridge() -> None:
    """Keep one device connection alive and execute action commands from stdin."""
    config = _load_config()
    _register_step_telemetry()
    device_id = config.get("device_id", "")
    platform = config.get("platform", "instagram")
    mode = config.get("mode", "lab")
    capture_artifacts = config.get("capture_artifacts", True)
    perf_fast = config.get("perf_fast", False)
    language_override = config.get("language") or None

    if not device_id:
        emit({"type": "error", "success": False, "message": "Missing device_id"})
        sys.exit(1)

    try:
        action_registry, create_device_facade, build_action_bundle = _load_platform_runtime(platform)
    except Exception as exc:
        emit({"type": "error", "success": False, "message": f"Unsupported action session platform: {platform}", "error": str(exc)})
        sys.exit(1)

    logger.info(f"Starting persistent action-test session: platform={platform} device={device_id}")
    try:
        from taktik.core.shared.device.manager import DeviceManager

        device_manager = DeviceManager(device_id=device_id)
        if not device_manager.connect(verify_atx=False):
            emit({"type": "error", "success": False, "message": f"Could not connect to device {device_id}"})
            sys.exit(1)

        device_facade = create_device_facade(device_manager.device)
        bundle = build_action_bundle(device_facade)
        attach_device_id(bundle, device_id)
        # The session usually opens with the app closed: the language is detected once the app is
        # on screen (after `app.launch`, or before the first action that finds it there).
        language = LabLanguage(platform, device_facade, _detect_and_optimize_selectors, override=language_override)
        language_optimization = language.refresh()
        tracer = _install_selector_tracer(device_facade, app=platform)
        session_context_cache = _SessionContextCache()
    except Exception as exc:
        emit({"type": "error", "success": False, "message": f"Action session init failed: {exc}", "traceback": traceback.format_exc()})
        sys.exit(1)

    emit(
        {
            "type": "session_ready",
            "success": True,
            "device_id": device_id,
            "platform": platform,
            "language_optimization": language_optimization,
        }
    )

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            command = json.loads(line)
        except Exception as exc:
            emit({"type": "error", "success": False, "message": f"Invalid action session command: {exc}"})
            continue

        command_type = command.get("type")
        if command_type in {"shutdown", "stop", "close"}:
            emit({"type": "session_closed", "success": True, "device_id": device_id, "platform": platform})
            return

        if command_type != "run_action":
            emit(
                {
                    "type": "error",
                    "request_id": command.get("request_id"),
                    "success": False,
                    "message": f"Unknown action session command: {command_type}",
                }
            )
            continue

        action_id = command.get("action_id", "")
        request_id = command.get("request_id")
        params = command.get("params") if isinstance(command.get("params"), dict) else {}
        scenario = command.get("scenario") if isinstance(command.get("scenario"), dict) else None

        if action_id not in action_registry:
            emit(
                {
                    "type": "result",
                    "request_id": request_id,
                    "success": False,
                    "message": f"Unknown action: '{action_id}'. Available: {sorted(action_registry.keys())}",
                    "selector_traces": [],
                    "ui_action_trace": None,
                    "artifacts": None,
                    "language_optimization": language.payload,
                    "transition": None,
                }
            )
            continue

        tracer.reset()
        _begin_action_run()
        language_optimization = language.refresh()
        _execute_action(
            action_registry,
            action_id,
            bundle,
            params,
            tracer,
            platform=platform,
            device_id=device_id,
            mode=command.get("mode", mode),
            capture_artifacts=bool(command.get("capture_artifacts", capture_artifacts)),
            perf_fast=bool(command.get("perf_fast", perf_fast)),
            language_optimization=language_optimization,
            request_id=request_id,
            exit_on_error=False,
            session_context_cache=session_context_cache,
            scenario=scenario,
            refresh_language=language.refresh,
        )


def _load_config() -> dict:
    if len(sys.argv) < 2:
        emit({"type": "error", "success": False, "message": "No config file provided"})
        sys.exit(1)

    try:
        with open(sys.argv[1], "r", encoding="utf-8-sig") as file_obj:
            return json.load(file_obj)
    except Exception as exc:
        emit({"type": "error", "success": False, "message": f"Failed to read config: {exc}"})
        sys.exit(1)


def _load_platform_runtime(platform: str):
    if platform == "instagram":
        from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions
        from bridges.compat.diagnostics.runtime.action_test.bundles import (
            build_instagram_action_bundle,
            create_instagram_device_facade,
        )

        register_actions()
        return ACTION_REGISTRY, create_instagram_device_facade, build_instagram_action_bundle

    if platform == "tiktok":
        from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions
        from bridges.compat.diagnostics.runtime.action_test.bundles import (
            build_tiktok_action_bundle,
            create_tiktok_device_facade,
        )

        register_actions()
        return ACTION_REGISTRY, create_tiktok_device_facade, build_tiktok_action_bundle

    raise ValueError(platform)


__all__ = ["run_action_session_bridge"]
