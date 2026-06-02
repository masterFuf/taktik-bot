"""Read-only analysis for Cartography Lab action reports."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_SCREEN_AFTER: dict[str, str] = {
    "detection.is_home_screen": "instagram.home",
    "detection.is_profile_screen": "instagram.profile",
    "detection.is_post_open": "instagram.post",
    "navigation.go_home": "instagram.home",
    "navigation.go_search": "instagram.search",
    "navigation.go_profile_tab": "instagram.profile",
    "navigation.open_profile": "instagram.profile",
}


def build_action_analysis(report: dict[str, Any]) -> dict[str, Any]:
    """Build a sidecar analysis from a completed Cartography action report."""
    selector_traces = report.get("selectorTraces") or []
    selector_summary = _selector_summary(selector_traces)
    transition = _transition_analysis(report)
    recommendations = _selector_recommendations(selector_traces)

    return {
        "schemaVersion": 1,
        "generatedAt": _utc_now(),
        "runId": report.get("runId"),
        "actionId": (report.get("action") or {}).get("id"),
        "verdict": _verdict(report, transition, recommendations),
        "transition": transition,
        "selectorSummary": selector_summary,
        "recommendations": recommendations,
        "notes": _notes(report, transition, selector_summary),
    }


def write_action_analysis(report_path: str | Path, analysis: dict[str, Any]) -> str:
    """Persist an analysis next to the report and return its path."""
    import json

    analysis_path = Path(report_path).with_name("analysis.json")
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return str(analysis_path)


def expected_screen_after(action_id: str) -> str | None:
    return EXPECTED_SCREEN_AFTER.get(action_id)


def build_transition(action_id: str, screen_after: str | None, success: bool) -> dict[str, Any]:
    expected = expected_screen_after(action_id)
    ok = None if expected is None else screen_after == expected
    reason = None
    if expected is not None and not ok:
        reason = "screen_mismatch" if success else "action_failed"

    return {
        "expectedScreenAfter": expected,
        "actualScreenAfter": screen_after,
        "ok": ok,
        "reason": reason,
    }


def _transition_analysis(report: dict[str, Any]) -> dict[str, Any]:
    action_id = (report.get("action") or {}).get("id") or ""
    result = report.get("result") or {}
    screens = report.get("screens") or {}
    return {
        "screenBefore": screens.get("before"),
        **build_transition(action_id, screens.get("after"), result.get("success") is True),
    }


def _selector_summary(selector_traces: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(selector_traces)
    found = sum(1 for trace in selector_traces if trace.get("found") is True)
    total_elapsed = sum(float(trace.get("elapsedMs") or 0) for trace in selector_traces)
    return {
        "total": total,
        "found": found,
        "notFound": total - found,
        "matchRate": round((found / total) * 100, 2) if total else 0,
        "totalElapsedMs": round(total_elapsed, 2),
        "averageElapsedMs": round(total_elapsed / total, 2) if total else 0,
    }


def _selector_recommendations(selector_traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in selector_traces:
        xpath = trace.get("xpath")
        if xpath:
            grouped[str(xpath)].append(trace)

    recommendations = []
    for xpath, traces in grouped.items():
        calls = len(traces)
        found = sum(1 for trace in traces if trace.get("found") is True)
        missed = calls - found
        total_elapsed = round(sum(float(trace.get("elapsedMs") or 0) for trace in traces), 2)
        average_elapsed = round(total_elapsed / calls, 2) if calls else 0
        screens = sorted({str(trace.get("screen")) for trace in traces if trace.get("screen")})
        family = next((trace.get("family") for trace in traces if trace.get("family")), None)

        if found > 0:
            recommendation = "keep"
            severity = "info"
            reason = "selector_matched"
        elif total_elapsed >= 1000 or calls >= 3:
            recommendation = "context_gate"
            severity = "warning"
            reason = "costly_never_matched_in_observed_context"
        else:
            recommendation = "watch"
            severity = "info"
            reason = "not_enough_samples"

        recommendations.append(
            {
                "recommendation": recommendation,
                "severity": severity,
                "reason": reason,
                "xpath": xpath,
                "family": family,
                "calls": calls,
                "found": found,
                "missed": missed,
                "totalElapsedMs": total_elapsed,
                "averageElapsedMs": average_elapsed,
                "screens": screens,
            }
        )

    return sorted(
        recommendations,
        key=lambda item: (
            item["recommendation"] != "context_gate",
            -float(item["totalElapsedMs"]),
            item["xpath"],
        ),
    )


def _verdict(
    report: dict[str, Any],
    transition: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> str:
    if (report.get("result") or {}).get("success") is not True:
        return "fail"
    if transition.get("ok") is False:
        return "warn"
    if any(item["recommendation"] == "context_gate" for item in recommendations):
        return "warn"
    return "pass"


def _notes(
    report: dict[str, Any],
    transition: dict[str, Any],
    selector_summary: dict[str, Any],
) -> list[str]:
    notes = []
    action_id = (report.get("action") or {}).get("id")
    if transition.get("ok") is False:
        result_success = (report.get("result") or {}).get("success") is True
        if result_success:
            notes.append(
                f"{action_id} returned success but ended on {transition.get('actualScreenAfter')} "
                f"instead of {transition.get('expectedScreenAfter')}."
            )
        else:
            notes.append(
                f"{action_id} failed before reaching {transition.get('expectedScreenAfter')} "
                f"(ended on {transition.get('actualScreenAfter')})."
            )
    if selector_summary["total"] and selector_summary["matchRate"] < 25:
        notes.append("Selector match rate is below 25%; review context gates before deleting selectors.")
    return notes


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "EXPECTED_SCREEN_AFTER",
    "build_action_analysis",
    "build_transition",
    "expected_screen_after",
    "write_action_analysis",
]
