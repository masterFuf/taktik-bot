import threading
import time

from taktik.core.shared.actions.optional_call import run_bounded_optional


def test_never_returning_optional_call_cannot_block_the_caller():
    release = threading.Event()
    started_at = time.monotonic()

    result = run_bounded_optional(
        lambda: release.wait(10),
        timeout_seconds=0.03,
        label="test stalled device read",
    )
    elapsed = time.monotonic() - started_at
    release.set()

    assert result.completed is False
    assert result.timed_out is True
    assert elapsed < 0.3


def test_completed_optional_call_returns_its_value():
    result = run_bounded_optional(
        lambda: {"biography": "complete"},
        timeout_seconds=0.2,
        label="test completed read",
    )

    assert result.completed is True
    assert result.timed_out is False
    assert result.value == {"biography": "complete"}
