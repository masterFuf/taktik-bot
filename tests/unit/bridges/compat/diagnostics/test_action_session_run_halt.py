"""The Cartography Lab session serves one action after another in the same process.

`run_bridge_main` lifts the run's stop lock once per process; a Lab session is one process for
many actions. Without a lift per action, a block or a lost phone seen by one action ended every
workflow action after it while the session stayed open (secours 2, 2026-09-24).
"""

import inspect

from bridges.compat.diagnostics.runtime.action_test import session
from taktik.core.shared.diagnostics import run_halt


def test_each_action_starts_without_the_previous_stop():
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    session._begin_action_run()

    assert run_halt.arret_demande() is None


def test_the_session_loop_lifts_it_before_running_the_action():
    source = inspect.getsource(session.run_action_session_bridge)

    assert source.index("_begin_action_run()") < source.index("_execute_action(")
