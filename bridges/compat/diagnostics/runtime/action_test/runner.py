"""Shared action-test runner for compat diagnostics bridges."""

import json
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from bridges.compat.diagnostics.runtime.events import emit
from bridges.compat.diagnostics.runtime.action_test.analysis import (
    build_action_analysis,
    build_transition,
    write_action_analysis,
)
from bridges.compat.diagnostics.runtime.action_test.artifacts import (
    artifact_dir_for,
    build_artifact_context,
    build_report_payload,
    capture_phase_artifacts,
    resolve_session_invariant_context,
    write_action_report,
)
from bridges.compat.diagnostics.runtime.action_test.tracing import SelectorTracer, TracedSelector


_BOT_ROOT = Path(__file__).resolve().parents[5]


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
    platform = config.get("platform", _platform_from_action_id(action_id))
    mode = config.get("mode", "manual")
    capture_artifacts = _should_capture_artifacts(config)
    perf_fast = _is_perf_fast(config)

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

    language_optimization = _detect_and_optimize_selectors(platform, device_facade)
    tracer = _install_selector_tracer(device_facade, app=platform)
    _execute_action(
        action_registry,
        action_id,
        bundle,
        params,
        tracer,
        platform=platform,
        device_id=device_id,
        mode=mode,
        capture_artifacts=capture_artifacts,
        perf_fast=perf_fast,
        language_optimization=language_optimization,
    )


def _install_selector_tracer(device_facade, app: str | None = None):
    tracer = SelectorTracer(app=app)
    original_xpath = device_facade._device.xpath

    def traced_xpath(expr, *args, **kwargs):
        return TracedSelector(original_xpath(expr, *args, **kwargs), expr, tracer)

    device_facade._device.xpath = traced_xpath
    return tracer


def _execute_action(
    action_registry: dict,
    action_id: str,
    bundle,
    params: dict,
    tracer: SelectorTracer,
    *,
    platform: str = "unknown",
    device_id: str = "unknown-device",
    mode: str = "manual",
    capture_artifacts: bool = False,
    perf_fast: bool = False,
    language_optimization: dict | None = None,
    request_id: str | None = None,
    exit_on_error: bool = True,
    session_context_cache=None,  # session-owned _SessionContextCache holder (.value)
    scenario: dict | None = None,  # scenario tag {runId,id,label,stepIndex,stepLabel,total}
) -> None:
    # perf_fast keeps the artifact context + report.json (for phase timings) but
    # skips the XML/PNG capture. It is a pure-timing diagnostic mode: the report is
    # tagged perfFast so the front never aggregates it with full-artifact runs.
    capture_media = capture_artifacts and not perf_fast
    run_started_at = time.perf_counter()
    phase_timings: dict[str, float] = {}
    tracer.set_action_context(action_id)
    run_id = _build_run_id(action_id)
    # Resolve currentAppBefore first so the artifact context can reuse it for
    # package resolution instead of issuing a third app_current() round-trip.
    current_app_before = _time_phase(phase_timings, "currentAppBeforeMs", lambda: _get_current_app(bundle))
    artifact_context = (
        _time_phase(
            phase_timings,
            "artifactContextMs",
            lambda: _resolve_artifact_context(
                session_context_cache=session_context_cache,
                bundle=bundle,
                device_id=device_id,
                platform=platform,
                action_id=action_id,
                run_id=run_id,
                mode=mode,
                current_app=current_app_before,
            ),
        )
        if capture_artifacts
        else None
    )
    screen_probe_start = len(tracer.traces)
    screen_before = _time_phase(phase_timings, "screenBeforeMs", lambda: _detect_screen(bundle))
    tracer.set_screen_for_traces_since(screen_probe_start, screen_before)
    tracer.set_screen(screen_before)
    artifacts = (
        _time_phase(
            phase_timings,
            "artifactsBeforeMs",
            lambda: capture_phase_artifacts(bundle, artifact_context, "before"),
        )
        if capture_media
        else {}
    )
    started_at = time.perf_counter()

    try:
        fn = action_registry[action_id]
        result = fn(bundle, params)
        # Actions may return a bool, or a dict {success, message?, details?} to surface data.
        if isinstance(result, dict):
            success = bool(result.get("success", True))
            action_message = result.get("message")
            action_details = result.get("details")
        else:
            success = bool(result)
            action_message = None
            action_details = None
        timing_ms = _elapsed_ms(started_at)
        phase_timings["actionMs"] = timing_ms
        screen_probe_start = len(tracer.traces)
        screen_after = _time_phase(phase_timings, "screenAfterMs", lambda: _detect_screen(bundle))
        current_app_after = _time_phase(phase_timings, "currentAppAfterMs", lambda: _get_current_app(bundle))
        tracer.set_screen_for_traces_since(screen_probe_start, screen_after)
        tracer.set_screen(screen_after)
        if capture_media:
            artifacts.update(
                _time_phase(
                    phase_timings,
                    "artifactsAfterMs",
                    lambda: capture_phase_artifacts(bundle, artifact_context, "after"),
                )
            )
        message = action_message or f"Action '{action_id}' {'succeeded' if success else 'failed'}"
        transition = build_transition(action_id, screen_after, success)
        matched = sum(1 for trace in tracer.traces if trace["found"])
        logger.info(f"{message} - selectors: {matched}/{len(tracer.traces)} matched")
        ui_action_trace = _build_ui_action_trace(
            action_id=action_id,
            success=success,
            screen_before=screen_before,
            screen_after=screen_after,
            selector_traces=tracer.traces,
            timing_ms=timing_ms,
        )
        phase_timings["totalBeforeReportMs"] = _elapsed_ms(run_started_at)
        if artifact_context:
            artifacts["report"] = str(artifact_context.report_path)
            artifacts["analysis"] = str(artifact_context.report_path.with_name("analysis.json"))
            report = build_report_payload(
                context=artifact_context,
                action_id=action_id,
                params=params,
                success=success,
                message=message,
                screen_before=screen_before,
                screen_after=screen_after,
                current_app_before=current_app_before,
                current_app_after=current_app_after,
                selector_traces=tracer.traces,
                ui_action_trace=ui_action_trace,
                artifacts=artifacts,
                timing_ms=timing_ms,
                phase_timings=phase_timings,
                language_optimization=language_optimization,
                transition=transition,
                perf_fast=perf_fast,
                details=action_details,
                scenario=scenario,
            )
            write_action_report(artifact_context, report)
            write_action_analysis(
                artifact_context.report_path,
                build_action_analysis(report),
            )
        emit(
            {
                "type": "result",
                "request_id": request_id,
                "success": success,
                "message": message,
                "selector_traces": tracer.traces,
                "ui_action_trace": ui_action_trace,
                "artifacts": artifacts or None,
                "phase_timings": phase_timings,
                "language_optimization": language_optimization,
                "transition": transition,
                "perf_fast": perf_fast,
                "details": action_details or None,
            }
        )
    except Exception as exc:
        timing_ms = _elapsed_ms(started_at)
        phase_timings["actionMs"] = timing_ms
        screen_probe_start = len(tracer.traces)
        screen_after = _time_phase(phase_timings, "screenAfterMs", lambda: _detect_screen(bundle))
        current_app_after = _time_phase(phase_timings, "currentAppAfterMs", lambda: _get_current_app(bundle))
        tracer.set_screen_for_traces_since(screen_probe_start, screen_after)
        tracer.set_screen(screen_after)
        if capture_media:
            artifacts.update(
                _time_phase(
                    phase_timings,
                    "artifactsAfterMs",
                    lambda: capture_phase_artifacts(bundle, artifact_context, "after"),
                )
            )
        tb = traceback.format_exc()
        logger.error(f"Action '{action_id}' raised exception: {exc}\n{tb}")
        transition = build_transition(action_id, screen_after, False)
        ui_action_trace = _build_ui_action_trace(
            action_id=action_id,
            success=False,
            screen_before=screen_before,
            screen_after=screen_after,
            selector_traces=tracer.traces,
            timing_ms=timing_ms,
        )
        phase_timings["totalBeforeReportMs"] = _elapsed_ms(run_started_at)
        if artifact_context:
            artifacts["report"] = str(artifact_context.report_path)
            artifacts["analysis"] = str(artifact_context.report_path.with_name("analysis.json"))
            report = build_report_payload(
                context=artifact_context,
                action_id=action_id,
                params=params,
                success=False,
                message=f"Exception: {exc}",
                screen_before=screen_before,
                screen_after=screen_after,
                current_app_before=current_app_before,
                current_app_after=current_app_after,
                selector_traces=tracer.traces,
                ui_action_trace=ui_action_trace,
                artifacts=artifacts,
                timing_ms=timing_ms,
                phase_timings=phase_timings,
                error=str(exc),
                language_optimization=language_optimization,
                transition=transition,
                perf_fast=perf_fast,
            )
            write_action_report(artifact_context, report)
            write_action_analysis(
                artifact_context.report_path,
                build_action_analysis(report),
            )
        emit(
            {
                "type": "result",
                "request_id": request_id,
                "success": False,
                "message": f"Exception: {exc}",
                "selector_traces": tracer.traces,
                "ui_action_trace": ui_action_trace,
                "artifacts": artifacts or None,
                "phase_timings": phase_timings,
                "language_optimization": language_optimization,
                "transition": transition,
                "perf_fast": perf_fast,
            }
        )
        if exit_on_error:
            sys.exit(1)


def _resolve_artifact_context(
    *,
    session_context_cache,
    bundle,
    device_id: str,
    platform: str,
    action_id: str,
    run_id: str,
    mode: str,
    current_app: dict | None,
):
    """Build the artifact context, reusing session-invariant device/app context.

    For a persistent session (``session_context_cache`` provided) the device/app
    context is resolved once on the first capturing run and reused afterwards, so
    later runs pay no ADB / uiautomator / app_current cost for it. The single-shot
    bridge passes no cache and recomputes per run, but still reuses ``current_app``
    to avoid a redundant app_current() round-trip.
    """
    session_context = None
    if session_context_cache is not None:
        if session_context_cache.value is None:
            session_context_cache.value = resolve_session_invariant_context(
                bundle=bundle,
                device_id=device_id,
                platform=platform,
                current_app=current_app,
            )
        session_context = session_context_cache.value

    return build_artifact_context(
        bot_root=_BOT_ROOT,
        bundle=bundle,
        device_id=device_id,
        platform=platform,
        action_id=action_id,
        run_id=run_id,
        mode=mode,
        session_context=session_context,
        current_app=current_app,
    )


def _detect_and_optimize_selectors(platform: str, device_facade) -> dict:
    started_at = time.perf_counter()
    try:
        if platform == "instagram":
            from taktik.core.social_media.instagram.ui.language import detect_and_optimize
        elif platform == "tiktok":
            from taktik.core.social_media.tiktok.ui.language import detect_and_optimize
        else:
            return {
                "platform": platform,
                "language": "unknown",
                "applied": False,
                "reason": "unsupported_platform",
                "timingMs": 0,
            }

        language = detect_and_optimize(device_facade)
        payload = {
            "platform": platform,
            "language": language,
            "applied": language not in (None, "", "unknown"),
            "reason": None if language not in (None, "", "unknown") else "language_unknown",
            "timingMs": round((time.perf_counter() - started_at) * 1000, 2),
        }
        logger.info(
            f"Action-test selectors optimized for language={payload['language']} "
            f"platform={platform}"
        )
        emit(
            {
                "type": "log",
                "level": "info",
                "message": f"App language detected: {str(payload['language']).upper()}",
                "language_optimization": payload,
            }
        )
        return payload
    except Exception as exc:
        logger.warning(f"Language selector optimization failed (non-fatal): {exc}")
        return {
            "platform": platform,
            "language": "unknown",
            "applied": False,
            "reason": "detection_failed",
            "timingMs": round((time.perf_counter() - started_at) * 1000, 2),
        }


def _time_phase(phase_timings: dict[str, float], name: str, callback):
    phase_started_at = time.perf_counter()
    try:
        return callback()
    finally:
        phase_timings[name] = _elapsed_ms(phase_started_at)


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


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


def _platform_from_action_id(action_id: str) -> str:
    return "tiktok" if action_id.startswith("tt.") else "instagram"


def _should_capture_artifacts(config: dict) -> bool:
    return config.get("mode") == "lab" or config.get("capture_artifacts") is True


def _is_perf_fast(config: dict) -> bool:
    """Opt-in pure-timing mode: build the report but skip XML/PNG capture."""
    return config.get("perf_fast") is True


def _build_run_id(action_id: str) -> str:
    safe_action = re.sub(r"[^a-zA-Z0-9_.-]+", "_", action_id).strip("._") or "action"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3] + "Z"
    return f"{safe_action}_{timestamp}"


def _artifact_dir(
    platform: str,
    run_id: str,
    device_id: str = "unknown-device",
    app_version: str = "unknown-version",
    action_id: str = "unknown-action",
) -> Path:
    return artifact_dir_for(
        _BOT_ROOT,
        platform=platform,
        run_id=run_id,
        device_id=device_id,
        app_version=app_version,
        action_id=action_id,
    )


def _detect_screen(bundle) -> str:
    detection = getattr(bundle, "detection", None)
    checks = [
        # Profile must stay before home: Instagram can keep feed_tab selected
        # while a profile surface is open in the navigation stack.
        ("instagram.profile", "is_on_profile_screen"),
        # Home must stay before broad post/story probes: feed posts expose Like
        # buttons and row_feed_profile_header, which are not opened post screens.
        ("instagram.home", "is_on_home_screen"),
        ("instagram.search", "is_on_search_screen"),
        ("instagram.story_viewer", "is_story_viewer_open"),
        ("instagram.post", "is_on_post_screen"),
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
