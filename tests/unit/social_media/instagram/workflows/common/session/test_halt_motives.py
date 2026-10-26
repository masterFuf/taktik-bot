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
