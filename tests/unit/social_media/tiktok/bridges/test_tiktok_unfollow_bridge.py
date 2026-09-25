"""Le pont d'unfollow TikTok lit la pause que la page et le planificateur envoient.

La page et le nœud envoient `config.delay_min` / `config.delay_max`, comme le reste de leur charge
(`max_unfollows`, `skip_friends`). Le pont lisait `minDelay` / `maxDelay`, que personne n'envoie :
chaque run attendait 1 à 3 s entre deux unfollows, quoi que l'opérateur ait réglé. Relevé par le
test de contrat des configurations le 2026-09-24.
"""

from types import SimpleNamespace

import pytest

import bridges.tiktok.automation.runtime.unfollow as bridge
import taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow as workflow_module
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow import UnfollowStats
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.payload import (
    unfollow_config_from_payload,
)


class _FakeWorkflow:
    built = []

    def __init__(self, device, config):
        self.config = config
        _FakeWorkflow.built.append(self)

    def set_on_unfollow_callback(self, cb):
        pass

    def set_on_skip_callback(self, cb):
        pass

    def set_on_unconfirmed_callback(self, cb):
        pass

    def set_on_stats_callback(self, cb):
        pass

    def run(self):
        return UnfollowStats()


@pytest.fixture
def run_bridge(monkeypatch):
    _FakeWorkflow.built = []
    manager = SimpleNamespace(device_manager=SimpleNamespace(device=object()))
    monkeypatch.setattr(bridge, "tiktok_startup", lambda device_id, fetch_profile=True: (manager, None))
    monkeypatch.setattr(workflow_module, "UnfollowWorkflow", _FakeWorkflow)
    monkeypatch.setattr(bridge, "send_message", lambda *a, **k: None)
    monkeypatch.setattr(bridge, "send_status", lambda *a, **k: None)

    def _run(config):
        assert bridge.run_unfollow_workflow({"deviceId": "emulator-5554", **config}) is True
        return _FakeWorkflow.built[-1].config

    return _run


def test_the_page_payload_sets_the_pause_between_unfollows(run_bridge):
    # Exactement ce que TikTokUnfollow.tsx envoie.
    config = run_bridge({
        "max_unfollows": 12,
        "delay_min": 7,
        "delay_max": 15,
        "sort_order": "default",
        "filter_type": "following_only",
        "skip_friends": True,
    })

    assert (config.min_delay, config.max_delay) == (7.0, 15.0)
    assert config.max_unfollows == 12
    assert config.include_friends is False


def test_skip_friends_off_keeps_friends_in_the_run(run_bridge):
    config = run_bridge({"max_unfollows": 5, "delay_min": 3, "delay_max": 8, "skip_friends": False})

    assert config.include_friends is True


def test_the_legacy_camel_case_pause_is_still_accepted():
    config = unfollow_config_from_payload({"minDelay": 2, "maxDelay": 4})

    assert (config.min_delay, config.max_delay) == (2.0, 4.0)


def test_the_wire_form_wins_over_a_legacy_name_carried_alongside():
    config = unfollow_config_from_payload({"delay_min": 9, "minDelay": 2, "delay_max": 12, "maxDelay": 4})

    assert (config.min_delay, config.max_delay) == (9.0, 12.0)


def test_nothing_sent_keeps_the_historical_defaults():
    config = unfollow_config_from_payload({})

    assert (config.min_delay, config.max_delay) == (1.0, 3.0)
    assert config.max_unfollows == 20
    assert config.include_friends is False


def test_a_negative_or_unreadable_pause_does_not_break_the_run():
    config = unfollow_config_from_payload({"delay_min": -3, "delay_max": "abc"})

    assert (config.min_delay, config.max_delay) == (0.0, 3.0)
