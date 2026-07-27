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
        self.refreshes = 0
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

    def refresh_notifications_screen(self):
        self.refreshes += 1
        return True

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
    """Sans zone, rien n'est touche — et le motif d'arret dit LAQUELLE des trois
    issues on a rencontree, parce qu'elles n'appellent pas la meme reaction."""
    pipeline = _FakePipeline()
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)
    wf.zone_reached = False
    wf.descent_outcome = "no_suggestions_offered"

    result = wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert result["stop_reason"] == "no_suggestions_offered"
    assert wf.taps == []


def test_the_list_is_collapsed_before_the_first_descent():
    """Le scan a deplie la liste a coups de « Voir plus » : chaque appui a insere une
    page de notifications entre nous et la section. Sortir/rentrer la replie."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)

    wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert wf.refreshes == 1


def test_the_collapse_can_be_skipped_for_an_isolated_probe():
    """Depuis le Lab on teste la zone sur l'ecran ou l'operateur s'est place."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)

    wf.visit_suggestions(max_profiles=1, refresh_first=False, delay_range=NO_DELAY)

    assert wf.refreshes == 0


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


# ---------------------------------------------------------------------------
# La descente vers la zone (QA device 2026-07-27).
#
# La zone vit au fond de l'ecran d'activite, et sa distance depend du COMPTE : un
# compte tres actif aligne des dizaines d'ecrans avant elle. Un budget fixe de scrolls
# s'est arrete en plein milieu de la liste et la passe est repartie sans rien faire,
# alors que la zone existait plus bas.
# ---------------------------------------------------------------------------

from lxml import etree

from taktik.core.social_media.instagram.ui.selectors import NOTIFICATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


def _screen_xml(marker, with_header=False):
    """Un ecran de notifications ; ``marker`` le rend different du precedent."""
    header = ('<node class="android.widget.TextView" resource-id="activity_feed_header_row"'
              ' text="Suggestions" bounds="[44,1498][306,1551]"/>') if with_header else ""
    return etree.fromstring(
        ("<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
         f'<node class="android.widget.TextView" text="notification {marker}"'
         f' bounds="[253,300][893,460]"/>' + header + "</hierarchy>").encode("utf-8")
    )


class _Descent(_Workflow):
    """Workflow reel, dont seul le defilement est simule."""

    def __init__(self, screens):
        super().__init__(rows=[], pipeline=None)
        self._screens = list(screens)
        self.selectors = NOTIFICATION_SELECTORS
        self.show_more_taps = 0

    def reach_suggestions_zone(self, max_scrolls=60):  # on teste la VRAIE methode
        return NotificationsEngagementWorkflow.reach_suggestions_zone(self, max_scrolls)

    def _dump_root(self):
        return self._screens[min(self.scrolls, len(self._screens) - 1)]

    def _tap_show_more(self):  # pragma: no cover — doit rester non appele
        self.show_more_taps += 1
        return True


@pytest.fixture(autouse=True)
def _french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def test_the_descent_goes_far_past_the_old_fixed_budget():
    """Trente ecrans avant la zone : un compteur de 8 s'arretait a mi-liste."""
    screens = [_screen_xml(i) for i in range(30)] + [_screen_xml(30, with_header=True)]
    wf = _Descent(screens)

    assert wf.reach_suggestions_zone() is True
    assert wf.scrolls == 30


def test_the_descent_stops_when_the_list_stops_moving():
    """Deux ecrans identiques = fond de liste. Insister ne changerait rien."""
    screens = [_screen_xml(0), _screen_xml(1)] + [_screen_xml(1)] * 20
    wf = _Descent(screens)

    assert wf.reach_suggestions_zone() is False
    # Un seul ecran identique ne prouve rien (un rendu en cours y ressemble) ;
    # on s'arrete au second, pas apres avoir epuise le garde-fou.
    assert wf.scrolls == 3


def test_the_descent_never_taps_show_more():
    """« Voir plus » charge des notifications PLUS ANCIENNES : elles s'inserent
    entre nous et la zone, donc le taper nous en eloigne."""
    wf = _Descent([_screen_xml(0), _screen_xml(1), _screen_xml(1), _screen_xml(1)])

    wf.reach_suggestions_zone()

    assert wf.show_more_taps == 0


def test_the_safety_cap_is_a_guard_rail_not_a_stop_policy():
    """Si l'ecran change encore au plafond, on le dit — on ne pretend pas etre au fond."""
    wf = _Descent([_screen_xml(i) for i in range(50)])

    assert wf.reach_suggestions_zone(max_scrolls=5) is False
    assert wf.scrolls == 6


def _people_section_xml(marker, header):
    """Le bas de l'ecran : une section de PERSONNES qui n'est pas les suggestions.

    Instagram sert a cet endroit une section dont l'identite VARIE — "Suggestions"
    une fois, "Followers que vous ne suivez pas" une autre (dump 19:55), rien
    parfois. Les confondre avec une panne de navigation ferait chercher un bug la ou
    il n'y en a pas.
    """
    return etree.fromstring(
        ("<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
         f'<node class="android.widget.TextView" text="notification {marker}"'
         f' bounds="[253,300][893,460]"/>'
         f'<node class="android.widget.TextView" resource-id="activity_feed_header_row"'
         f' text="{header}" bounds="[44,949][737,1002]"/>'
         "</hierarchy>").encode("utf-8")
    )


def test_a_bottom_without_suggestions_is_reported_as_such_not_as_a_failure():
    other = "Followers que vous ne suivez pas"
    wf = _Descent([_people_section_xml(0, other)] + [_people_section_xml(1, other)] * 5)

    assert wf.reach_suggestions_zone() is False
    assert wf.descent_outcome == "no_suggestions_offered"


def test_hitting_the_guard_rail_is_not_reported_as_an_absent_section():
    """La liste bougeait encore : on ne sait PAS si la zone existait plus bas."""
    wf = _Descent([_screen_xml(i) for i in range(50)])

    assert wf.reach_suggestions_zone(max_scrolls=5) is False
    assert wf.descent_outcome == "cap_hit"


def test_reaching_the_zone_is_reported_as_reached():
    wf = _Descent([_screen_xml(0), _screen_xml(1, with_header=True)])

    assert wf.reach_suggestions_zone() is True
    assert wf.descent_outcome == "reached"
