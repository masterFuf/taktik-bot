"""Visite QUALIFIEE de l'ecran « Decouvrir des personnes ».

Pourquoi cet ecran en plus de la zone du bas des notifications : cette derniere est
**servie par l'algorithme**. QA device du 2026-07-27, meme compte, meme heure : une
fois « Suggestions », une fois « Followers que vous ne suivez pas », une fois rien.
Une acquisition ne peut pas reposer sur une surface qui apparait quand Instagram le
decide ; « Decouvrir des personnes » est, lui, un ecran dedie et entier.

Le sequencage n'est pas reecrit ici : il vient du service partage
``common/suggestion_visit``, exactement comme la zone Notifications. Ce module ne
possede que la navigation propre a cet ecran.

Difference notable avec la zone Notifications : ici la ligne porte un
``row_recommended_user_username``. Quand ce libelle a la forme d'un vrai @handle, on
peut savoir AVANT d'ouvrir la fiche que le profil est deja traite, et epargner la
visite ET l'appel IA. Quand il n'en a pas la forme (IG y met souvent le nom complet),
on visite : se tromper la couterait une cible, ce qui est pire que de repayer.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from ..common.suggestion_visit import SuggestionSurface, visit_suggestions
from .suggestions_parsing import followable_rows

# Un @handle Instagram : lettres, chiffres, point, underscore. Un libelle qui ne rentre
# pas dans ce moule est un nom affiche, pas une clef — on ne l'interroge pas en base.
_HANDLE_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


class DiscoverSuggestionsVisitMixin:
    """Mixin: visite qualifiee des lignes de l'ecran « Decouvrir des personnes »."""

    def open_discover_profile(self, row: Dict[str, Any], load_timeout_s: float = 8.0) -> bool:
        """Ouvrir le profil d'une ligne, et le PROUVER.

        On tape le NOM, pas le centre de la ligne : le bouton d'abonnement occupe la
        partie droite, et viser le milieu ferait un follow depuis la liste — c'est-a-dire
        exactement ce que cette visite remplace. A defaut de bounds du nom, on vise le
        premier tiers gauche de la ligne, derive de ses bounds vivantes.
        """
        bounds = row.get("name_bounds")
        if not bounds:
            row_bounds = row.get("row_bounds")
            if not row_bounds:
                self.logger.warning(f"Suggestion '{row.get('label') or '?'}': aucune geometrie a taper")
                return False
            x1, y1, x2, y2 = row_bounds
            bounds = (x1, y1, x1 + (x2 - x1) // 3, y2)

        if not self.device.human_tap(tuple(bounds)):
            self.logger.debug(f"Tap d'ouverture en echec pour '{row.get('label') or '?'}'")
            return False
        self._human_like_delay('navigation')
        return bool(self.detection_actions.wait_for_profile_screen(timeout=load_timeout_s))

    def leave_discover_profile(self, attempts: int = 6) -> bool:
        """Revenir du profil vers la liste de suggestions.

        Le pipeline a pu descendre dans les posts ou ouvrir une story : plusieurs backs
        peuvent etre necessaires. On tape la FLECHE de la barre d'action quand elle est
        la — QA du 2026-07-26 : cet ecran a deja ignore `press('back')`.
        """
        from taktik.core.social_media.instagram.ui.selectors import NAVIGATION_SELECTORS

        for _ in range(max(int(attempts), 1)):
            if self.is_on_discover_people_screen():
                return True
            if not self._tap_first_present(NAVIGATION_SELECTORS.back_buttons):
                try:
                    self.device.press('back')
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug(f"Touche back en echec: {exc}")
                    break
            self._human_like_delay('navigation')
        return self.is_on_discover_people_screen()

    def visit_discover_suggestions(self, config: Dict[str, Any],
                                   max_profiles: int = 5, max_scrolls: int = 15,
                                   delay_range: tuple = (4, 12)) -> Dict[str, Any]:
        """Visiter et qualifier les comptes de l'ecran deja ouvert.

        Chaque profil traverse le pipeline par-profil de production — le meme que
        target et hashtag — via ``_process_profile_on_screen``, que cette classe porte
        deja : il n'y a donc rien a injecter ici, contrairement au workflow
        Notifications qui n'est pas un ``BaseBusinessAction``.
        """
        return visit_suggestions(
            _DiscoverSuggestionSurface(self, config),
            max_profiles=max_profiles, max_scrolls=max_scrolls,
            delay_range=delay_range,
        )

    def run_discover_visit_pass(self, config: Dict[str, Any], max_profiles: int = 5,
                                max_carousel_scrolls: int = 12,
                                max_scrolls: int = 15,
                                delay_range: tuple = (4, 12)) -> Dict[str, Any]:
        """Passe complete : accueil -> carousel -> Decouvrir des personnes -> visites -> retour.

        Meme trajet d'entree que le follow de masse (``run_feed_suggestions_pass``) —
        il est deja eprouve, modale contacts comprise — mais ce qui se passe une fois
        sur l'ecran est la visite qualifiee et non un follow depuis la liste.

        Limite connue et assumee : l'entree passe par le carousel du feed, **lui aussi
        servi par l'algorithme**. Tant qu'une entree deterministe n'est pas cablee,
        cette passe peut rentrer bredouille — elle le dit (``stop_reason``) plutot que
        de laisser croire qu'il n'y avait personne a suivre.
        """
        result = {
            'entered': False, 'visited': 0, 'processed': 0, 'follows': 0,
            'filtered': 0, 'skipped_known': 0, 'errors': 0,
            'contacts_dialog': 'absent', 'profiles': [],
            'stop_reason': 'carousel_not_found', 'returned_to_feed': False,
        }

        try:
            if not self.nav_actions.navigate_to_home():
                result['stop_reason'] = 'home_not_reached'
                return result
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"Retour a l'accueil impossible: {exc}")
            result['stop_reason'] = 'home_not_reached'
            return result

        if not self.find_feed_suggestions_carousel(max_carousel_scrolls).get('found'):
            return result

        if not self.open_suggestions_see_all():
            result['stop_reason'] = 'cta_tap_failed'
            return result

        result['contacts_dialog'] = self.handle_contacts_access_dialog(
            config.get('suggestions_contacts_choice', 'deny')
        )
        if result['contacts_dialog'] == 'other_dialog':
            # Une autre alerte Instagram (soft-ban, mise a jour...) : on ne la traite
            # pas ici, et on ne visite surtout pas derriere.
            result['stop_reason'] = 'blocked_by_dialog'
            result['returned_to_feed'] = self._return_to_feed()
            return result

        if not self._wait_for_discover_screen():
            result['stop_reason'] = 'discover_screen_not_reached'
            result['returned_to_feed'] = self._return_to_feed()
            return result

        result['entered'] = True
        visit = self.visit_discover_suggestions(
            config, max_profiles=max_profiles, max_scrolls=max_scrolls,
            delay_range=delay_range,
        )
        result.update({k: visit[k] for k in
                       ('visited', 'processed', 'follows', 'filtered', 'skipped_known',
                        'errors', 'profiles', 'stop_reason')})
        result['returned_to_feed'] = self._return_to_feed()
        return result


class _DiscoverSuggestionSurface(SuggestionSurface):
    """Adaptateur : la navigation propre a « Decouvrir des personnes »."""

    name = "discover_people"

    # Provenance ecrite en base pour chaque profil traite par ce chemin.
    SOURCE_TYPE = "SUGGESTIONS"
    SOURCE_NAME = "discover_people"

    def __init__(self, business, config: Dict[str, Any]):
        self._biz = business
        self._config = config
        self.reach_failure_reason = "discover_screen_lost"

    def reach(self) -> bool:
        # L'ecran est deja ouvert par l'appelant ; on verifie seulement qu'on n'en est
        # pas sorti entre deux profils (un back de trop, une modale).
        return self._biz.is_on_discover_people_screen()

    def scan(self) -> List[Dict[str, Any]]:
        return self._biz.scan_discover_suggestions()

    def followable(self, rows):
        return followable_rows(rows)

    def row_key(self, row):
        return self._biz._row_key(row)

    def already_known(self, row) -> bool:
        """Le libelle designe-t-il un profil deja traite pour ce compte ?

        Seulement quand il a la forme d'un @handle : IG met souvent le nom complet dans
        ce champ, et interroger la base avec « Marie Dupont » ne repondrait rien
        d'utile. Fail-open : la moindre incertitude fait visiter.
        """
        label = (row.get("label") or "").strip().lstrip("@")
        if not label or not _HANDLE_RE.match(label):
            return False
        try:
            skippable, _reason = InstagramWorkflowStateService.is_profile_skippable(
                label, self._biz._get_account_id(),
            )
            return bool(skippable)
        except Exception as exc:  # noqa: BLE001 — jamais fatal
            self._biz.logger.debug(f"Lecture 'deja traite' impossible pour @{label}: {exc}")
            return False

    def open_profile(self, row) -> bool:
        return self._biz.open_discover_profile(row)

    def read_username(self) -> Optional[str]:
        return self._biz.detection_actions.get_username_from_profile()

    def process(self, username: str):
        return self._biz._process_profile_on_screen(
            username, self._config,
            source_type=self.SOURCE_TYPE, source_name=self.SOURCE_NAME,
            account_id=self._biz._get_account_id(),
            session_id=self._biz._get_session_id(),
        )

    def leave(self) -> bool:
        return self._biz.leave_discover_profile()

    def scroll(self) -> None:
        self._biz.scroll_discover_suggestions()

    def log_info(self, message: str) -> None:
        self._biz.logger.info(f"Discover {message}")

    def log_warning(self, message: str) -> None:
        self._biz.logger.warning(f"Discover {message}")


__all__ = ["DiscoverSuggestionsVisitMixin"]
