"""Selector tracing helpers for compat diagnostics."""

import time

from bridges.compat.diagnostics.runtime.events import log


class SelectorTracer:
    """Records every XPath selector check performed during an action."""

    def __init__(self):
        self.traces: list[dict] = []
        self._screen = "unknown"
        self._family = None

    def set_screen(self, screen: str | None) -> None:
        self._screen = screen or "unknown"

    def set_screen_for_traces_since(self, start_index: int, screen: str | None) -> None:
        resolved_screen = screen or "unknown"
        for trace in self.traces[start_index:]:
            trace["screen"] = resolved_screen

    def set_action_context(self, action_id: str) -> None:
        self._family = _family_from_action_id(action_id)

    def record(self, xpath_str: str, found: bool, elapsed_ms: float | None = None) -> None:
        trace = {
            "xpath": xpath_str,
            "found": found,
            "source": "python",
            "screen": self._screen,
            "fallbackIndex": 0,
        }
        if self._family:
            trace["family"] = self._family
        if elapsed_ms is not None:
            trace["elapsedMs"] = round(elapsed_ms, 2)

        self.traces.append(trace)
        icon = "OK" if found else "MISS"
        short = xpath_str if len(xpath_str) <= 80 else "..." + xpath_str[-77:]
        log("debug", f"[selector] {icon} {short}")

    def reset(self) -> None:
        self.traces.clear()
        self._screen = "unknown"
        self._family = None


class TracedSelector:
    """Wraps a uiautomator2 XPathSelector and records `.exists` checks."""

    __slots__ = ("_o", "_xpath", "_tracer")

    def __init__(self, original, xpath_str: str, tracer: SelectorTracer):
        object.__setattr__(self, "_o", original)
        object.__setattr__(self, "_xpath", xpath_str)
        object.__setattr__(self, "_tracer", tracer)

    @property
    def exists(self) -> bool:
        original = object.__getattribute__(self, "_o")
        tracer = object.__getattribute__(self, "_tracer")
        xpath = object.__getattribute__(self, "_xpath")
        started_at = time.perf_counter()
        try:
            result = bool(original.exists)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            tracer.record(xpath, False, elapsed_ms=elapsed_ms)
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        tracer.record(xpath, result, elapsed_ms=elapsed_ms)
        return result

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_o"), name)

    def __bool__(self):
        return bool(object.__getattribute__(self, "_o"))


def _family_from_action_id(action_id: str) -> str | None:
    parts = [part for part in action_id.split(".") if part]
    if not parts:
        return None
    if parts[0] == "tt" and len(parts) > 1:
        return parts[1]
    return parts[0]


__all__ = ["SelectorTracer", "TracedSelector"]
