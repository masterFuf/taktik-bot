"""A manual CLI run, without any OpenRouter key, never reaches an AI client.

Each run goes the whole CLI path (`taktik workflows run <id> --json`) on a recording phone, with no
key in the environment and none saved. The AI construction points are wrapped: the factory's
`create_ai_service` and `build_ai_service` (every AI service of the bot is built there), the
OpenRouter client's constructor and the HTTP call. A manual run touches none of them and ends
normally. The control runs, the same payloads with AI on and a key, do reach the wrapped factory:
the wrap sees AI when there is some.
"""
import pytest

from instagram_cold_dm_rig import AI_KEY as COLD_DM_KEY, cold_dm_payload
from instagram_rig import AI_KEY as AUTOMATION_KEY, target_payload
from instagram_scraping_rig import AI_KEY as SCRAPING_KEY, hashtag_payload
from instagram_dm_rig import dm_command


@pytest.fixture
def ai_reached(monkeypatch):
    """Wrap every way to an AI client; the list says which ones a run took."""
    import urllib.request

    from taktik.core.app.ai import factory
    from taktik.core.app.ai.providers import openrouter

    reached = []

    def wrap(name, inner):
        def wrapper(*args, **kwargs):
            reached.append(name)
            return inner(*args, **kwargs)
        return wrapper

    def install():
        # After the rig: its fakes stay what answers, the wrap only records who called them.
        monkeypatch.setattr(factory, "create_ai_service", wrap("create_ai_service", factory.create_ai_service))
        monkeypatch.setattr(factory, "build_ai_service", wrap("build_ai_service", factory.build_ai_service))

    def refuse_client(*_args, **_kwargs):
        reached.append("AIService")
        raise AssertionError("the OpenRouter client must not be built")

    def refuse_http(*_args, **_kwargs):
        reached.append("urlopen")
        raise AssertionError("no HTTP call in tests")

    monkeypatch.setattr(openrouter.AIService, "__init__", refuse_client)
    monkeypatch.setattr(urllib.request, "urlopen", refuse_http)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return reached, install


def test_a_manual_instagram_automation(ig_rig, ai_reached):
    reached, install = ai_reached
    install()
    result = ig_rig.run_cli(target_payload())
    assert result.exit_code == 0, result.output
    assert ig_rig.workflows
    assert reached == [] and ig_rig.ai_services == [] and ig_rig.ai_installs == []


def test_control_an_instagram_automation_with_ai_reaches_the_factory(ig_rig, ai_reached):
    reached, install = ai_reached
    install()
    result = ig_rig.run_cli(target_payload(ai={"enabled": True, "profileAnalysis": True}),
                            env={"OPENROUTER_API_KEY": AUTOMATION_KEY})
    assert result.exit_code == 0, result.output
    assert "create_ai_service" in reached


def test_a_manual_instagram_scraping(igs_rig, ai_reached):
    reached, install = ai_reached
    install()
    result = igs_rig.run_cli(hashtag_payload(ai={"enabled": False}))
    assert result.exit_code == 0, result.output
    assert "run_scraping" in igs_rig.calls
    assert reached == [] and igs_rig.ai_builds == []


def test_control_an_instagram_scraping_with_ai_reaches_the_factory(igs_rig, ai_reached):
    reached, install = ai_reached
    install()
    payload = hashtag_payload()
    payload["ai"] = {key: value for key, value in payload["ai"].items() if key != "openrouterApiKey"}
    result = igs_rig.run_cli(payload, env={"OPENROUTER_API_KEY": SCRAPING_KEY})
    assert result.exit_code == 0, result.output
    assert "build_ai_service" in reached


def test_a_manual_instagram_cold_dm(igc_rig, ai_reached):
    reached, install = ai_reached
    install()
    result = igc_rig.run_cli(cold_dm_payload())
    assert result.exit_code == 0, result.output
    assert igc_rig.sent
    assert reached == [] and igc_rig.ai_calls == []


def test_control_an_instagram_cold_dm_with_ai_reaches_the_factory(igc_rig, ai_reached):
    reached, install = ai_reached
    install()
    payload = cold_dm_payload(messageMode="ai", aiPrompt="Invite them", messages=[])
    result = igc_rig.run_cli(payload, env={"OPENROUTER_API_KEY": COLD_DM_KEY})
    assert result.exit_code == 0, result.output
    # The cold DM builds its service through its own module's import of the factory's builder,
    # which the rig answers: the rig's record is the control here.
    assert igc_rig.ai_calls


def test_an_instagram_dm_read(igd_rig, ai_reached):
    reached, install = ai_reached
    install()
    result = igd_rig.run_cli("instagram.engagement.dm_read", {"limit": 2})
    assert result.exit_code == 0, result.output
    assert reached == []


def test_a_manual_tiktok_for_you(rig, page_payload, ai_reached):
    reached, install = ai_reached
    install()
    result = rig.run_cli(page_payload())
    assert result.exit_code == 0, result.output
    assert rig.workflows
    assert reached == [] and rig.ai_services == [] and rig.ai_installs == []


def test_control_a_tiktok_for_you_with_ai_reaches_the_factory(rig, page_payload, ai_reached):
    reached, install = ai_reached
    install()
    result = rig.run_cli(page_payload(ai={"enabled": True, "profileAnalysis": True}),
                         env={"OPENROUTER_API_KEY": "sk-or-control"})
    assert result.exit_code == 0, result.output
    assert rig.ai_installs


def test_a_manual_tiktok_cold_dm(rig, outreach_payload, ai_reached):
    reached, install = ai_reached
    install()
    rig.use_real_sent_dms()
    rig.use_real_outreach()
    database = rig.tmp_path / "cli_cold_dm.db"
    database.write_bytes(b"")
    rig.monkeypatch.setenv("TAKTIK_DB_PATH", str(database))
    result = rig.run_cli(outreach_payload("manual"), workflow_id="tiktok.standalone.tiktok_dm_outreach")
    assert result.exit_code == 0, result.output
    assert reached == [] and rig.ai_services == []


def test_a_tiktok_new_followers_read(rig, inbox_payload, ai_reached):
    reached, install = ai_reached
    install()
    rig.show_notifications()
    result = rig.run_cli(inbox_payload("new_followers"), workflow_id="tiktok.automation.new_followers")
    assert result.exit_code == 0, result.output
    assert reached == [] and rig.ai_services == []
