"""The shared step-telemetry sink: configurable, no-op by default, never raises."""

import pytest

from taktik.core.shared import telemetry
from taktik.core.shared.telemetry import (
    StepMetric,
    emit_step,
    configure_telemetry_sink,
    clear_telemetry_sink,
    is_telemetry_active,
)


@pytest.fixture(autouse=True)
def _reset_sink():
    clear_telemetry_sink()
    yield
    clear_telemetry_sink()


def test_noop_when_unconfigured():
    assert is_telemetry_active() is False
    # Must not raise with no sink wired.
    emit_step("tap", action="press", x=1, y=2)


def test_emits_structured_metric():
    got = []
    configure_telemetry_sink(got.append)
    assert is_telemetry_active() is True

    emit_step("scroll", action="flick", target="up", distance_px=900, duration_ms=70)
    assert len(got) == 1
    m = got[0]
    assert isinstance(m, StepMetric)
    assert m.category == "scroll"
    assert m.action == "flick"
    assert m.target == "up"
    assert m.detail == {"distance_px": 900, "duration_ms": 70}
    assert m.ts > 0


def test_clear_makes_it_noop_again():
    got = []
    configure_telemetry_sink(got.append)
    emit_step("tap")
    clear_telemetry_sink()
    emit_step("tap")
    assert len(got) == 1


def test_a_throwing_sink_never_breaks_the_caller():
    def boom(_m):
        raise RuntimeError("sink down")

    configure_telemetry_sink(boom)
    # Telemetry must never propagate an error into a workflow.
    emit_step("keystroke", action="type", length=5)


def test_follower_decision_shape():
    got = []
    configure_telemetry_sink(got.append)
    emit_step(
        "follower_decision", action="skipped", target="alice",
        reason="already_processed", encounter_order=3, source_type="HASHTAG",
    )
    m = got[0]
    assert m.category == "follower_decision"
    assert m.action == "skipped"
    assert m.target == "alice"
    assert m.detail["reason"] == "already_processed"
    assert m.detail["encounter_order"] == 3
