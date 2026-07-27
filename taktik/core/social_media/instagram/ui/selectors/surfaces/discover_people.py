"""Selectors de la surface "Discover people" (suggestions de comptes).

Provenance : dumps reels device 9CHAY1PN, Instagram v410.0.0.53.71, 2026-07-26
(feed -> carousel netego "Suggested for you" -> "See all" -> modale contacts ->
liste "Discover people"). Voir aussi `POPUP_SELECTORS.contacts_access_*` pour la
modale d'acces aux contacts qui s'intercale entre les deux ecrans.

Deux familles volontairement separees :

- des XPATH pour les acces device directs (detection d'ecran, tap d'un bouton) ;
- des resource-id NUS pour le fast-path de parsing du dump XML. Une ligne de
  suggestion est un sous-arbre `recommended_user_row_content_identifier` qui
  contient DEJA son username, son bouton et son contexte social : pas besoin
  d'apparier des bounds par proximite verticale comme sur la surface
  notifications. IG rend certaines lignes avec un resource-id nu (sans prefixe
  `com.instagram.android:id/`), donc le parsing matche par SOUS-CHAINE.

Les libelles d'etat du bouton ("Follow" / "Follow back" / "Following" /
"Requested") ne sont PAS redefinis ici : ils vivent deja dans
`PROFILE_SELECTORS.follow_state_labels_*` et sont lus par
`classify_follow_state()`, source de verite unique partagee avec le header profil.
"""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class DiscoverPeopleSelectors:
    """Ecran "Discover people" : liste de comptes suggeres, un bouton par ligne."""

    # === Titre de l'ecran (langue-dependant, overlay locales/) ===
    _screen_title_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
    ])

    @property
    def screen_title(self) -> List[str]:
        return self._screen_title_base

    @property
    def screen_title_texts(self) -> List[str]:
        """Libelles bruts du titre de l'ecran (pas des xpaths) — confirmation de surface."""
        return L("discover_people.screen_title_texts")

    # === Preuve de surface : au moins une ligne de recommandation rendue ===
    # NB (regle AGENTS "preuve de surface specifique") : `row_recommended_user_username`
    # seul est trop large (il apparait aussi dans la queue "suggestions" d'une liste
    # followers). La preuve retenue est le CONTENEUR de ligne + son bouton d'action,
    # qui n'existent ensemble que sur une liste de recommandations.
    suggestion_row: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "recommended_user_row_content_identifier")]',
    ])
    suggestion_follow_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "row_recommended_user_follow_button")]',
    ])

    # === Conteneur scrollable ===
    list_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/recycler_view"]',
        '//*[@resource-id="com.instagram.android:id/refreshable_container"]',
    ])

    # === Fast-path dump XML : resource-id NUS (matches par sous-chaine) ===
    row_container_id: str = "recommended_user_row_content_identifier"
    row_username_id: str = "row_recommended_user_username"
    row_follow_button_id: str = "row_recommended_user_follow_button"
    row_social_context_id: str = "row_recommended_social_context"
    row_dismiss_id: str = "row_recommended_hide_icon_button"
    section_header_id: str = "row_header_textview"
    section_header_action_id: str = "row_header_action"

    # Lignes d'accroche en haut de l'ecran ("Connect to Facebook" / "Connect contacts").
    # Elles portent un bouton d'action mais ne sont PAS des suggestions : on ne les
    # touche jamais.
    connect_row_ids: tuple = ("facebook_button", "contacts_button")


DISCOVER_PEOPLE_SELECTORS = DiscoverPeopleSelectors()
