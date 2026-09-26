"""A refused publication is filed in the account's health history, on both platforms.

The publish bridges were the only runs that never knew the operated account: a refusal stopped
the publication but left no `action_blocked` entry, so the account did not rest after it. The app
now names the account in the payload (`botUsername`, the key the other config bridges read) and
the core installs the run's witness with it, as every other run does.
"""

from types import SimpleNamespace

from taktik.core.database import account_health
from taktik.core.shared.diagnostics import run_halt


def _filed(monkeypatch):
    filed = []
    monkeypatch.setattr(account_health, "record_action_block",
                        lambda halt, **kw: filed.append((kw["platform"], kw["account_username"],
                                                         halt["code"], kw["source_type"])))
    return filed


def test_an_instagram_refusal_is_filed_under_the_account_the_app_names(monkeypatch):
    from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow

    filed = _filed(monkeypatch)
    monkeypatch.setattr(InstagramPostWorkflow, "_build_actions", lambda self, device: {})
    workflow = InstagramPostWorkflow(object(), "device-1", package_name="com.instagram.android",
                                     account_username="@my_account")

    workflow.execute(media_paths=[])
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page (words)")

    assert filed == [("instagram", "my_account", "action_blocked", "PUBLISH")]


def test_a_tiktok_refusal_is_filed_under_the_account_the_app_names(monkeypatch):
    from taktik.core.social_media.tiktok.workflows.publish import agent_handler

    filed = _filed(monkeypatch)
    monkeypatch.setattr(agent_handler, "_patch_clone_selectors", lambda *a, **k: None)

    class _Upload:
        def __init__(self, *a, **k):
            pass

        def execute(self, **kwargs):
            run_halt.demander_arret(run_halt.ACTION_BLOCKED, "tiktok (Too many requests)")
            return {"success": False, "message": "refused", "error_type": "action_blocked"}

    agent_handler.run_tiktok_publish(
        {"deviceId": "device-1", "localPath": "C:/media/clip.mp4", "botUsername": "@my_account"},
        device=SimpleNamespace(), device_id="device-1", workflow_factory=_Upload,
    )

    assert filed == [("tiktok", "my_account", "action_blocked", "PUBLISH")]
