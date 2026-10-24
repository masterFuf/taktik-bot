"""An Instagram scraping run starts and reads the Instagram its payload names, from the desktop and the CLI.

The scraping read `packageName` only to choose the selector overrides of the installed version: the
desktop restarted the official Instagram before launching its bridge, and neither path matched the
selectors to a clone nor made its package the active one, as the automation does. A phone set to run a
clone scraped on the official app, another account. The bridge now restarts the run's Instagram itself,
as the CLI does, and the launcher matches the selectors to the clone.
"""

import pytest

from instagram_scraping_rig import INSTAGRAM, target_payload

CLONE = "com.taktik.ig1"


def _bridge_calls(rig, payload):
    code = rig.run_bridge(payload)
    assert code == 0, rig.stdout_lines
    calls = list(rig.calls)
    rig.reset()
    return calls


def _cli_calls(rig, payload):
    result = rig.run_cli(payload)
    assert result.exit_code == 0, result.output
    calls = list(rig.calls)
    rig.reset()
    return calls


def _launched(calls, package):
    return [i for i, call in enumerate(calls) if call.startswith(f"launch {package} ")]


def test_the_desktop_scraping_restarts_instagram_itself_before_the_run(igs_rig):
    calls = _bridge_calls(igs_rig, target_payload())

    assert f"stop {INSTAGRAM}" in calls, calls
    assert _launched(calls, INSTAGRAM), calls
    assert calls.index(f"stop {INSTAGRAM}") < _launched(calls, INSTAGRAM)[0] < calls.index("run_scraping")


@pytest.mark.parametrize("path", ["bridge", "cli"])
def test_a_scraping_restarts_the_clone_its_payload_names(igs_rig, path):
    calls = (_bridge_calls if path == "bridge" else _cli_calls)(igs_rig, target_payload(packageName=CLONE))

    assert f"stop {CLONE}" in calls, calls
    assert _launched(calls, CLONE), calls
    assert not _launched(calls, INSTAGRAM), calls
    assert _launched(calls, CLONE)[0] < calls.index("run_scraping")


@pytest.mark.parametrize("path", ["bridge", "cli"])
def test_a_scraping_matches_the_selectors_to_its_clone_before_the_workflow(igs_rig, path):
    from taktik.core.clone import get_active_package, set_active_package

    set_active_package(INSTAGRAM)
    try:
        calls = (_bridge_calls if path == "bridge" else _cli_calls)(igs_rig, target_payload(packageName=CLONE))
        workflow = next(i for i, call in enumerate(calls) if call.startswith("workflow "))

        assert f"clone_patch {CLONE}" in calls, calls
        assert calls.index(f"clone_patch {CLONE}") < workflow
        assert get_active_package() == CLONE
    finally:
        set_active_package(INSTAGRAM)


def test_a_scraping_without_a_clone_patches_nothing(igs_rig):
    calls = _bridge_calls(igs_rig, target_payload())

    assert not [call for call in calls if call.startswith("clone_patch")], calls
