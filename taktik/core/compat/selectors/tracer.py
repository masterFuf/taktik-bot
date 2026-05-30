"""Selector tracer owner package."""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class XPathCall:
    xpath: str
    found: bool
    elapsed_ms: float
    step: str
    timestamp: float
    error: Optional[str] = None
    screen: str = "unknown"


@dataclass
class WorkflowStep:
    name: str
    started_at: float
    ended_at: float = 0.0
    success: bool = True
    error: Optional[str] = None
    xpath_calls: List[XPathCall] = field(default_factory=list)


class SelectorTracer:
    """Instrument BaseDeviceFacade.xpath() to record XPath calls."""

    def __init__(self, on_xpath_call=None):
        self._calls: List[XPathCall] = []
        self._steps: List[WorkflowStep] = []
        self._current_step: Optional[WorkflowStep] = None
        self._attached_device = None
        self._original_xpath = None
        self._active = False
        self._on_xpath_call = on_xpath_call
        self._current_screen: str = "unknown"

    def attach(self, device_facade) -> None:
        if self._active:
            return

        self._attached_device = device_facade
        self._original_xpath = device_facade.xpath
        self._active = True

        tracer = self

        def instrumented_xpath(xpath_expr: str):
            t0 = time.time()
            result = None
            found = False
            error_msg = None

            try:
                result = tracer._original_xpath(xpath_expr)
                if result is not None and hasattr(result, "exists"):
                    try:
                        found = result.exists
                    except Exception:
                        found = False
            except Exception as e:
                error_msg = str(e)

            elapsed = (time.time() - t0) * 1000

            call = XPathCall(
                xpath=xpath_expr,
                found=found,
                elapsed_ms=round(elapsed, 2),
                step=tracer._current_step.name if tracer._current_step else "__unknown__",
                timestamp=t0,
                error=error_msg,
                screen=tracer._current_screen,
            )
            tracer._calls.append(call)

            if tracer._current_step:
                tracer._current_step.xpath_calls.append(call)

            if tracer._on_xpath_call:
                try:
                    tracer._on_xpath_call(call)
                except Exception:
                    pass

            return result

        device_facade.xpath = instrumented_xpath
        logger.info("[SelectorTracer] Attached to device facade")

    def detach(self) -> None:
        if not self._active:
            return
        if self._attached_device and self._original_xpath:
            self._attached_device.xpath = self._original_xpath
        self._active = False
        self._attached_device = None
        self._original_xpath = None
        logger.info("[SelectorTracer] Detached from device facade")

    def set_screen(self, screen: str) -> None:
        self._current_screen = screen

    @property
    def current_screen(self) -> str:
        return self._current_screen

    def begin_step(self, name: str) -> None:
        if self._current_step and self._current_step.ended_at == 0.0:
            self._current_step.ended_at = time.time()
            self._steps.append(self._current_step)
        self._current_step = WorkflowStep(name=name, started_at=time.time())

    def end_step(self, success: bool = True, error: str = None) -> None:
        if self._current_step:
            self._current_step.ended_at = time.time()
            self._current_step.success = success
            self._current_step.error = error
            self._steps.append(self._current_step)
            self._current_step = None

    def report(self) -> Dict[str, Any]:
        if self._current_step and self._current_step.ended_at == 0.0:
            self._current_step.ended_at = time.time()
            self._steps.append(self._current_step)
            self._current_step = None

        xpath_stats: Dict[str, Dict[str, Any]] = {}
        for call in self._calls:
            key = call.xpath
            if key not in xpath_stats:
                xpath_stats[key] = {
                    "xpath": key,
                    "total_calls": 0,
                    "found_count": 0,
                    "not_found_count": 0,
                    "error_count": 0,
                    "avg_ms": 0.0,
                    "steps_used_in": set(),
                    "screens_used_in": set(),
                }
            stats = xpath_stats[key]
            stats["total_calls"] += 1
            if call.error:
                stats["error_count"] += 1
            elif call.found:
                stats["found_count"] += 1
            else:
                stats["not_found_count"] += 1
            stats["avg_ms"] += call.elapsed_ms
            stats["steps_used_in"].add(call.step)
            stats["screens_used_in"].add(call.screen)

        for stats in xpath_stats.values():
            if stats["total_calls"] > 0:
                stats["avg_ms"] = round(stats["avg_ms"] / stats["total_calls"], 2)
            stats["steps_used_in"] = sorted(stats["steps_used_in"])
            stats["screens_used_in"] = sorted(stats["screens_used_in"])

        step_summaries = []
        for step in self._steps:
            total_calls = len(step.xpath_calls)
            found_calls = sum(1 for c in step.xpath_calls if c.found)
            step_summaries.append(
                {
                    "name": step.name,
                    "success": step.success,
                    "error": step.error,
                    "duration_ms": round((step.ended_at - step.started_at) * 1000, 2),
                    "xpath_calls": total_calls,
                    "xpath_found": found_calls,
                    "xpath_not_found": total_calls - found_calls,
                }
            )

        never_found = [
            stats["xpath"]
            for stats in xpath_stats.values()
            if stats["found_count"] == 0 and stats["error_count"] == 0
        ]
        errored = [
            stats["xpath"] for stats in xpath_stats.values() if stats["error_count"] > 0
        ]

        total_unique = len(xpath_stats)
        total_found = sum(1 for stats in xpath_stats.values() if stats["found_count"] > 0)

        return {
            "total_xpath_calls": len(self._calls),
            "unique_xpaths": total_unique,
            "unique_xpaths_found": total_found,
            "unique_xpaths_never_found": len(never_found),
            "unique_xpaths_errored": len(errored),
            "compatibility_score": round(total_found / total_unique * 100, 1)
            if total_unique > 0
            else 0.0,
            "steps": step_summaries,
            "xpath_stats": sorted(xpath_stats.values(), key=lambda x: x["xpath"]),
            "never_found_xpaths": sorted(never_found),
            "errored_xpaths": sorted(errored),
        }

    def reset(self) -> None:
        self._calls.clear()
        self._steps.clear()
        self._current_step = None
        self._current_screen = "unknown"
