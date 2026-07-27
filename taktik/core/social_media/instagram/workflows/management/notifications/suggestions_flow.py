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

import random
import time
from typing import Any, Callable, Dict, List, Optional

from .suggestions_parsing import (
    find_suggestions_header_y,
    followable_suggestions,
    parse_notification_suggestions,
)


class NotificationSuggestionsMixin:
    """Mixin: lecture de la zone suggestions et visite qualifiee de ses profils."""

    # Deux dumps d'affilee sans AUCUNE ligne signent la fin de la liste. Un seul ne
    # prouve rien : un rendu en cours donne le meme resultat qu'une liste finie.
    _SUGGESTIONS_EMPTY_DUMP_RUNS = 2

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
    def reach_suggestions_zone(self, max_scrolls: int = 8) -> bool:
        """Descendre jusqu'a ce que l'en-tete "Suggestions" soit a l'ecran.

        La zone vit tout en bas de l'ecran Notifications, apres le bouton "Voir plus".
        Le scan complet y arrive naturellement en fin de course ; une action isolee (ou
        un retour de profil, qui repositionne la liste plus haut) doit y redescendre.
        """
        for _ in range(max(int(max_scrolls), 0) + 1):
            root = self._dump_root()
            if find_suggestions_header_y(root, self.selectors.suggestions_header_texts) is not None:
                return True
            self._scroll_down(1)
        self.logger.info("Suggestions zone not reached (header never came on screen)")
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
                          delay_range: tuple = (4, 12),
                          on_profile: Optional[Callable[[Dict[str, Any]], None]] = None,
                          ) -> Dict[str, Any]:
        """Visiter et qualifier les comptes proposes en bas de l'ecran Notifications.

        Chaque profil traverse le pipeline de production complet : extraction (bio,
        photo, stats), qualification IA, filtres, follow, ecritures DB. Le libelle
        affiche ne sert qu'a viser la ligne ; c'est le @handle lu SUR le profil qui est
        persiste.

        Regle metier identique aux autres surfaces (arbitrage Kevin) : seul un bouton
        dont l'etat est exactement 'follow' est retenu. Un 'follow back' appartient au
        flux de follow-back de cet ecran, un 'following' est deja fait.
        """
        result: Dict[str, Any] = {
            "visited": 0, "processed": 0, "follows": 0, "filtered": 0,
            "errors": 0, "attempts": 0, "scrolls": 0, "skipped_follow_back": 0,
            "profiles": [], "stop_reason": "max_reached",
        }
        if max_profiles <= 0:
            result["stop_reason"] = "disabled"
            return result

        pipeline = getattr(self, "profile_pipeline", None)
        if pipeline is None:
            # Refus FRANC : sans pipeline il ne resterait que le follow a l'aveugle
            # depuis la liste, c'est-a-dire exactement ce que ce mode remplace.
            result["stop_reason"] = "no_pipeline"
            self.logger.error("Suggestions visit skipped: no per-profile pipeline injected")
            self._notify("suggestions", "failed", "Pipeline profil indisponible")
            return result

        self._optimize_locale()  # l'en-tete de la zone et les boutons sont du TEXTE
        low, high = (delay_range if delay_range and len(delay_range) == 2 else (4, 12))
        attempted: set = set()
        seen_follow_back: set = set()
        self._reported_unreadable_suggestions = False
        empty_dump_streak = 0

        while result["visited"] < max_profiles:
            if not self.reach_suggestions_zone(max_scrolls):
                result["stop_reason"] = "zone_not_reached"
                break

            rows = self.scan_suggestions()
            # Comptes par IDENTITE et non par ecran : la meme ligne reste visible sur
            # plusieurs dumps successifs, un cumul la compterait autant de fois qu'on la voit.
            seen_follow_back.update(self._row_key(row) for row in rows
                                    if row.get("state") == "follow_back")
            result["skipped_follow_back"] = len(seen_follow_back)
            self._report_unreadable_rows(rows)

            candidates = [row for row in followable_suggestions(rows)
                          if self._row_key(row) not in attempted]

            if not candidates:
                empty_dump_streak = empty_dump_streak + 1 if not rows else 0
                if empty_dump_streak >= self._SUGGESTIONS_EMPTY_DUMP_RUNS:
                    result["stop_reason"] = "list_exhausted"
                    break
                if result["scrolls"] >= max_scrolls:
                    result["stop_reason"] = "max_scrolls"
                    break
                self._scroll_down(1)
                result["scrolls"] += 1
                continue

            empty_dump_streak = 0
            row = candidates[0]
            label = row.get("label") or "(sans libelle)"
            attempted.add(self._row_key(row))
            result["attempts"] += 1
            self._notify("suggestion_visit", "running", label, label=label)

            if not self.open_suggestion_profile(row):
                # Ni un profil, ni une erreur silencieuse : le tap a rate sa cible ou la
                # page n'a pas charge. On le dit, on revient, et on passe a la suivante.
                self.logger.warning(f"Suggestion '{label}': profile did not open")
                self._notify("suggestion_visit", "failed", f"{label}: profil non ouvert", label=label)
                result["errors"] += 1
                result["profiles"].append({"label": label, "username": None, "status": "not_opened"})
                self.leave_suggestion_profile()
                continue

            result["visited"] += 1
            username = pipeline.read_username()
            if not username:
                self.logger.warning(f"Suggestion '{label}': profile open but @handle unreadable")
                self._notify("suggestion_visit", "failed", f"{label}: @handle illisible", label=label)
                result["errors"] += 1
                result["profiles"].append({"label": label, "username": None, "status": "no_username"})
                self.leave_suggestion_profile()
                continue

            outcome = pipeline.process(username)
            result["processed"] += 1
            follows = outcome.follows
            result["follows"] += follows
            if outcome.was_filtered:
                result["filtered"] += 1
            if outcome.was_error:
                result["errors"] += 1
            entry = {
                "label": label, "username": username, "status": outcome.status,
                "follows": follows, "reasons": list(outcome.filter_reasons or []),
            }
            result["profiles"].append(entry)
            self.logger.info(f"Suggestion '{label}' -> @{username}: {outcome.status} "
                             f"({result['visited']}/{max_profiles})")
            # `outcome=` et non `status=` : `_notify` porte deja un parametre `status`
            # (running/done/failed) et la collision faisait echouer la narration.
            self._notify("suggestion_visit", "done", f"@{username}: {outcome.status}",
                         label=label, username=username, outcome=outcome.status)
            if on_profile:
                try:
                    on_profile(entry)
                except Exception as exc:  # noqa: BLE001 — un callback ne casse pas la passe
                    self.logger.debug(f"suggestion callback failed: {exc}")

            self.leave_suggestion_profile()
            # Cadence humaine ENTRE deux profils : le follow est le geste le plus
            # surveille, on ne l'enchaine jamais a vitesse machine.
            if result["visited"] < max_profiles:
                time.sleep(random.uniform(min(low, high), max(low, high)))

        return result


__all__ = ["NotificationSuggestionsMixin"]
