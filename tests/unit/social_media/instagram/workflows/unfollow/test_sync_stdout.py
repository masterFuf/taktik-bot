"""What the follow-list syncs write on stdout is what the app reads.

An enriched sync printed a `sync_user_enriched` line after each profile, with four counts the
extraction had just sent in its own `profile_captured`; the standalone non-followers step printed
a `scrape_non_followers_complete` the desktop can never receive. No reader for either.
"""

import json
from types import SimpleNamespace

import pytest

from fake_follow_list import FakeFacade, FakeScreen, follow_list_xml, unified_tabs
from taktik.core.social_media.instagram.actions.business.management.profile import extraction
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import (
    sync_followers as followers_mixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.core.config_builder import build_instagram_automation_config
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner


@pytest.fixture(autouse=True)
def _french_and_fast(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "following_tab_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "list_load_timeout", 0.0)
    yield
    set_active_locale(None)


def _json_types(out: str):
    return [json.loads(line)["type"] for line in out.splitlines() if line.startswith("{")]


def test_an_enriched_profile_is_reported_by_the_extraction_alone(monkeypatch, capsys):
    extractions = []

    class _Extraction:
        def __init__(self, device, session_manager=None):
            pass

        def get_complete_profile_info(self, username=None, **kwargs):
            extractions.append((username, kwargs))
            return {"username": username, "followers_count": 10, "following_count": 5, "posts_count": 3}

    monkeypatch.setattr(extraction, "ProfileExtraction", _Extraction)
    monkeypatch.setattr(followers_mixin, "tap_element_human", lambda *a, **k: True)
    graph = followers_mixin.InstagramFollowGraphService
    monkeypatch.setattr(graph, "get_active_following_usernames", staticmethod(lambda _a: set()))
    monkeypatch.setattr(graph, "upsert_follower", staticmethod(lambda username, **_k: "new"))
    monkeypatch.setattr(graph, "set_followings_reciprocity", staticmethod(lambda _a, names: len(names)))

    titles = ("2 followers", "4 suivi(e)s", "0 abonnements", "À vérifier")
    page = follow_list_xml([("f1", "Suivi(e)"), ("f2", "Suivre en retour")],
                           extra=unified_tabs(selected=0, titles=titles))
    business = UnfollowBusiness(FakeFacade(FakeScreen(page)))
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_followers_list = lambda: True
    business._scroll_followers_list = lambda: True

    stats = business.sync_followers_list({"mode": "enriched"})

    assert stats["success"] is True
    assert [username for username, _kw in extractions] == ["f1", "f2"]
    # The extraction saves the profile and emits `profile_captured`: nothing may switch that off.
    assert all(kw.get("emit_ipc", True) and kw.get("save_to_db", True) for _u, kw in extractions)
    types = _json_types(capsys.readouterr().out)
    assert types.count("sync_user_discovered") == 2
    assert "sync_user_enriched" not in types


def test_the_desktop_cannot_ask_for_the_standalone_non_followers_step():
    with pytest.raises(ValueError):
        build_instagram_automation_config({"workflowType": "scrape_non_followers"})


def test_the_standalone_non_followers_step_writes_no_event(monkeypatch, capsys):
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.automation = SimpleNamespace()
    runner.logger = unfollow_workflow.logger
    business = SimpleNamespace(scrape_non_followers_category=lambda: {
        "non_followers_count": 3, "mutuals_count": 1, "success": True})
    monkeypatch.setattr(runner, "_get_unfollow_business", lambda: business, raising=False)

    assert runner._run_scrape_non_followers_workflow({"type": "scrape_non_followers"}) is True
    assert _json_types(capsys.readouterr().out) == []
