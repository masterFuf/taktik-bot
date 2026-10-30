"""One Instagram scraping config, one run: the desktop bridge and the CLI must do the same thing.

The CLI ran the Agent handler, which kept its own older reading of the payload: no profile filters
(`minPosts`, `minFollowers`, private profiles, profile picture), no `fetchLocation`, no premium
taxonomy, no `usernames` or `profile_posts` sources, and no AI service at all. The desktop restarts
Instagram before every scraping run (Electron, before the bridge); the CLI restarted nothing.
Neither path read the app language at the start, as the automation does (`runtime_setup`).
"""

import pytest

from taktik.core.shared.device import screen
from instagram_scraping_rig import (
    AI_KEY,
    INSTAGRAM,
    hashtag_payload,
    post_url_payload,
    profile_posts_payload,
    target_payload,
    usernames_payload,
)


def _run_both(rig, payload, env=None):
    code = rig.run_bridge(payload)
    assert code == 0, rig.stdout_lines
    bridge = {"config": rig.built_config, "ai": [dict(build, ipc=None) for build in rig.ai_builds]}
    rig.reset()

    result = rig.run_cli(payload, env=env)
    assert result.exit_code == 0, result.output
    cli = {"config": rig.built_config, "ai": [dict(build, ipc=None) for build in rig.ai_builds],
           "calls": list(rig.calls)}
    return bridge, cli


def test_the_cli_builds_the_config_the_bridge_builds(igs_rig):
    bridge, cli = _run_both(igs_rig, target_payload())

    assert cli["config"] == bridge["config"]
    assert cli["config"]["minPosts"] == 1
    assert cli["config"]["skipPrivateProfiles"] is False
    assert cli["config"]["fetchLocation"] is True


def test_a_hashtag_run_with_ai_builds_the_same_service_from_both_paths(igs_rig):
    bridge, cli = _run_both(igs_rig, hashtag_payload())

    assert cli["config"] == bridge["config"]
    assert bridge["ai"], "the bridge built no AI service"
    assert cli["ai"] == bridge["ai"]
    assert cli["config"]["niche_taxonomy"] == {"food": ["baking"]}


def test_a_post_url_run_reads_its_links_and_populations_the_same_way(igs_rig):
    bridge, cli = _run_both(igs_rig, post_url_payload())

    assert cli["config"] == bridge["config"]
    assert cli["config"]["scrape_commenters"] is True and cli["config"]["scrape_likers"] is False


def test_the_cli_reaches_the_usernames_source(igs_rig):
    bridge, cli = _run_both(igs_rig, usernames_payload())

    assert cli["config"] == bridge["config"]
    assert cli["config"]["usernames"] == ["first_account", "second_account"]


def test_the_cli_reaches_the_profile_posts_source(igs_rig):
    bridge, cli = _run_both(igs_rig, profile_posts_payload())

    assert cli["config"] == bridge["config"]
    assert cli["config"]["scrape_type"] == "profile_posts"


def test_the_cli_restarts_instagram_before_scraping_like_the_app(igs_rig):
    _bridge, cli = _run_both(igs_rig, target_payload())

    steps = cli["calls"]
    restart = [f"is_installed {INSTAGRAM}", f"stop {INSTAGRAM}"]
    assert steps[steps.index(restart[0]):][:2] == restart
    assert steps.index(f"stop {INSTAGRAM}") < steps.index("run_scraping")


_SELECTOR_SETUP = ("installed_version", "version_overrides", "clone_patch", "detect_language")


def _selector_setup(calls):
    return [call for call in calls if call.split(" ")[0] in _SELECTOR_SETUP]


def _workflow_built(calls):
    return next(i for i, call in enumerate(calls) if call.startswith("workflow "))


def test_both_paths_match_the_selectors_to_the_phone_before_the_workflow(igs_rig):
    """A phone on another version or in another language: the overrides of the installed version,
    then the app language, before the workflow reads a screen. The launcher did neither: only the
    connection applied the official app's overrides, and the language was never read."""
    igs_rig.installed_version = "447.0.0.55.81"
    assert igs_rig.run_bridge(target_payload()) == 0, igs_rig.stdout_lines
    bridge = list(igs_rig.calls)
    igs_rig.reset()
    result = igs_rig.run_cli(target_payload())
    assert result.exit_code == 0, result.output
    cli = list(igs_rig.calls)

    expected = [f"installed_version {INSTAGRAM}", "version_overrides 447.0.0.55.81", "detect_language"]
    for calls in (bridge, cli):
        assert _selector_setup(calls) == expected
        assert calls.index("detect_language") < _workflow_built(calls) < calls.index("run_scraping")


def test_the_cli_takes_the_openrouter_key_from_the_environment(igs_rig):
    payload = hashtag_payload()
    payload["ai"] = {key: value for key, value in payload["ai"].items() if key != "openrouterApiKey"}

    result = igs_rig.run_cli(payload, env={"OPENROUTER_API_KEY": AI_KEY})

    assert result.exit_code == 0, result.output
    assert [build["api_key"] for build in igs_rig.ai_builds] == [AI_KEY]


def test_without_a_key_a_scripted_ai_scraping_is_refused_before_the_phone(igs_rig):
    payload = hashtag_payload()
    payload["ai"] = {key: value for key, value in payload["ai"].items() if key != "openrouterApiKey"}

    result = igs_rig.run_cli(payload, env={"OPENROUTER_API_KEY": ""})

    assert result.exit_code == 2, result.output
    assert "OPENROUTER_API_KEY" in result.output
    assert igs_rig.ai_builds == []
    assert "run_scraping" not in igs_rig.calls


def test_a_scraping_without_ai_needs_no_key(igs_rig):
    payload = hashtag_payload()
    payload["ai"] = {"enabled": False}

    result = igs_rig.run_cli(payload, env={"OPENROUTER_API_KEY": ""})

    assert result.exit_code == 0, result.output
    assert "run_scraping" in igs_rig.calls
    assert igs_rig.ai_builds == []


def test_the_cli_refuses_a_target_run_without_targets_before_the_phone(igs_rig):
    result = igs_rig.run_cli(target_payload(targetUsernames=[]))

    assert result.exit_code == 1, result.output
    # Not even the CLI's connection: the reader refuses a run with nothing to scrape.
    assert igs_rig.calls == []


@pytest.mark.parametrize("payload, why", [
    (target_payload(sessionDurationMinutes=601), "sessionDurationMinutes = 601"),
    (target_payload(targetUsernames=[]), "requires targetUsernames"),
    (hashtag_payload(hashtags=[], hashtag=None), "requires hashtags"),
])
def test_a_refused_scraping_touches_no_phone_from_either_path(igs_rig, payload, why):
    """The launcher reads (bounds, then a source to scrape), then asks its host for the phone: the
    bridge connects in that call, the CLI too, so a refused run connects nothing. A run with nothing
    to scrape used to be refused by the launcher after the bridge had connected; the CLI connected
    before it called the handler."""
    assert igs_rig.run_bridge(payload) == 1
    assert igs_rig.calls == []
    assert why in igs_rig.stdout_lines[-1]["error"]
    igs_rig.reset()

    result = igs_rig.run_cli(payload)

    assert result.exit_code == 1, result.output
    assert igs_rig.calls == []
    assert why in " ".join(result.output.split())


def _error_codes(events):
    return [fields.get("error_code") for kind, fields in events if kind == "error"]


def test_a_locked_phone_scrapes_nothing_from_either_path(igs_rig, monkeypatch):
    """The run of a C57S on its lock screen (2026-10-30): a minute of misses, `target_never_reached`.
    Both paths now refuse it at the launcher's door, with its motive, before Instagram restarts."""
    monkeypatch.setattr(screen, "_dumpsys_window", lambda serial: "    mDreamingLockscreen=true isKeyguardShowing=true")
    monkeypatch.setattr(screen, "_tell_phone", lambda serial, command: None)
    monkeypatch.setattr(screen, "LIFT_CHECK_DELAY_S", 0)

    assert igs_rig.run_bridge(target_payload()) == 1
    assert _error_codes(igs_rig.events)[-1] == "PHONE_LOCKED"
    assert igs_rig.stdout_lines[-1]["error_code"] == "PHONE_LOCKED"
    assert "run_scraping" not in igs_rig.calls and "detect_language" not in igs_rig.calls
    igs_rig.reset()

    result = igs_rig.run_cli(target_payload())

    assert result.exit_code == 1, result.output
    assert "PHONE_LOCKED" in result.output
    assert "run_scraping" not in igs_rig.calls and f"stop {INSTAGRAM}" not in igs_rig.calls


def test_a_phone_without_network_scrapes_nothing_from_either_path(igs_rig):
    """No route at all: a scraping read the phone's cache and recorded empty profiles as measures.
    Neither path measured the network; both now refuse the run at the launcher's network door, once
    the phone is connected, before Instagram restarts and before a screen is read."""
    igs_rig.network.cut()

    assert igs_rig.run_bridge(target_payload()) == 1
    assert _error_codes(igs_rig.events)[-1] == "NETWORK_UNREACHABLE"
    assert igs_rig.stdout_lines[-1]["success"] is False
    # The last line the app reads carries the motive, for the page to say its sentence.
    assert igs_rig.stdout_lines[-1]["error_code"] == "NETWORK_UNREACHABLE"
    assert "run_scraping" not in igs_rig.calls and "detect_language" not in igs_rig.calls
    igs_rig.reset()

    result = igs_rig.run_cli(target_payload())

    assert result.exit_code == 1, result.output
    assert "NETWORK_UNREACHABLE" in result.output
    assert "run_scraping" not in igs_rig.calls and f"stop {INSTAGRAM}" not in igs_rig.calls


def test_both_paths_measure_the_network_once_before_scraping(igs_rig):
    """The door is the launcher's, crossed by both hosts: one measure, once the phone is connected,
    before the CLI's clean restart and before the selectors are matched to the phone."""
    igs_rig.network.calls = igs_rig.calls
    for run in (lambda: igs_rig.run_bridge(target_payload()), lambda: igs_rig.run_cli(target_payload())):
        run()
        measures = [call for call in igs_rig.calls if call.startswith("network_baseline ")]
        assert measures == ["network_baseline emulator-5554"]
        measured = igs_rig.calls.index(measures[0])
        connected = next(i for i, call in enumerate(igs_rig.calls) if call in ("connect", "cli_connect emulator-5554"))
        assert connected < measured < igs_rig.calls.index("detect_language")
        if f"stop {INSTAGRAM}" in igs_rig.calls:
            assert measured < igs_rig.calls.index(f"stop {INSTAGRAM}")
        igs_rig.reset()


# ---- The Instagram the payload names ---------------------------------------------------------------
#
# An Instagram scraping run starts and reads the Instagram its payload names, from the desktop and the CLI.
#
# The scraping read `packageName` only to choose the selector overrides of the installed version: the
# desktop restarted the official Instagram before launching its bridge, and neither path matched the
# selectors to a clone nor made its package the active one, as the automation does. A phone set to run a
# clone scraped on the official app, another account. The bridge now restarts the run's Instagram itself,
# as the CLI does, and the launcher matches the selectors to the clone.

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
