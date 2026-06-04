"""Filesystem artifacts and reports for Cartography Lab action runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


UNKNOWN_DEVICE = "unknown-device"
UNKNOWN_VERSION = "unknown-version"
UNKNOWN_ACTION = "unknown-action"


@dataclass(frozen=True)
class ActionArtifactContext:
    """Stable filesystem context for one Cartography Lab action run."""

    bot_root: Path
    device_id: str
    platform: str
    app_version: str
    action_id: str
    run_id: str
    mode: str
    package_name: str | None
    resolution: dict[str, int] | None
    model: str | None
    manufacturer: str | None
    android_version: str | None
    density_dpi: int | None
    scaled_density: float | None
    started_at: str

    @property
    def artifact_dir(self) -> Path:
        return (
            self.bot_root
            / "debug_ui"
            / "cartography"
            / _safe_segment(self.device_id, UNKNOWN_DEVICE)
            / _safe_segment(self.platform, "unknown-platform")
            / _safe_segment(self.app_version, UNKNOWN_VERSION)
            / "action-runs"
            / _safe_segment(self.action_id, UNKNOWN_ACTION)
            / _safe_segment(self.run_id, "run")
        )

    @property
    def report_path(self) -> Path:
        return self.artifact_dir / "report.json"


@dataclass(frozen=True)
class SessionInvariantContext:
    """Device/app context that stays constant for a whole Cartography Lab session.

    Resolved once (ADB / uiautomator / app_current) and reused across every run of
    the same persistent session instead of being rebuilt at each action. Holds only
    session-stable fields: no run_id/action_id/mode (per-run) and no current_app
    before/after (those must stay real, see runner).
    """

    package_name: str | None
    app_version: str | None
    resolution: dict[str, int] | None
    model: str | None
    manufacturer: str | None
    android_version: str | None
    density_dpi: int | None
    scaled_density: float | None


def resolve_session_invariant_context(
    *,
    bundle: Any,
    device_id: str,
    platform: str,
    current_app: dict | None = None,
) -> SessionInvariantContext:
    """Resolve the session-stable device/app context (one ADB/uiautomator pass).

    ``current_app`` lets the caller reuse an ``app_current()`` value already obtained
    (e.g. ``currentAppBefore``) so package resolution does not trigger an extra
    device round-trip.
    """
    package_name = _resolve_package_name(bundle, platform, current_app=current_app)
    app_version = _resolve_app_version(device_id, package_name, platform)
    device_metadata = _resolve_device_metadata(bundle, device_id)
    return SessionInvariantContext(
        package_name=package_name,
        app_version=app_version,
        resolution=_resolve_resolution(bundle),
        model=device_metadata.get("model"),
        manufacturer=device_metadata.get("manufacturer"),
        android_version=device_metadata.get("android_version"),
        density_dpi=device_metadata.get("density_dpi"),
        scaled_density=device_metadata.get("scaled_density"),
    )


def build_artifact_context(
    *,
    bot_root: Path,
    bundle: Any,
    device_id: str,
    platform: str,
    action_id: str,
    run_id: str,
    mode: str,
    session_context: SessionInvariantContext | None = None,
    current_app: dict | None = None,
) -> ActionArtifactContext:
    """Create the filesystem context before writing XML/PNG/report files.

    When ``session_context`` is provided, the session-stable device/app fields are
    reused as-is (no ADB / uiautomator / app_current call). Otherwise they are
    resolved on the spot, reusing ``current_app`` for package resolution when given.
    """
    invariant = session_context or resolve_session_invariant_context(
        bundle=bundle,
        device_id=device_id,
        platform=platform,
        current_app=current_app,
    )
    return ActionArtifactContext(
        bot_root=bot_root,
        device_id=device_id or UNKNOWN_DEVICE,
        platform=platform or "unknown-platform",
        app_version=invariant.app_version or UNKNOWN_VERSION,
        action_id=action_id or UNKNOWN_ACTION,
        run_id=run_id,
        mode=mode or "manual",
        package_name=invariant.package_name,
        resolution=invariant.resolution,
        model=invariant.model,
        manufacturer=invariant.manufacturer,
        android_version=invariant.android_version,
        density_dpi=invariant.density_dpi,
        scaled_density=invariant.scaled_density,
        started_at=_utc_now(),
    )


def capture_phase_artifacts(bundle: Any, context: ActionArtifactContext, phase: str) -> dict[str, str]:
    """Capture XML + screenshot for one phase and return JSON-safe paths."""
    artifacts: dict[str, str] = {}
    context.artifact_dir.mkdir(parents=True, exist_ok=True)

    xml = _safe_get_xml(bundle)
    if xml:
        xml_path = context.artifact_dir / f"{phase}.xml"
        xml_path.write_text(xml, encoding="utf-8")
        artifacts[f"xml{phase.title()}"] = str(xml_path)

    screenshot_path = context.artifact_dir / f"{phase}.png"
    if _safe_screenshot(bundle, screenshot_path):
        artifacts[f"screenshot{phase.title()}"] = str(screenshot_path)

    logger.debug(
        f"Cartography artifacts captured for {context.action_id} "
        f"phase={phase}: {artifacts}"
    )
    return artifacts


def write_action_report(context: ActionArtifactContext, report: dict[str, Any]) -> str:
    """Persist the complete action report and return its path."""
    context.artifact_dir.mkdir(parents=True, exist_ok=True)
    context.report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return str(context.report_path)


def build_report_payload(
    *,
    context: ActionArtifactContext,
    action_id: str,
    params: dict,
    success: bool,
    message: str,
    screen_before: str | None,
    screen_after: str | None,
    current_app_before: dict | None,
    current_app_after: dict | None,
    selector_traces: list[dict],
    ui_action_trace: dict,
    artifacts: dict[str, str],
    timing_ms: float,
    phase_timings: dict[str, Any] | None = None,
    language_optimization: dict[str, Any] | None = None,
    transition: dict[str, Any] | None = None,
    error: str | None = None,
    perf_fast: bool = False,
    details: dict[str, Any] | None = None,
    scenario: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the on-disk report used by humans and future selector-health jobs."""
    found = sum(1 for trace in selector_traces if trace.get("found") is True)
    return {
        "schemaVersion": 1,
        "runId": context.run_id,
        "mode": context.mode,
        "perfFast": perf_fast,
        "details": details or {},
        "scenario": scenario or None,
        "startedAt": context.started_at,
        "finishedAt": _utc_now(),
        "device": {
            "id": context.device_id,
            "model": context.model,
            "manufacturer": context.manufacturer,
            "androidVersion": context.android_version,
            "resolution": context.resolution,
            "densityDpi": context.density_dpi,
            "scaledDensity": context.scaled_density,
        },
        "app": {
            "platform": context.platform,
            "packageName": context.package_name,
            "version": context.app_version,
            "currentBefore": current_app_before,
            "currentAfter": current_app_after,
        },
        "action": {
            "id": action_id,
            "intent": ui_action_trace.get("intent"),
            "params": _summarize_params(params),
        },
        "languageOptimization": language_optimization,
        "phaseTimings": phase_timings or {},
        "screens": {
            "before": screen_before,
            "after": screen_after,
        },
        "transition": transition,
        "result": {
            "success": success,
            "message": message,
            "error": error,
            "timingMs": timing_ms,
        },
        "selectorHealth": {
            "total": len(selector_traces),
            "found": found,
            "notFound": len(selector_traces) - found,
            "fallbackUsed": ui_action_trace.get("fallbackUsed") is True,
        },
        "selectorTraces": selector_traces,
        "uiActionTrace": ui_action_trace,
        "artifacts": artifacts,
    }


def artifact_dir_for(
    bot_root: Path,
    *,
    platform: str,
    run_id: str,
    device_id: str = UNKNOWN_DEVICE,
    app_version: str = UNKNOWN_VERSION,
    action_id: str = UNKNOWN_ACTION,
) -> Path:
    """Return the canonical Cartography Lab action artifact directory."""
    context = ActionArtifactContext(
        bot_root=bot_root,
        device_id=device_id,
        platform=platform,
        app_version=app_version,
        action_id=action_id,
        run_id=run_id,
        mode="lab",
        package_name=None,
        resolution=None,
        model=None,
        manufacturer=None,
        android_version=None,
        density_dpi=None,
        scaled_density=None,
        started_at=_utc_now(),
    )
    return context.artifact_dir


def _resolve_package_name(bundle: Any, platform: str, *, current_app: dict | None = None) -> str | None:
    current = current_app if current_app is not None else _get_current_app(bundle)
    package_name = current.get("package") if current else None
    if package_name:
        return package_name

    try:
        from bridges.common.device.apps import get_app_config

        config = get_app_config(platform)
        if config:
            package = config.get("package")
            return str(package) if package else None
    except Exception as exc:
        logger.debug(f"Could not resolve default package for {platform}: {exc}")

    return None


def _resolve_app_version(device_id: str, package_name: str | None, platform: str) -> str | None:
    if not device_id or device_id == UNKNOWN_DEVICE or not package_name:
        return None

    try:
        from bridges.common.device.app_inspection import get_installed_app_version

        return get_installed_app_version(device_id, package_name, platform)
    except Exception as exc:
        logger.debug(f"Could not resolve app version for {package_name}: {exc}")
        return None


def _resolve_resolution(bundle: Any) -> dict[str, int] | None:
    try:
        device = getattr(bundle, "device", None)
        if device is not None and hasattr(device, "get_screen_size"):
            width, height = device.get_screen_size()
            return {"width": int(width), "height": int(height)}

        raw_device = getattr(device, "_device", None)
        info = getattr(raw_device, "info", None)
        if isinstance(info, dict):
            width = info.get("displayWidth")
            height = info.get("displayHeight")
            if width and height:
                return {"width": int(width), "height": int(height)}
    except Exception as exc:
        logger.debug(f"Could not resolve screen resolution: {exc}")

    return None


def _resolve_device_metadata(bundle: Any, device_id: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "model": None,
        "manufacturer": None,
        "android_version": None,
        "density_dpi": None,
        "scaled_density": None,
    }

    try:
        info = _get_raw_device_info(bundle)
        if isinstance(info, dict):
            metadata["model"] = _first_text(info, "productName", "model", "displayName")
            metadata["manufacturer"] = _first_text(info, "brand", "manufacturer")
            metadata["android_version"] = _first_text(info, "release", "androidVersion")
            metadata["density_dpi"] = _first_int(info, "displayDensity", "densityDpi", "density")
            metadata["scaled_density"] = _first_float(info, "scaledDensity")
    except Exception as exc:
        logger.debug(f"Could not resolve device metadata from uiautomator info: {exc}")

    # Prefer the marketing model (ro.product.model, e.g. "Pixel 3a") over the
    # uiautomator productName (codename, e.g. "sargo") so runs stay identifiable.
    marketing_model = _resolve_marketing_model(device_id)
    if marketing_model:
        metadata["model"] = marketing_model

    if metadata["density_dpi"] is None:
        metadata["density_dpi"] = _resolve_density_from_adb(device_id)

    return metadata


def _get_raw_device_info(bundle: Any) -> dict | None:
    device = getattr(bundle, "device", None)
    raw_device = getattr(device, "_device", None)
    info = getattr(raw_device, "info", None)
    return info if isinstance(info, dict) else None


def _first_text(info: dict, *keys: str) -> str | None:
    for key in keys:
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_int(info: dict, *keys: str) -> int | None:
    for key in keys:
        value = info.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _first_float(info: dict, *keys: str) -> float | None:
    for key in keys:
        value = info.get(key)
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                continue
    return None


def _resolve_density_from_adb(device_id: str) -> int | None:
    if not device_id or device_id == UNKNOWN_DEVICE:
        return None

    try:
        from taktik.core.shared.device.adb import run_adb_shell

        output = run_adb_shell(device_id, "wm density")
        match = re.search(r"(?:Physical|Override)\s+density:\s*(\d+)", output or "")
        return int(match.group(1)) if match else None
    except Exception as exc:
        logger.debug(f"Could not resolve screen density via ADB: {exc}")
        return None


def _resolve_marketing_model(device_id: str) -> str | None:
    """Marketing device name (e.g. "Pixel 3a") via getprop, not the ADB codename."""
    if not device_id or device_id == UNKNOWN_DEVICE:
        return None

    try:
        from taktik.core.shared.device.adb import run_adb_shell

        for prop in ("ro.product.model", "ro.config.marketing_name", "ro.product.marketname"):
            text = (run_adb_shell(device_id, f"getprop {prop}") or "").strip()
            if text:
                return text
        return None
    except Exception as exc:
        logger.debug(f"Could not resolve marketing model via ADB: {exc}")
        return None


def _safe_get_xml(bundle: Any) -> str | None:
    try:
        device = getattr(bundle, "device", None)
        if device is None or not hasattr(device, "get_xml_dump"):
            return None
        xml = device.get_xml_dump()
        return xml if isinstance(xml, str) and xml else None
    except Exception as exc:
        logger.debug(f"XML artifact capture failed: {exc}")
        return None


def _safe_screenshot(bundle: Any, path: Path) -> bool:
    try:
        device = getattr(bundle, "device", None)
        if device is None or not hasattr(device, "screenshot"):
            return False
        return bool(device.screenshot(str(path)))
    except Exception as exc:
        logger.debug(f"Screenshot artifact capture failed: {exc}")
        return False


def _get_current_app(bundle: Any) -> dict | None:
    try:
        device = getattr(bundle, "device", None)
        raw_device = getattr(device, "_device", None)
        if raw_device is not None and hasattr(raw_device, "app_current"):
            app = raw_device.app_current()
            return app if isinstance(app, dict) else None
    except Exception:
        return None

    return None


def _safe_segment(value: str | None, fallback: str) -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw).strip("._") or fallback


def _summarize_params(params: dict) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for key, value in params.items():
        if isinstance(value, str):
            summary[key] = {"type": "string", "length": len(value), "redacted": True}
        elif isinstance(value, (int, float, bool)) or value is None:
            summary[key] = {"type": type(value).__name__, "value": value}
        else:
            summary[key] = {"type": type(value).__name__, "redacted": True}
    return summary


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
