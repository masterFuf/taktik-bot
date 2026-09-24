"""L'unfollow TikTok garde les comptes suivis depuis moins que l'« Âge min. (jours) » du nœud.

Le nœud `tiktok-unfollow` du planificateur propose « Âge min. (jours) » (`minFollowAge`, 3 par
défaut). Le runner ne le transmettait pas et le bot n'en faisait rien : un compte suivi la veille
par le bot pouvait être retiré avant d'avoir eu le temps de suivre en retour. Relevé par le test de
contrat des configurations le 2026-09-24.

L'âge vient des interactions FOLLOW du bot (`TikTokFollowGraphService.get_days_since_follow`,
le même mécanisme que la synchro des listes). Seul un follow récent CONNU retient un compte : sans
handle sur la ligne, sans compte actif ou sans trace de follow, le run fait ce qu'il faisait avant.
"""

from types import SimpleNamespace

import pytest

import taktik.core.database.local.service as db_service
import taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow as workflow_module
from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.models import (
    UnfollowConfig,
    UnfollowStats,
)
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.payload import (
    unfollow_config_from_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow import UnfollowWorkflow
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS


class _Row:
    """Une ligne de la liste Abonnements : le bouton « Following » et le handle à côté."""

    def __init__(self, username):
        self.username = username
        self.text = "Following"
        self.bounds = (0, 100, 50, 150)
        self.clicked = False

    def click(self):
        self.clicked = True


class _Device:
    """La liste ne montre ses lignes qu'une fois, puis plus rien : le run s'arrête."""

    def __init__(self, rows):
        self._rows = rows
        self._shown = False

    def xpath(self, selector):
        device = self

        class _Query:
            def all(self):
                if device._shown:
                    return []
                device._shown = True
                return list(device._rows)

        return _Query()


@pytest.fixture
def follow_ages(monkeypatch):
    """Âge (jours) du follow, par handle ; None = aucune trace. Le compte actif a l'id 7."""
    ages = {}
    looked_up = []

    def _days(username, account_id):
        looked_up.append((username, account_id))
        return ages.get(username)

    monkeypatch.setattr(TikTokFollowGraphService, "get_days_since_follow", staticmethod(_days))
    monkeypatch.setattr(
        db_service,
        "get_local_database",
        lambda: SimpleNamespace(get_or_create_tiktok_account=lambda username: (7, False)),
    )
    monkeypatch.setattr(workflow_module.time, "sleep", lambda seconds: None)
    ages["_looked_up"] = looked_up
    return ages


def _run(rows, **config):
    workflow = UnfollowWorkflow.__new__(UnfollowWorkflow)
    workflow.device = _Device(rows)
    workflow.config = UnfollowConfig(max_scroll_attempts=1, min_delay=0, max_delay=0, **config)
    workflow.stats = UnfollowStats()
    workflow.stopped = False
    workflow._account_id = None
    workflow._account_resolved = False
    workflow._selectors = FOLLOWERS_SELECTORS
    workflow._nav = SimpleNamespace(navigate_to_profile=lambda: True)
    workflow._scroll = SimpleNamespace(scroll_profile_videos=lambda direction: None)
    workflow._base = SimpleNamespace(
        _find_and_click=lambda *a, **k: True,
        _human_tap_bounds=lambda elem: elem.click() or True,
    )
    workflow._resolve_username = lambda elem: elem.username
    skipped = []
    workflow._on_unfollow = None
    workflow._on_stats = None
    workflow._on_skip = lambda username, reason="friends": skipped.append((username, reason))
    workflow.run()
    return workflow, skipped


def test_an_account_followed_too_recently_is_kept(follow_ages):
    follow_ages.update({"fresh": 1, "old": 10})
    rows = [_Row("fresh"), _Row("old")]

    workflow, skipped = _run(rows, min_follow_age_days=3, bot_username="moncompte")

    assert [row.username for row in rows if row.clicked] == ["old"]
    assert skipped == [("fresh", "followed_too_recently")]
    assert workflow.stats.skipped_recent_follows == 1
    assert workflow.stats.unfollowed == 1
    assert ("fresh", 7) in follow_ages["_looked_up"]


def test_an_account_without_a_known_follow_date_is_not_held_back(follow_ages):
    rows = [_Row("followed_by_hand")]

    workflow, skipped = _run(rows, min_follow_age_days=3, bot_username="moncompte")

    assert rows[0].clicked
    assert skipped == []


def test_no_minimum_age_means_no_lookup(follow_ages):
    follow_ages.update({"fresh": 0})
    rows = [_Row("fresh")]

    _run(rows, min_follow_age_days=0, bot_username="moncompte")

    assert rows[0].clicked
    assert follow_ages["_looked_up"] == []


def test_without_the_acting_account_the_age_rule_cannot_apply(follow_ages):
    follow_ages.update({"fresh": 0})
    rows = [_Row("fresh")]

    _run(rows, min_follow_age_days=3, bot_username=None)

    assert rows[0].clicked
    assert follow_ages["_looked_up"] == []


def test_the_scheduler_payload_carries_the_minimum_age():
    # Ce que le runner du planificateur envoie depuis le 2026-09-24.
    config = unfollow_config_from_payload({"max_unfollows": 50, "min_follow_age": 3, "delay_min": 3})

    assert config.min_follow_age_days == 3


def test_the_page_payload_has_no_minimum_age():
    config = unfollow_config_from_payload({"max_unfollows": 50, "delay_min": 3, "delay_max": 8})

    assert config.min_follow_age_days == 0
