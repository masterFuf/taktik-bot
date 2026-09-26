"""One TikTok scraping config, one run: the desktop bridge and the CLI read it the same way, start
TikTok the same way and file the same rows.

The CLI's handler had its own reading of the payload: no post links, no commenter budget, no
sound, no budget of posts per account, so the post, sound and account-posts modes scraped with
empty settings. It started nothing (no clean restart, no language), and wrote nothing: no
scraping session, no profile, because only the bridge held the database writes.
"""
import dataclasses

import pytest

SCRAPING_ID = "tiktok.automation.scraping"


def _run_both(rig, payload, set_phone=lambda: None):
    """The bridge gets the app's config file; the CLI gets the same keys, as a terminal user writes
    them (the serial comes from `--device`)."""
    rig.install_scraping_database()
    set_phone()
    bridge_exit = rig.run_scraping_bridge(payload)
    bridge = {"exit": bridge_exit, "calls": list(rig.calls), "db_writes": list(rig.db_writes),
              "configs": [dataclasses.asdict(config) for config in rig.built_configs]}
    rig.forget_run()

    set_phone()
    cli_payload = {key: value for key, value in payload.items() if key != "deviceId"}
    result = rig.run_cli(cli_payload, workflow_id=SCRAPING_ID)
    cli = {"exit": result.exit_code, "calls": list(rig.calls), "db_writes": list(rig.db_writes),
           "configs": [dataclasses.asdict(config) for config in rig.built_configs],
           "result": rig.cli_results[-1] if rig.cli_results else None, "output": result.output}
    return bridge, cli


def test_a_cli_scraping_starts_tiktok_like_the_bridge(rig, scraping_payload):
    bridge, cli = _run_both(rig, scraping_payload())

    assert cli["exit"] == bridge["exit"] == 0, cli["output"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert "detect_language" in cli["calls"]
    assert cli["calls"] == bridge["calls"]


@pytest.mark.parametrize("mode", ["target", "hashtag", "post_url", "sound", "account_posts", "scheduler_node"])
def test_a_cli_scraping_builds_the_config_the_bridge_builds(rig, scraping_payload, mode):
    bridge, cli = _run_both(rig, scraping_payload(mode))

    assert cli["exit"] == 0, cli["output"]
    assert cli["configs"] == bridge["configs"]


def test_a_cli_post_scraping_reads_the_links_and_their_budget(rig, scraping_payload):
    bridge, cli = _run_both(rig, scraping_payload("post_url"))

    config = cli["configs"][0]
    assert config["post_urls"] == ["https://www.tiktok.com/@creator/video/1", "https://vm.tiktok.com/ZNexample/"]
    assert config["max_commenters_per_post"] == 5
    assert cli["result"]["total_scraped"] == 2


def test_a_cli_sound_and_account_posts_scraping_keep_their_settings(rig, scraping_payload):
    _bridge, sound = _run_both(rig, scraping_payload("sound"))
    rig.forget_run()
    _bridge, posts = _run_both(rig, scraping_payload("account_posts"))

    assert sound["configs"][0]["sound_query"] == "summer anthem"
    assert sound["configs"][0]["max_users_per_sound"] == 4
    assert posts["configs"][0]["max_posts_per_account"] == 6


def test_a_cli_scraping_files_its_session_and_profiles_like_the_bridge(rig, scraping_payload):
    bridge, cli = _run_both(rig, scraping_payload("hashtag"))

    assert cli["exit"] == 0, cli["output"]
    assert cli["db_writes"] == bridge["db_writes"]
    kinds = [next(iter(write)) for write in cli["db_writes"]]
    assert kinds == ["scraping_session", "scraped_profile", "scraped_profile", "scraping_session_end"]
    assert cli["db_writes"][0]["scraping_session"]["source_type"] == "HASHTAG"
    assert cli["db_writes"][-1]["scraping_session_end"]["status"] == "COMPLETED"


def test_a_run_told_not_to_save_writes_nothing_on_either_path(rig, scraping_payload):
    bridge, cli = _run_both(rig, scraping_payload(saveToDb=False))

    assert cli["exit"] == 0, cli["output"]
    assert bridge["db_writes"] == cli["db_writes"] == []


def test_a_stopped_run_is_filed_cancelled_on_both_paths(rig, scraping_payload):
    def set_phone():
        rig.scraping_reason = "stopped_by_user"

    bridge, cli = _run_both(rig, scraping_payload(), set_phone=set_phone)

    assert cli["db_writes"] == bridge["db_writes"]
    assert cli["db_writes"][-1]["scraping_session_end"]["status"] == "CANCELLED"


def test_a_target_run_without_an_account_is_refused_before_the_phone_on_both_paths(rig, scraping_payload):
    bridge, cli = _run_both(rig, scraping_payload(targetUsernames=[]))

    assert bridge["exit"] == cli["exit"] == 1
    assert bridge["calls"] == cli["calls"] == []
    assert bridge["db_writes"] == cli["db_writes"] == []
    assert "requires targetUsernames" in cli["output"]
