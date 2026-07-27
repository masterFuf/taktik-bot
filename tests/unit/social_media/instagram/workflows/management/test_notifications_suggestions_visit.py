"""Visite qualifiee des suggestions de l'ecran Notifications.

Ce que ces tests verrouillent, et pourquoi ca compte : une suggestion est un profil
INCONNU. La surface n'affiche que son libelle, jamais son @handle — il n'y a donc rien
a reconcilier en base, il faut produire la fiche. Le mode precedent tapait le bouton
"Suivre" de la ligne et enregistrait le follow sous le libelle affiche ; ces tests
interdisent son retour.

Les primitives device sont remplacees ; le sequencage teste (quoi taper, quoi refuser,
quoi passer au pipeline) est bien celui de production.
"""

import pytest

from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
    NotificationsEngagementWorkflow,
)
from taktik.core.social_media.instagram.actions.core.base_business.profile_processing import (
    ProfileProcessingResult,
)


class _FakePipeline:
    """Pipeline par-profil injecte : enregistre ce qu'on lui demande de traiter."""

    def __init__(self, username="real_handle", opens=True, status=ProfileProcessingResult.SUCCESS):
        self.username = username
        self.opens = opens
        self._status = status
        self.processed = []

    def wait_for_profile(self, timeout=8.0):
        return self.opens

    def read_username(self):
        return self.username

    def process(self, username):
        self.processed.append(username)
        outcome = ProfileProcessingResult(self._status, username)
        outcome.interaction_result = {"follows": 1 if self._status == ProfileProcessingResult.SUCCESS else 0}
        return outcome


class _Workflow(NotificationsEngagementWorkflow):
    """Workflow reel, primitives device remplacees."""

    def __init__(self, rows, pipeline=None):
        self._rows = list(rows)
        self.profile_pipeline = pipeline
        self.taps = []
        self.returns = 0
        self.scrolls = 0
        self.zone_reached = True
        import loguru
        self.logger = loguru.logger.bind(module="test")
        self._notify_cb = None

    # --- primitives remplacees ---
    def _optimize_locale(self):
        return None

    def scan_suggestions(self, root=None):
        return self._rows

    def reach_suggestions_zone(self, max_scrolls=8):
        return self.zone_reached

    def _tap_point(self, point, name):
        self.taps.append((point, name))
        return True

    def _scroll_down(self, times=1):
        self.scrolls += times

    def _return_to_notifications(self, attempts=3):
        self.returns += 1
        return True

    def ensure_notifications_screen(self):  # pragma: no cover — jamais atteint ici
        return True


def _row(label, state, row_point, follow_point):
    return {"label": label, "state": state, "state_label": state,
            "social_context": "", "row_point": row_point,
            "follow_point": follow_point, "row_top": 0}


NO_DELAY = (0, 0)


def test_the_row_body_is_tapped_and_never_the_follow_button():
    """Taper le bouton, c'est suivre sans jamais savoir QUI : c'est le mode supprime."""
    pipeline = _FakePipeline(username="spa_echo")
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert [point for point, _name in wf.taps] == [(274, 1526)]
    assert result["visited"] == 1
    assert result["processed"] == 1


def test_the_handle_read_on_the_profile_is_what_gets_processed():
    """Le libelle affiche ('Spa Ec(h)o') n'est pas une clef : seul le @handle en est une."""
    pipeline = _FakePipeline(username="spa_echo")
    wf = _Workflow([_row("Spa Ec(h)o", "follow", (274, 1526), (838, 1557))], pipeline)

    wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert pipeline.processed == ["spa_echo"]


def test_without_a_pipeline_nothing_is_tapped_at_all():
    """Sans pipeline il ne resterait que le follow a l'aveugle : on refuse, franchement."""
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline=None)

    result = wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert result["stop_reason"] == "no_pipeline"
    assert wf.taps == []
    assert result["visited"] == 0


def test_a_profile_that_does_not_open_is_an_error_not_a_silent_skip():
    """Le tap est parti mais aucune fiche n'est apparue : ne rien traiter, et le dire."""
    pipeline = _FakePipeline(opens=False)
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert pipeline.processed == []
    assert result["errors"] == 1
    assert result["visited"] == 0
    assert result["profiles"] == [{"label": "Spa Echo", "username": None, "status": "not_opened"}]


def test_an_open_profile_with_no_readable_handle_is_never_processed():
    """Sans @handle, ecrire reviendrait a inventer une clef."""
    pipeline = _FakePipeline(username=None)
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert pipeline.processed == []
    assert result["errors"] == 1
    assert result["profiles"][0]["status"] == "no_username"


def test_only_plain_follow_rows_are_visited():
    """Meme regle que partout ailleurs : ni follow-back, ni deja suivi."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([
        _row("Me suit", "follow_back", (274, 1300), (838, 1330)),
        _row("Deja suivi", "following", (274, 1500), (838, 1530)),
        _row("Inconnu", "follow", (274, 1700), (838, 1730)),
    ], pipeline)

    result = wf.visit_suggestions(max_profiles=5, max_scrolls=0, delay_range=NO_DELAY)

    assert [point for point, _name in wf.taps] == [(274, 1700)]
    assert result["skipped_follow_back"] == 1


def test_each_visit_returns_to_the_notifications_screen():
    """Rester sur le profil ferait lire la fiche courante comme la liste suivante."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)

    wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert wf.returns == 1


def test_the_zone_must_be_reachable_before_anything_is_touched():
    """Zone hors ecran = on n'est pas descendu assez bas, pas "plus de suggestions"."""
    pipeline = _FakePipeline()
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)
    wf.zone_reached = False

    result = wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert result["stop_reason"] == "zone_not_reached"
    assert wf.taps == []


def test_a_filtered_profile_counts_as_processed_not_as_a_follow():
    """Un profil ouvert, qualifie puis rejete a coute un run complet : il doit se voir."""
    pipeline = _FakePipeline(username="hors_cible",
                             status=ProfileProcessingResult.FILTERED_CRITERIA)
    wf = _Workflow([_row("Hors cible", "follow", (274, 1700), (838, 1730))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert result["processed"] == 1
    assert result["filtered"] == 1
    assert result["follows"] == 0


def test_the_removed_blind_list_mode_cannot_come_back():
    """Le follow depuis la liste n'existe plus : il suivait sous un libelle affiche."""
    assert not hasattr(NotificationsEngagementWorkflow, "follow_suggestions")


@pytest.mark.parametrize("state", ["follow_back", "following", "requested", None])
def test_no_state_other_than_follow_is_ever_opened(state):
    pipeline = _FakePipeline()
    wf = _Workflow([_row("X", state, (274, 1700), (838, 1730))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert wf.taps == []
    assert result["visited"] == 0
