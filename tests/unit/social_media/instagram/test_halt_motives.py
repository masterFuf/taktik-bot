"""Every motive of the shared halt latch has its own stop reason on Instagram.

The latch gained two motives the same day on two branches: the Instagram block ("Try again later")
and the desktop app gone. Merged, `for_halt` translated only the second: a run stopped by a block
would have been reported "target app crashed", and its account's restriction never shown as one.
"""

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


@pytest.mark.parametrize("code, expected", [
    (run_halt.DEVICE_DISCONNECTED, "device_disconnected"),
    (run_halt.TARGET_APP_CRASHED, "target_app_crashed"),
    (run_halt.ACTION_BLOCKED, "action_blocked"),
    (run_halt.DESKTOP_GONE, "desktop_gone"),
])
def test_each_halt_motive_keeps_its_own_reason(code, expected):
    reason = stop_reasons.for_halt({"code": code, "detail": "test"})
    assert reason.code == expected


def test_every_motive_of_the_latch_is_covered():
    motives = {getattr(run_halt, name) for name in run_halt.__all__ if name.isupper()}
    assert motives == {run_halt.DEVICE_DISCONNECTED, run_halt.TARGET_APP_CRASHED,
                       run_halt.ACTION_BLOCKED, run_halt.DESKTOP_GONE}
