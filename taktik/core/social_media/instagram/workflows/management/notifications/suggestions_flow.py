"""La zone "Suggestions" en bas de l'ecran Notifications, de bout en bout.

Ce que fait ce flux, et pourquoi il ne ressemble pas au follow de masse du feed :

    descendre jusqu'a la zone -> ouvrir LE PROFIL de la suggestion -> lui appliquer
    le pipeline par-profil de production (extraction, qualification IA, persistance,
    follow) -> revenir aux notifications -> redescendre -> suivante.

La visite n'est pas un confort. Ces surfaces (feed netego, zone suggestions) n'exposent
que le LIBELLE affiche, jamais le @handle. Sur les notifications ordinaires ce n'etait
pas genant : on recoit une notification de quelqu'un avec qui on a deja interagi, donc
le profil est deja en base et le nom suffit a le retrouver. Une suggestion, elle, est un
profil INCONNU : il n'y a rien a reconcilier, il faut produire la fiche. D'ou la visite,
et d'ou le fait que ce mode ait le cout d'un run target et non d'un scan.

Le pipeline par-profil n'est PAS reimplemente ici : il est injecte
(``profile_pipeline``, cf. ``profile_pipeline.py``) et c'est exactement celui que
traversent target et hashtag. Ce module ne possede que la navigation propre a cette
surface et le sequencage de la boucle.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ....actions.business.workflows.common.suggestion_visit import (
    SuggestionSurface,
    visit_suggestions,
)
from .suggestions_parsing import (
    find_suggestions_header_y,
    followable_suggestions,
    iter_text_nodes,
    parse_notification_suggestions,
)


class NotificationSuggestionsMixin:
    """Mixin: lecture de la zone suggestions et visite qualifiee de ses profils."""

    # Deux dumps d'affilee sans AUCUNE ligne signent la fin de la liste. Un seul ne
    # prouve rien : un rendu en cours donne le meme resultat qu'une liste finie.
    _SUGGESTIONS_EMPTY_DUMP_RUNS = 2

    # Pourquoi la derniere descente s'est arretee : 'reached' | 'no_suggestions_offered'
    # | 'cap_hit'. Renseigne par reach_suggestions_zone, lu par visit_suggestions pour
    # que le motif d'arret remonte tel quel jusqu'au front.
    descent_outcome = "reached"

    # ------------------------------------------------------------------
    # Geometrie vivante de l'ecran
    # ------------------------------------------------------------------
    def _screen_height(self) -> int:
        """Hauteur d'ecran vivante — le pas entre deux lignes en depend."""
        try:
            return int(self.device.info.get("displayHeight", 2400))
        except Exception:
            return 2400

    def _screen_width(self) -> int:
        try:
            return int(self.device.info.get("displayWidth", 1080))
        except Exception:
            return 1080

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def scan_suggestions(self, root=None) -> List[Dict[str, Any]]:
        """Lignes de suggestion visibles en bas de l'ecran, avec leur etat."""
        from ....actions.atomic.interaction.profile_interaction import classify_follow_state
        from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS

        root = root if root is not None else self._dump_root()
        return parse_notification_suggestions(
            root,
            self.selectors.suggestions_header_texts,
            PROFILE_SELECTORS,
            classify_follow_state,
            screen_height=self._screen_height(),
            screen_width=self._screen_width(),
            header_resource_id=self.selectors.notification_section_header_resource_id,
            row_resource_id=self.selectors.suggestion_row_resource_id,
            button_resource_id=self.selectors.suggestion_button_resource_id,
        )

    @staticmethod
    def _row_key(row: Dict[str, Any]) -> str:
        """Clef de deduplication d'une ligne entre deux dumps.

        Le libelle suffit dans l'immense majorite des cas. Sans lui, on retombe sur la
        bande verticale de la ligne : imparfait apres un scroll, mais infiniment mieux
        que la chaine vide, qui ferait passer TOUTES les lignes sans libelle pour la
        meme — donc une seule tentee, les autres ignorees en silence.
        """
        label = (row.get("label") or "").strip()
        if label:
            return label.lower()
        top = row.get("row_top")
        return f"row@{int(top) // 50}" if top is not None else "row@?"

    def _report_unreadable_rows(self, rows: List[Dict[str, Any]]) -> None:
        """Dire, une fois, qu'on n'a pas su lire des boutons.

        Un libelle de bouton illisible est un TROU DE LOCALE, pas une ligne sans
        interet — et un ecran entier d'illisibles ressemble exactement a un ecran sans
        suggestions. Se taire ici, c'est transformer une panne en "rien a faire".
        """
        unreadable = [row for row in rows if row.get("state") is None]
        if not unreadable or getattr(self, "_reported_unreadable_suggestions", False):
            return
        self._reported_unreadable_suggestions = True
        samples = ", ".join(repr(row.get("state_label", "")) for row in unreadable[:3])
        self.logger.warning(f"{len(unreadable)} suggestion row(s) unreadable "
                            f"(locale gap?): {samples}")

    # ------------------------------------------------------------------
    # Navigation propre a la zone
    # ------------------------------------------------------------------
    def _feed_signature(self, root) -> str:
        """Empreinte de ce qui est affiche, pour savoir si la liste a AVANCE.

        Deux dumps identiques = la liste ne bouge plus : soit on est au fond, soit le
        geste n'a pas pris. Dans les deux cas insister ne sert a rien.
        """
        if root is None:
            return ""
        return "|".join(f"{text}@{bounds[1]}" for _node, text, bounds in iter_text_nodes(root))

    def refresh_notifications_screen(self) -> bool:
        """Ressortir puis rouvrir l'ecran d'activite, pour REPLIER la liste.

        Ce que montre le dump du 2026-07-27 19:55 : a l'ouverture, l'ecran tient en
        deux blocs — les notifications du jour, un bouton « Voir plus », puis la
        section de personnes. Celle-ci est donc a UN ou DEUX ecrans du haut.

        Mais le scan qui precede tape « Voir plus » a chaque fois qu'il ne trouve plus
        rien de neuf, pour lire l'historique : chaque appui insere une page de
        notifications ENTRE nous et la section, et c'est ce qui transformait la
        descente en dizaines de scrolls. Sortir et rentrer replie la liste, et rend a
        la section sa distance d'origine.
        """
        for _ in range(3):
            if not self._on_notifications_screen():
                break
            try:
                self.device.press("back")
            except Exception as exc:  # noqa: BLE001
                self.logger.debug(f"back before re-entering notifications failed: {exc}")
                break
            time.sleep(1.0)
        if self._tap_activity_and_check():
            return True
        return self.ensure_notifications_screen()

    def reach_suggestions_zone(self, max_scrolls: int = 60) -> bool:
        """Descendre jusqu'a ce que l'en-tete "Suggestions" soit a l'ecran.

        La zone vit tout en bas de l'ecran Notifications. **Sa distance depend du
        compte, pas de nous** : un compte tres actif aligne des dizaines d'ecrans de
        notifications avant elle. Un budget fixe de scrolls est donc le mauvais
        critere — QA device du 2026-07-27 : huit scrolls sur un compte charge se sont
        arretes en plein milieu de la liste et la passe est repartie sans rien faire,
        alors que la zone existait bel et bien plus bas.

        On s'arrete donc sur la PROGRESSION : tant que l'ecran change, on continue ;
        deux ecrans identiques d'affilee signent le fond de liste. ``max_scrolls``
        n'est plus qu'un garde-fou anti-boucle, pas une politique d'arret.

        On ne tape jamais "Voir plus" ici : ce bouton charge des notifications PLUS
        ANCIENNES, qui s'inserent entre nous et la zone — on s'en eloignerait.

        En sortie, ``descent_outcome`` dit POURQUOI on s'est arrete. Les trois issues
        n'ont pas du tout le meme sens et les confondre a deja coute une QA :
        'reached', 'no_suggestions_offered' (fond de liste atteint — la section de
        personnes qu'Instagram sert a cet instant n'est pas celle des suggestions) et
        'cap_hit' (garde-fou touche alors que la liste bougeait encore).
        """
        from .dump_parsing import parse_section_headers

        previous = None
        stale = 0
        seen_sections: List[str] = []
        for index in range(max(int(max_scrolls), 0) + 1):
            root = self._dump_root()
            if find_suggestions_header_y(
                root, self.selectors.suggestions_header_texts,
                self.selectors.notification_section_header_resource_id,
            ) is not None:
                self.descent_outcome = "reached"
                self.logger.info(f"Suggestions zone reached after {index} scroll(s)")
                return True
            for header in parse_section_headers(
                root, self.selectors.notification_section_header_resource_id
            ):
                if header not in seen_sections:
                    seen_sections.append(header)
            signature = self._feed_signature(root)
            stale = stale + 1 if signature and signature == previous else 0
            if stale >= 2:
                self.descent_outcome = "no_suggestions_offered"
                # Nommer les sections traversees : Instagram sert au bas de cet ecran une
                # section de personnes dont l'identite VARIE ("Suggestions" une fois,
                # "Followers que vous ne suivez pas" une autre, rien parfois). Sans ces
                # noms dans les logs, "pas de suggestions" est indiscernable d'une panne.
                sections = ", ".join(repr(s) for s in seen_sections[-4:]) or "aucune"
                self.logger.info(
                    f"Bottom of the notifications list reached after {index} scroll(s): "
                    f"Instagram is not serving a suggestions section right now "
                    f"(sections seen: {sections})"
                )
                return False
            previous = signature
            self._scroll_down(1)
        self.descent_outcome = "cap_hit"
        self.logger.warning(f"Suggestions zone not reached: the {max_scrolls}-scroll safety "
                            f"cap was hit while the list was still moving")
        return False

    def open_suggestion_profile(self, row: Dict[str, Any],
                                load_timeout_s: float = 8.0) -> bool:
        """Ouvrir le profil d'une ligne de suggestion, et le PROUVER.

        On tape le corps de la ligne (``row_point``), pas son bouton : le libelle n'est
        pas cliquable, mais son ancetre — la cellule de la ligne — l'est et recoit
        l'evenement. Le bouton, lui, est une cible distincte qui ferait un follow a
        l'aveugle sans jamais ouvrir la fiche.

        Le succes n'est pas "le tap est parti" mais "on est sur un profil" : c'est le
        pipeline injecte qui le prouve, avec les signatures propres a la surface profil.
        """
        pipeline = getattr(self, "profile_pipeline", None)
        if pipeline is None:
            self.logger.error("Cannot open a suggestion profile: no profile pipeline injected")
            return False
        point = row.get("row_point")
        if not point:
            self.logger.warning(f"Suggestion '{row.get('label') or '?'}' has no row point to tap")
            return False
        if not self._tap_point(point, f"Open suggestion '{row.get('label') or '?'}'"):
            return False
        return pipeline.wait_for_profile(timeout=load_timeout_s)

    def leave_suggestion_profile(self) -> bool:
        """Revenir du profil a l'ecran Notifications.

        Le pipeline a pu descendre dans les posts ou ouvrir une story : plusieurs backs
        peuvent etre necessaires. Si l'ecran ne revient toujours pas, on repasse par
        ``ensure_notifications_screen``, qui sait relancer Instagram et re-naviguer
        (auto-reparation deja utilisee par les actions par ligne).
        """
        if self._return_to_notifications(attempts=6):
            return True
        self.logger.info("Back presses did not restore the notifications screen — recovering")
        return self.ensure_notifications_screen()

    # ------------------------------------------------------------------
    # Boucle complete
    # ------------------------------------------------------------------
    def visit_suggestions(self, max_profiles: int = 5, max_scrolls: int = 8,
                          max_descent_scrolls: int = 60,
                          refresh_first: bool = True,
                          delay_range: tuple = (4, 12),
                          on_profile: Optional[Callable[[Dict[str, Any]], None]] = None,
                          ) -> Dict[str, Any]:
        """Visiter et qualifier les comptes proposes en bas de l'ecran Notifications.

        Le SEQUENCAGE (lire, ouvrir, qualifier, revenir, suivant) est celui du service
        partage ``common/suggestion_visit`` : il est identique sur l'ecran « Decouvrir
        des personnes », et le dupliquer ferait diverger les deux surfaces sur des
        regles fines — deduplication par identite, erreurs dites et non sautees,
        cadence entre deux profils. Ce module ne garde que la NAVIGATION propre a la
        zone Notifications, exposee via l'adaptateur ci-dessous.
        """
        if max_profiles > 0 and getattr(self, "profile_pipeline", None) is None:
            # Refus FRANC : sans pipeline il ne resterait que le follow a l'aveugle
            # depuis la liste, c'est-a-dire exactement ce que ce mode remplace.
            self.logger.error("Suggestions visit skipped: no per-profile pipeline injected")
            self._notify("suggestions", "failed", "Pipeline profil indisponible")
            return {"visited": 0, "processed": 0, "follows": 0, "filtered": 0,
                    "skipped_known": 0, "errors": 0, "attempts": 0, "scrolls": 0,
                    "skipped_follow_back": 0, "profiles": [], "stop_reason": "no_pipeline"}

        self._optimize_locale()  # l'en-tete de la zone et les boutons sont du TEXTE
        if refresh_first:
            # Le scan qui precede a DEPLIE la liste a coups de « Voir plus » : la section
            # de personnes, qui est a un ou deux ecrans du haut sur une liste repliee, se
            # retrouve alors des dizaines d'ecrans plus bas. Sortir et rentrer la replie.
            self.refresh_notifications_screen()
        self._reported_unreadable_suggestions = False

        return visit_suggestions(
            _NotificationsSuggestionSurface(self, max_descent_scrolls),
            max_profiles=max_profiles, max_scrolls=max_scrolls,
            delay_range=delay_range, on_profile=on_profile,
        )


class _NotificationsSuggestionSurface(SuggestionSurface):
    """Adaptateur : ce que la zone Notifications a de particulier, et rien d'autre.

    Sa singularite est la DESCENTE — la zone vit au fond d'une liste dont la longueur
    depend du compte, et elle n'est pas toujours servie. C'est le seul endroit ou cette
    surface differe de « Decouvrir des personnes ».
    """

    name = "notifications"

    def __init__(self, workflow, max_descent_scrolls: int):
        self._wf = workflow
        self._max_descent_scrolls = max_descent_scrolls
        self.reach_failure_reason = "zone_not_reached"

    def reach(self) -> bool:
        if self._wf.reach_suggestions_zone(self._max_descent_scrolls):
            return True
        # 'no_suggestions_offered' n'est pas un echec : Instagram ne sert pas de section
        # de suggestions a cet instant. Le confondre avec un probleme de navigation
        # ferait chercher un bug la ou il n'y en a pas.
        self.reach_failure_reason = self._wf.descent_outcome
        return False

    def scan(self) -> List[Dict[str, Any]]:
        rows = self._wf.scan_suggestions()
        self._wf._report_unreadable_rows(rows)
        return rows

    def followable(self, rows):
        return followable_suggestions(rows)

    def row_key(self, row):
        return self._wf._row_key(row)

    def open_profile(self, row) -> bool:
        return self._wf.open_suggestion_profile(row)

    def read_username(self):
        return self._wf.profile_pipeline.read_username()

    def process(self, username):
        return self._wf.profile_pipeline.process(username)

    def leave(self) -> bool:
        return self._wf.leave_suggestion_profile()

    def scroll(self) -> None:
        self._wf._scroll_down(1)

    def log_info(self, message: str) -> None:
        self._wf.logger.info(f"Suggestion {message}")

    def log_warning(self, message: str) -> None:
        self._wf.logger.warning(f"Suggestion {message}")

    def notify(self, step: str, status: str, message: str = "", **extra) -> None:
        self._wf._notify(step, status, message, **extra)

__all__ = ["NotificationSuggestionsMixin"]
