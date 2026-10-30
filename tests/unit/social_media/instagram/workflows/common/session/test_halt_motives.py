"""Every motive of the shared halt latch has its own stop reason on Instagram.

The latch gained two motives the same day on two branches: the Instagram block ("Try again later")
and the desktop app gone. Merged, `for_halt` translated only the second: a run stopped by a block
would have been reported "target app crashed", and its account's restriction never shown as one.

The codes are read from the contract (`RUN_HALT_CODE`), which `test_workflow_contract_stop_reasons`
holds to the latch's constants: a code added to the latch without its branch in `for_halt` is red
here, instead of reaching the operator as « the app crashed ».
"""

import pytest

from taktik.core.contract.stop_reasons import RUN_HALT_CODE
from taktik.core.social_media.instagram.workflows.common.session import stop_reasons


@pytest.mark.parametrize("code", RUN_HALT_CODE.values)
def test_each_halt_motive_keeps_its_own_reason(code):
    reason = stop_reasons.for_halt({"code": code, "detail": "test"})

    assert reason.code == code
    assert reason.family == stop_reasons.FAMILY_FAILED
    # Also when it travels as the bare code (the TikTok loops pass strings).
    assert stop_reasons.terminal_status(code) == stop_reasons.STATUS_INTERRUPTED


# --- the end of a run, once the latch has been read -----------------------------------------

def test_the_latch_explains_an_expected_end_too():
    """The run of a single profile that the phone could not open, offline: its list ran out, so
    the loop ended on `completed`. The latch had seen the cause; its motive is the run's."""
    settled = stop_reasons.settled_by_halt(stop_reasons.completed(0), {"code": "network_lost"})

    assert settled.code == "network_lost"
    assert stop_reasons.terminal_status(settled) == stop_reasons.STATUS_INTERRUPTED


@pytest.mark.parametrize("reason", [
    stop_reasons.end_of_list(12, 40),
    stop_reasons.duration_cap(30),
    stop_reasons.navigation_lost(),
    "Limits reached",
], ids=["end_of_list", "duration_cap", "navigation_lost", "plain_string"])
def test_one_rule_for_every_end_but_three(reason):
    assert stop_reasons.settled_by_halt(reason, {"code": "account_challenge"}).code == "account_challenge"


@pytest.mark.parametrize("reason", [
    stop_reasons.manual_stop(),
    stop_reasons.crashed("boom"),
    stop_reasons.network_lost("no route"),
], ids=["manual_stop", "crashed", "already_the_latch"])
def test_a_manual_stop_a_crash_and_the_latch_own_motive_keep_theirs(reason):
    assert stop_reasons.settled_by_halt(reason, {"code": "network_lost"}) is reason


def test_without_a_halt_every_motive_stays():
    reason = stop_reasons.completed(3)

    assert stop_reasons.settled_by_halt(reason, None) is reason


def test_a_phone_locked_during_the_run_is_a_failure_with_its_motive():
    settled = stop_reasons.settled_by_halt(stop_reasons.navigation_lost(), {"code": "phone_locked"})

    assert settled.code == "phone_locked"
    assert stop_reasons.terminal_status(settled) == stop_reasons.STATUS_INTERRUPTED
