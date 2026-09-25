"""The Instagram automation menus of the CLI run the desktop's launcher, not a third translation.

`taktik automation workflow` and the interactive menu wrote the workflow's internal format
themselves (session settings, actions) and built the automation by hand: no clean restart, no
warmup caps, no AI, a blacklist prompt and canned comments nothing read. The prompts now describe
the run the way a desktop page does, and the run goes through the automation handler.
"""
import json

import pytest
from click.testing import CliRunner

from instagram_rig import DEVICE_ID, INSTAGRAM, feed_payload


@pytest.fixture
def cli_main(ig_rig, monkeypatch):
    from taktik.cli import main

    monkeypatch.setattr(main, "DeviceManager", lambda *a, **k: ig_rig.device_manager)
    return main


def _write(tmp_path, payload) -> str:
    path = tmp_path / "run.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_a_page_file_runs_through_the_launcher(ig_rig, cli_main, tmp_path):
    result = CliRunner().invoke(
        cli_main.workflow_instagram, ["--device-id", DEVICE_ID, "--config", _write(tmp_path, feed_payload())]
    )

    assert result.exit_code == 0, result.output
    restart = [f"is_installed {INSTAGRAM}", f"stop {INSTAGRAM}"]
    assert ig_rig.calls[ig_rig.calls.index(restart[0]):][:2] == restart
    assert ig_rig.calls.index(f"stop {INSTAGRAM}") < ig_rig.calls.index("run_workflow")
    assert ig_rig.built_config["session_settings"]["warmup_policy"]["max_actions_per_day"] == 40


def test_a_file_in_the_internal_format_is_refused(ig_rig, cli_main, tmp_path):
    internal = {"session_settings": {"total_profiles_limit": 5}, "actions": [{"type": "feed"}]}

    result = CliRunner().invoke(
        cli_main.workflow_instagram, ["--device-id", DEVICE_ID, "--config", _write(tmp_path, internal)]
    )

    assert result.exit_code == 1, result.output
    assert "run_workflow" not in ig_rig.calls


def test_the_menu_prompts_describe_the_run_like_a_page(monkeypatch):
    from rich.prompt import Prompt

    from taktik.cli.context import update_language_state
    from taktik.cli.prompts import instagram as prompts
    from taktik.locales import en

    update_language_state(en.TRANSLATIONS, en.BANNER)
    answers = iter([
        "alpha, beta",  # targets
        "2",            # the accounts they follow
        "6", "3",       # profiles, likes per profile
        "40", "5", "0", "20", "10",  # like, follow, comment, story, story like
        "10", "9000", "2", "3000",   # followers min/max, posts min, following max
        "25", "4", "12",             # duration, delay min/max
    ])
    monkeypatch.setattr(Prompt, "ask", lambda *a, **k: next(answers))

    payload = prompts.generate_target_workflow()

    assert payload == {
        "workflowType": "target_following",
        "target": "alpha,beta",
        "limits": {"maxProfiles": 6, "maxLikesPerProfile": 3},
        "probabilities": {"like": 40, "follow": 5, "comment": 0, "watchStories": 20, "likeStories": 10},
        "filters": {"minFollowers": 10, "maxFollowers": 9000, "minPosts": 2, "maxFollowing": 3000},
        "session": {"durationMinutes": 25, "minDelay": 4, "maxDelay": 12},
    }


def test_the_hashtag_prompts_keep_their_post_criteria(monkeypatch):
    from rich.prompt import Prompt

    from taktik.cli.context import update_language_state
    from taktik.cli.prompts import instagram as prompts
    from taktik.locales import en

    update_language_state(en.TRANSLATIONS, en.BANNER)
    answers = iter(["#cuisine", "200", "9000", "5", "2", "30", "0", "0", "0", "0",
                    "10", "50000", "3", "7500", "30", "5", "15"])
    monkeypatch.setattr(Prompt, "ask", lambda *a, **k: next(answers))

    payload = prompts.generate_hashtags_workflow()

    assert payload["workflowType"] == "hashtags"
    assert payload["target"] == "cuisine"
    assert payload["postCriteria"] == {"minLikes": 200, "maxLikes": 9000}
