"""Platform-agnostic step telemetry.

A single, dependency-free sink the shared low-level primitives (keyboard, taps,
gestures) and the platform workflows emit fine-grained metrics to — one event
per atomic action (keystroke, tap, double-tap, button click, scroll/flick,
post entry, follower decision, …). The bridge layer wires the sink to stdout
JSON; when no sink is configured (standalone / tests) every emit is a cheap
no-op, so primitives can call it unconditionally.

This lives under `shared/` (never imports `social_media/<platform>`) so the
shared primitives can emit without violating the layering invariant.
"""

from taktik.core.shared.telemetry.sink import (
    StepMetric,
    emit_step,
    configure_telemetry_sink,
    clear_telemetry_sink,
    is_telemetry_active,
)

__all__ = [
    "StepMetric",
    "emit_step",
    "configure_telemetry_sink",
    "clear_telemetry_sink",
    "is_telemetry_active",
]
