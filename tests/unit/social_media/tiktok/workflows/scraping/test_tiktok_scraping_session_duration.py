"""Le scraping TikTok s'arrête à la durée max. de session que la page et le nœud envoient.

La page Scraping TikTok et le nœud du planificateur proposent « durée max. de la session »
(`sessionDurationMinutes`). L'app ne la recopiait pas vers le pont, et le bot ne lisait aucune
durée : un run allait jusqu'au bout de son budget de profils ou de sa source. Relevé par le test de
contrat des configurations le 2026-09-24.

L'échéance répond à la question que chaque boucle du workflow pose déjà (`stopped`) : le run
s'arrête là où un stop l'arrêterait, avant le profil, le défilement ou la vidéo suivants. Le motif
est `max_duration_reached` (code partagé `duration_cap`) ; la session est rangée COMPLETED, pas
STOPPED : le run a fait le temps qu'on lui donnait.
"""

from types import SimpleNamespace

import pytest

import bridges.tiktok.scraping.runtime.workflow as bridge
import taktik.core.social_media.tiktok.actions.atomic.navigation.navigation_actions as navigation_module
import taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow as workflow_module
from bridges.tiktok.scraping.runtime.config import build_scraping_config
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.models import ScrapingConfig
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow import ScrapingWorkflow


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(workflow_module.time, "monotonic", fake)
    return fake


def _workflow(clock, minutes, seconds_per_post=600):
    """Un scraping d'URL de post dont chaque post coûte `seconds_per_post` à l'horloge."""
    config = ScrapingConfig(
        scrape_type="post_url",
        post_urls=["https://t/1", "https://t/2", "https://t/3"],
        max_profiles=100,
        session_duration_minutes=minutes,
    )
    workflow = ScrapingWorkflow(object(), object(), config)
    workflow.opened = []

    def _scrape(url, remaining):
        workflow.opened.append(url)
        clock.now += seconds_per_post
        return [{"username": url.rsplit("/", 1)[-1]}]

    workflow._scrape_post_commenters = _scrape
    return workflow


def test_the_page_payload_reaches_the_workflow_config():
    # Ce que TikTokScraping.tsx envoie, recopié par buildScrapingPayload.
    config = build_scraping_config({"type": "hashtag", "hashtag": "cuisine", "sessionDurationMinutes": 30})

    assert config.session_duration_minutes == 30


def test_no_duration_sent_means_no_limit():
    assert build_scraping_config({"type": "hashtag", "hashtag": "cuisine"}).session_duration_minutes == 0


def test_the_run_stops_at_the_deadline_between_two_posts(clock):
    # 15 minutes : le 1er post finit à 10 min, l'échéance tombe pendant le 2e, le 3e n'est pas ouvert.
    workflow = _workflow(clock, minutes=15)

    profiles = workflow.run()

    assert workflow.opened == ["https://t/1", "https://t/2"]
    assert len(profiles) == 2
    assert workflow.completion_reason == "max_duration_reached"


def test_without_a_duration_the_run_goes_to_the_end_of_its_source(clock):
    workflow = _workflow(clock, minutes=0)

    workflow.run()

    assert len(workflow.opened) == 3
    assert workflow.completion_reason == "completed"


def test_a_manual_stop_keeps_its_own_reason(clock):
    workflow = _workflow(clock, minutes=15)
    workflow.stop()

    workflow.run()

    assert workflow.opened == []
    assert workflow.completion_reason == "stopped_by_user"


# --- le pont : la session et le dernier statut -------------------------------------------------


class _FakeScrapingWorkflow:
    reason = "max_duration_reached"

    def __init__(self, device, navigation, config):
        self.config = config
        self.completion_reason = None
        self.stopped = False

    def set_on_status_callback(self, cb):
        pass

    def set_on_progress_callback(self, cb):
        pass

    def set_on_profile_callback(self, cb):
        pass

    def set_on_error_callback(self, cb):
        pass

    def set_on_save_profile_callback(self, cb):
        pass

    def run(self):
        self.completion_reason = _FakeScrapingWorkflow.reason
        self.stopped = True  # l'échéance répond « arrêté », comme le vrai workflow
        return [{"username": "a"}, {"username": "b"}]


@pytest.fixture
def run_bridge(monkeypatch):
    calls = {"session": [], "status": []}
    manager = SimpleNamespace(device_manager=SimpleNamespace(device=object()))
    monkeypatch.setattr(bridge, "tiktok_startup", lambda device_id, fetch_profile=True: (manager, None))
    monkeypatch.setattr(navigation_module, "NavigationActions", lambda device: object())
    monkeypatch.setattr(workflow_module, "ScrapingWorkflow", _FakeScrapingWorkflow)
    monkeypatch.setattr(bridge, "create_scraping_session", lambda config: 42)
    monkeypatch.setattr(bridge, "update_scraping_session", lambda *args: calls["session"].append(args))
    monkeypatch.setattr(bridge, "send_status", lambda status, message: calls["status"].append((status, message)))
    monkeypatch.setattr(bridge, "send_scraping_completed", lambda total: None)

    def _run(reason):
        _FakeScrapingWorkflow.reason = reason
        payload = {"deviceId": "emulator-5554", "type": "hashtag", "hashtag": "cuisine",
                   "sessionDurationMinutes": 20, "saveToDb": True}
        assert bridge.run_scraping_workflow(payload) is True
        return calls

    return _run


def test_a_spent_session_budget_files_a_completed_session_and_says_why(run_bridge):
    calls = run_bridge("max_duration_reached")

    assert calls["session"][-1][2] == "COMPLETED"
    assert calls["status"][-1] == (
        "completed", "Maximum session duration reached (20 minutes): scraped 2 profiles"
    )


def test_a_manual_stop_still_files_a_stopped_session(run_bridge):
    calls = run_bridge("stopped_by_user")

    assert calls["session"][-1][2] == "STOPPED"
