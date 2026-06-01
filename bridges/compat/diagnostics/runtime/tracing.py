"""Selector tracing helpers for compat diagnostics."""

from bridges.compat.diagnostics.runtime.events import log


class SelectorTracer:
    """Records every XPath selector check performed during an action."""

    def __init__(self):
        self.traces: list[dict] = []

    def record(self, xpath_str: str, found: bool) -> None:
        self.traces.append({"xpath": xpath_str, "found": found})
        icon = "OK" if found else "MISS"
        short = xpath_str if len(xpath_str) <= 80 else "..." + xpath_str[-77:]
        log("debug", f"[selector] {icon} {short}")


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
        result = original.exists
        tracer.record(xpath, result)
        return result

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_o"), name)

    def __bool__(self):
        return bool(object.__getattribute__(self, "_o"))


__all__ = ["SelectorTracer", "TracedSelector"]

