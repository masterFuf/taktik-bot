"""Le pont URL de post TikTok respecte le budget de profils envoyé en `maxVideos`.

La page URL de post envoie le budget deux fois, en `maxProfiles` et en `maxVideos` (le nom que lit
le panneau live). Le pont ne lisait que `maxProfiles` et `maxFollowers` : une charge qui ne portait
le budget qu'en `maxVideos` tournait sur le nombre de commentateurs. Relevé par le test de contrat
des configurations le 2026-09-24.
"""

from types import SimpleNamespace

import pytest

import bridges.tiktok.workflows.automation.post_url as bridge
import taktik.core.social_media.tiktok.actions.business.workflows.post_url as post_url_package
from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import FollowersStats


class _FakeWorkflow:
    built = []

    def __init__(self, device, config, device_id=None):
        self.config = config
        _FakeWorkflow.built.append(self)

    def run(self, bot_username=None):
        return FollowersStats()


@pytest.fixture
def run_bridge(monkeypatch):
    _FakeWorkflow.built = []
    manager = SimpleNamespace(device_manager=SimpleNamespace(device=object()))
    monkeypatch.setattr(bridge, "tiktok_startup", lambda device_id, fetch_profile=True: (manager, "bot"))
    monkeypatch.setattr(bridge, "install_profile_ai_hooks", lambda config, log=None: None)
    monkeypatch.setattr(bridge, "wire_single_pass_callbacks", lambda workflow, stats: None)
    monkeypatch.setattr(bridge, "send_message", lambda *a, **k: None)
    monkeypatch.setattr(bridge, "send_status", lambda *a, **k: None)
    monkeypatch.setattr(post_url_package, "PostUrlWorkflow", _FakeWorkflow)

    def _run(config):
        payload = {"deviceId": "emulator-5554", "postUrl": "https://www.tiktok.com/@a/video/1", **config}
        assert bridge.run_post_url_workflow(payload) is True
        return _FakeWorkflow.built[-1].config

    return _run


def test_a_budget_sent_as_max_videos_alone_is_the_visit_budget(run_bridge):
    config = run_bridge({"maxCommenters": 20, "maxVideos": 7})

    assert config.max_followers == 7
    assert config.max_commenters == 20


def test_the_page_payload_keeps_its_budget(run_bridge):
    # Ce que TikTokPostUrl.tsx envoie : le même nombre sous les deux noms.
    config = run_bridge({"maxCommenters": 30, "maxProfiles": 12, "maxVideos": 12})

    assert config.max_followers == 12


def test_max_profiles_wins_when_the_two_names_disagree():
    assert bridge.read_profile_budget({"maxProfiles": 5, "maxVideos": 9}, 20) == 5


def test_no_budget_at_all_falls_back_to_the_commenter_count():
    assert bridge.read_profile_budget({}, 20) == 20
    assert bridge.read_profile_budget({"maxVideos": 0}, 20) == 20
