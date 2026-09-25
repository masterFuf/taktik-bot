"""One Instagram scraping config, one run: the desktop bridge and the CLI must do the same thing.

The CLI ran the Agent handler, which kept its own older reading of the payload: no profile filters
(`minPosts`, `minFollowers`, private profiles, profile picture), no `fetchLocation`, no premium
taxonomy, no `usernames` or `profile_posts` sources, and no AI service at all. The desktop restarts
Instagram before every scraping run (Electron, before the bridge); the CLI restarted nothing.
"""
from loguru import logger

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


def test_the_cli_takes_the_openrouter_key_from_the_environment(igs_rig):
    payload = hashtag_payload()
    payload["ai"] = {key: value for key, value in payload["ai"].items() if key != "openrouterApiKey"}

    result = igs_rig.run_cli(payload, env={"OPENROUTER_API_KEY": AI_KEY})

    assert result.exit_code == 0, result.output
    assert [build["api_key"] for build in igs_rig.ai_builds] == [AI_KEY]


def test_without_a_key_the_cli_scrapes_without_ai_and_says_why(igs_rig):
    payload = hashtag_payload()
    payload["ai"] = {key: value for key, value in payload["ai"].items() if key != "openrouterApiKey"}
    warnings = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        result = igs_rig.run_cli(payload, env={"OPENROUTER_API_KEY": ""})
    finally:
        logger.remove(sink)

    assert result.exit_code == 0, result.output
    assert igs_rig.ai_builds == []
    assert "run_scraping" in igs_rig.calls
    assert any("OPENROUTER_API_KEY" in line for line in warnings)


def test_the_cli_refuses_a_target_run_without_targets_before_the_phone(igs_rig):
    result = igs_rig.run_cli(target_payload(targetUsernames=[]))

    assert result.exit_code == 1, result.output
    assert "run_scraping" not in igs_rig.calls
    assert not any(call.startswith("stop ") for call in igs_rig.calls)
