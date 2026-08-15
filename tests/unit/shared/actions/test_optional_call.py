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
    # The invariant is "the caller did NOT wait out the 10s stall", not a precise budget.
    # A tight bound here measured the machine's thread scheduling rather than the code, and
    # went red on a loaded PC — which is exactly the machine this bot runs on, with several
    # devices attached. Half the stall keeps the test discriminating (an unbounded call
    # takes the full 10s) while ignoring load.
    assert elapsed < 5.0


def test_completed_optional_call_returns_its_value():
    result = run_bounded_optional(
        lambda: {"biography": "complete"},
        timeout_seconds=0.2,
        label="test completed read",
    )

    assert result.completed is True
    assert result.timed_out is False
    assert result.value == {"biography": "complete"}
