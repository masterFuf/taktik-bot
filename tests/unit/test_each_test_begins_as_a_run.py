"""The harness begins each test as a run (`run_start.begin_run`, `tests/unit/conftest.py`).

A pytest process plays thousands of tests, as the CLI's menu plays runs one after another. The harness
used to lift the stop latch only: the failure captures' cap, the screen ring and the foreground
check's clock went from one test to the next, so a test that filled the cap made the captures of a
later one silently skipped, depending on the order the tests ran in.

The first test leaves what a run leaves, as a test that forgot to clean would; the second, played
after it in the same process, must find nothing of it. Under xdist the two may land on different
workers: the second then has nothing to check, and says so.
"""
from __future__ import annotations

import pytest

from taktik.core.shared.diagnostics import foreground_guard, miss_capture, run_halt, screen_ring

_left_behind = False


def test_a_test_that_leaves_what_a_run_leaves():
    global _left_behind
    miss_capture._captures = miss_capture.MAX_PAR_RUN
    miss_capture._dernier_selecteur = "back_button"
    miss_capture._repetitions = miss_capture.SEUIL_BLOCAGE
    foreground_guard._dernier_controle = 1.0e9
    screen_ring._anneau.append({"fingerprint": "an earlier test"})
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")
    _left_behind = True


def test_the_next_test_starts_without_it():
    if not _left_behind:
        pytest.skip("the test that leaves the state ran in another worker")

    assert (miss_capture._captures, miss_capture._dernier_selecteur, miss_capture._repetitions) == (0, None, 0)
    assert foreground_guard._dernier_controle == 0.0
    assert screen_ring._anneau == []
    assert run_halt.arret_demande() is None
