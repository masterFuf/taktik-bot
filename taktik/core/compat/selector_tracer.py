"""
SelectorTracer — Instruments DeviceFacade.xpath() to log every XPath call.

Monkey-patches BaseDeviceFacade.xpath() at runtime. Each call records:
  - xpath expression
  - found (bool)
  - elapsed_ms (float)
  - caller context (action step name)
  - timestamp

The tracer is opt-in: call `tracer.attach(device_facade)` to start,
`tracer.detach()` to stop and `tracer.report()` to get the full report.

Usage:
    tracer = SelectorTracer()
    tracer.attach(device_facade)
    # ... run workflow ...
    tracer.detach()
    report = tracer.report()
"""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class XPathCall:
    """Record of a single xpath() invocation."""
    xpath: str
    found: bool
    elapsed_ms: float
    step: str
    timestamp: float
    error: Optional[str] = None
    screen: str = "unknown"


@dataclass
class WorkflowStep:
    """A named step in the workflow (e.g. 'navigate_to_profile')."""
    name: str
    started_at: float
    ended_at: float = 0.0
    success: bool = True
    error: Optional[str] = None
    xpath_calls: List[XPathCall] = field(default_factory=list)


class SelectorTracer:
    """
    Instruments BaseDeviceFacade.xpath() to record every XPath call.

    Thread-safe: only one tracer should be active at a time.
    """

    def __init__(self, on_xpath_call=None):
        self._calls: List[XPathCall] = []
        self._steps: List[WorkflowStep] = []
        self._current_step: Optional[WorkflowStep] = None
        self._attached_device = None
        self._original_xpath = None
        self._active = False
        self._on_xpath_call = on_xpath_call  # Optional callback(XPathCall)
        self._current_screen: str = "unknown"  # Current UI screen context

    # ------------------------------------------------------------------
    # Attach / Detach
    # ------------------------------------------------------------------

    def attach(self, device_facade) -> None:
        """Monkey-patch the device facade's xpath() method."""
        if self._active:
            return

        self._attached_device = device_facade
        self._original_xpath = device_facade.xpath
        self._active = True

        tracer = self  # closure reference

        def instrumented_xpath(xpath_expr: str):
            t0 = time.time()
            result = None
            found = False
            error_msg = None

            try:
                result = tracer._original_xpath(xpath_expr)
                # Check .exists without triggering another instrumented call
                if result is not None and hasattr(result, 'exists'):
                    try:
                        found = result.exists
                    except Exception:
                        found = False
            except Exception as e:
                error_msg = str(e)

            elapsed = (time.time() - t0) * 1000  # ms

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

            # Real-time callback
            if tracer._on_xpath_call:
                try:
                    tracer._on_xpath_call(call)
                except Exception:
                    pass  # Never let callback errors break the workflow

            return result

        device_facade.xpath = instrumented_xpath
        logger.info("[SelectorTracer] Attached to device facade")

    def detach(self) -> None:
        """Restore the original xpath() method."""
        if not self._active:
            return
        if self._attached_device and self._original_xpath:
            self._attached_device.xpath = self._original_xpath
        self._active = False
        self._attached_device = None
        self._original_xpath = None
        logger.info("[SelectorTracer] Detached from device facade")

    # ------------------------------------------------------------------
    # Step tracking
    # ------------------------------------------------------------------

    def set_screen(self, screen: str) -> None:
        """Update the current UI screen context (e.g. 'home', 'profile', 'followers_list')."""
        self._current_screen = screen

    @property
    def current_screen(self) -> str:
        return self._current_screen

    def begin_step(self, name: str) -> None:
        """Mark the beginning of a workflow step."""
        if self._current_step and self._current_step.ended_at == 0.0:
            self._current_step.ended_at = time.time()
            self._steps.append(self._current_step)
        self._current_step = WorkflowStep(name=name, started_at=time.time())

    def end_step(self, success: bool = True, error: str = None) -> None:
        """Mark the end of the current workflow step."""
        if self._current_step:
            self._current_step.ended_at = time.time()
            self._current_step.success = success
            self._current_step.error = error
            self._steps.append(self._current_step)
            self._current_step = None

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def report(self) -> Dict[str, Any]:
        """Generate a full compatibility report."""
        # Finalize any open step
        if self._current_step and self._current_step.ended_at == 0.0:
            self._current_step.ended_at = time.time()
            self._steps.append(self._current_step)
            self._current_step = None

        # Aggregate per-xpath stats
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
            s = xpath_stats[key]
            s["total_calls"] += 1
            if call.error:
                s["error_count"] += 1
            elif call.found:
                s["found_count"] += 1
            else:
                s["not_found_count"] += 1
            s["avg_ms"] += call.elapsed_ms
            s["steps_used_in"].add(call.step)
            s["screens_used_in"].add(call.screen)

        # Finalize averages and convert sets
        for s in xpath_stats.values():
            if s["total_calls"] > 0:
                s["avg_ms"] = round(s["avg_ms"] / s["total_calls"], 2)
            s["steps_used_in"] = sorted(s["steps_used_in"])
            s["screens_used_in"] = sorted(s["screens_used_in"])

        # Build step summaries
        step_summaries = []
        for step in self._steps:
            total_calls = len(step.xpath_calls)
            found_calls = sum(1 for c in step.xpath_calls if c.found)
            step_summaries.append({
                "name": step.name,
                "success": step.success,
                "error": step.error,
                "duration_ms": round((step.ended_at - step.started_at) * 1000, 2),
                "xpath_calls": total_calls,
                "xpath_found": found_calls,
                "xpath_not_found": total_calls - found_calls,
            })

        # Unique xpaths that were NEVER found across all calls
        never_found = [
            s["xpath"] for s in xpath_stats.values()
            if s["found_count"] == 0 and s["error_count"] == 0
        ]

        # Unique xpaths that had errors
        errored = [
            s["xpath"] for s in xpath_stats.values()
            if s["error_count"] > 0
        ]

        total_unique = len(xpath_stats)
        total_found = sum(1 for s in xpath_stats.values() if s["found_count"] > 0)

        return {
            "total_xpath_calls": len(self._calls),
            "unique_xpaths": total_unique,
            "unique_xpaths_found": total_found,
            "unique_xpaths_never_found": len(never_found),
            "unique_xpaths_errored": len(errored),
            "compatibility_score": round(total_found / total_unique * 100, 1) if total_unique > 0 else 0.0,
            "steps": step_summaries,
            "xpath_stats": sorted(xpath_stats.values(), key=lambda x: x["xpath"]),
            "never_found_xpaths": sorted(never_found),
            "errored_xpaths": sorted(errored),
        }

    def reset(self) -> None:
        """Clear all collected data."""
        self._calls.clear()
        self._steps.clear()
        self._current_step = None
        self._current_screen = "unknown"
