"""The cold DM menu of the CLI describes the run like the Cold DM page and runs the desktop's engine.

The menu wrote snake_case settings for the CLI's own engine (`delay_min`, `max_dms`,
`skip_private`), asked for a session duration nothing read, had no question for certified
accounts, and offered an AI mode that sent a placeholder.
"""
import pytest

from instagram_cold_dm_rig import DEVICE_ID, INSTAGRAM


@pytest.fixture
def answer(monkeypatch):
    import click
    from rich.prompt import Confirm, Prompt

    def feed(mode, answers, confirms):
        prompts, checks = iter(answers), iter(confirms)
        monkeypatch.setattr(click, "prompt", lambda *a, **k: mode)
        monkeypatch.setattr(Prompt, "ask", lambda *a, **k: next(prompts))
        monkeypatch.setattr(Confirm, "ask", lambda *a, **k: next(checks))

    return feed


def test_the_cold_dm_prompts_describe_the_run_like_the_page(answer):
    from taktik.cli.prompts import outreach as prompts

    # Manual messages; skip private: no; skip certified: yes; start: yes.
    answer(1, ["alpha, @beta", "Hello there", "", "20", "40", "12"], [False, True, True])

    assert prompts.generate_cold_dm_workflow() == {
        "recipients": ["alpha", "beta"],
        "messageMode": "manual",
        "messages": ["Hello there"],
        "delayMin": 20,
        "delayMax": 40,
        "maxDmsPerSession": 12,
        "skipPrivateAccounts": False,
        "skipVerifiedAccounts": True,
    }


def test_the_ai_mode_asks_what_the_messages_should_say(answer):
    from taktik.cli.prompts import outreach as prompts

    answer(2, ["alpha", "Invite them to the tasting", "30", "60", "5"], [True, False, True])
    payload = prompts.generate_cold_dm_workflow()

    assert payload["messageMode"] == "ai"
    assert payload["aiPrompt"] == "Invite them to the tasting"
    assert payload["messages"] == []


def test_a_menu_run_goes_through_the_desktop_engine(igc_rig):
    from taktik.cli.common.instagram_host import run_instagram_cold_dm_payload

    igc_rig.users["closed_one"] = {"private": True, "message_button": True}
    result = run_instagram_cold_dm_payload(igc_rig.device_manager, DEVICE_ID, {
        "recipients": ["open_one", "closed_one"], "messageMode": "manual", "messages": ["Hello there"],
        "delayMin": 3, "delayMax": 6, "maxDmsPerSession": 5,
        "skipPrivateAccounts": False, "skipVerifiedAccounts": False,
    })

    assert igc_rig.calls.index(f"stop {INSTAGRAM}") < igc_rig.calls.index(f"launch {INSTAGRAM}")
    assert igc_rig.sent == ["open_one", "closed_one"]
    assert result["dms_success"] == 2
