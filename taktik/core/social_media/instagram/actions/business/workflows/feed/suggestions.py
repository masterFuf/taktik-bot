"""Mode "follow des suggestions" du workflow Feed.

Chemin produit complet, une methode par etape pour rester testable unitairement
depuis le Cartography Lab :

feed -> carousel netego "Suggested for you" -> CTA "See all" -> modale d'acces aux
contacts -> ecran "Discover people" -> follow en masse -> retour au feed.

Regles metier (arbitrage Kevin) :

- on ne fait NI follow-back NI acceptation de demande de suivi ici : les deux
  vivent deja dans le workflow Notifications. Seul un bouton dont l'etat est
  exactement 'follow' est tape (cf. ``followable_rows``) ;
- on ne visite AUCUN profil : c'est un follow de masse depuis la liste, pas une
  acquisition qualifiee. Aucun filtre profil / IA ne s'applique donc ici ;
- la modale contacts est traitee explicitement, jamais laissee au detecteur de
  pages problematiques generique.

Limite connue de la surface : IG n'expose pas le @handle dans cette liste, mais
seulement le libelle affiche (souvent le nom complet). Les follows sont donc
enregistres sous ce libelle, avec la provenance dans ``content`` ; la
reconciliation avec les vrais handles se fait plus tard par la synchro
``following_sync``.
"""

import random
import time
from typing import Any, Dict, List, Optional

from lxml import etree

from taktik.core.shared.telemetry import emit_step
from ....atomic.interaction.profile_interaction import classify_follow_state
from ....core.ipc import IPCEmitter
from .suggestions_parsing import (
    followable_rows,
    is_discover_people_screen,
    parse_feed_suggestions_carousel,
    parse_suggestion_rows,
    read_screen_title,
)


class FeedSuggestionsMixin:
    """Mixin: detection du carousel de suggestions et follow de masse associe."""

    # Passes de scroll consecutives sans nouvelle ligne "Follow" avant de
    # considerer la liste epuisee (meme esprit que la stop policy des workflows
    # target : on raisonne en comptes rencontres, pas en nombre de scrolls).
    _SUGGESTIONS_EMPTY_SCROLL_RUNS = 2

    # ------------------------------------------------------------------
    # Lecture d'ecran
    # ------------------------------------------------------------------

    def _suggestions_dump_root(self):
        """Dump complet (non compresse) parse en racine lxml, ou None."""
        xml = None
        try:
            xml = self.device.dump_hierarchy(compressed=False)
        except TypeError:
            try:
                xml = self.device.dump_hierarchy()
            except Exception as exc:
                self.logger.debug(f"dump_hierarchy failed: {exc}")
        except Exception as exc:
            self.logger.debug(f"dump_hierarchy failed: {exc}")
        if not xml:
            return None
        try:
            return etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
        except Exception as exc:
            self.logger.debug(f"XML parse failed: {exc}")
            return None

    def has_feed_suggestions_carousel(self) -> bool:
        """Sonde LEGERE du carousel : un seul acces device, pas de dump complet.

        Appelee a chaque post de la boucle feed, elle doit rester bon marche ; le
        dump complet n'est fait qu'une fois le carousel confirme.
        """
        from taktik.core.social_media.instagram.ui.selectors import FEED_SUGGESTIONS_SELECTORS
        try:
            for selector in FEED_SUGGESTIONS_SELECTORS.carousel_see_all:
                if self.device.xpath(selector).exists:
                    return True
        except Exception as exc:
            self.logger.debug(f"Suggestions carousel probe failed: {exc}")
        return False

    def detect_feed_suggestions_carousel(self, root=None) -> Dict[str, Any]:
        """Etat du carousel "Suggested for you" dans le feed courant."""
        from taktik.core.social_media.instagram.ui.selectors import FEED_SUGGESTIONS_SELECTORS
        root = root if root is not None else self._suggestions_dump_root()
        return parse_feed_suggestions_carousel(root, FEED_SUGGESTIONS_SELECTORS)

    def is_on_discover_people_screen(self, root=None) -> bool:
        """True si l'ecran de suggestions ("Discover people") est affiche."""
        from taktik.core.social_media.instagram.ui.selectors import DISCOVER_PEOPLE_SELECTORS
        root = root if root is not None else self._suggestions_dump_root()
        return is_discover_people_screen(root, DISCOVER_PEOPLE_SELECTORS)

    def scan_discover_suggestions(self, root=None) -> List[Dict[str, Any]]:
        """Lignes de suggestion visibles, avec leur etat de relation."""
        from taktik.core.social_media.instagram.ui.selectors import (
            DISCOVER_PEOPLE_SELECTORS,
            PROFILE_SELECTORS,
        )
        root = root if root is not None else self._suggestions_dump_root()
        return parse_suggestion_rows(
            root, DISCOVER_PEOPLE_SELECTORS, PROFILE_SELECTORS, classify_follow_state
        )

    # ------------------------------------------------------------------
    # Navigation d'entree
    # ------------------------------------------------------------------

    def open_suggestions_see_all(self, root=None) -> bool:
        """Taper le CTA "See all" du carousel pour ouvrir Discover people.

        Le CTA est cible par resource-id (langue-neutre) et tape sur ses bounds
        reelles, jamais sur une coordonnee ecrite en dur.
        """
        carousel = self.detect_feed_suggestions_carousel(root)
        if not carousel.get("cta_bounds"):
            self.logger.debug("Suggestions carousel CTA not visible")
            return False
        if not self.device.human_tap(carousel["cta_bounds"]):
            self.logger.debug("Suggestions CTA tap failed")
            return False
        self.logger.info(f"Opened suggestions list from feed carousel "
                         f"('{carousel.get('title') or 'Suggested for you'}')")
        emit_step("tap", action="suggestions_see_all")
        self._human_like_delay('navigation')
        return True

    def handle_contacts_access_dialog(self, choice: str = 'deny') -> str:
        """Traiter la modale "autoriser l'acces aux contacts".

        Returns ``'denied'`` | ``'allowed'`` | ``'absent'`` | ``'other_dialog'``.

        La modale porte les resource-id GENERIQUES des alertes Instagram
        (``igds_alert_dialog_*``), que porte aussi l'alerte soft-ban "Try again
        later". On exige donc que le HEADLINE corresponde aux fragments de
        ``contacts_access_headline_texts`` avant de taper quoi que ce soit :
        sinon on rend ``'other_dialog'`` sans toucher a l'ecran, et l'alerte
        reste au detecteur de pages problematiques.
        """
        from taktik.core.social_media.instagram.ui.selectors import POPUP_SELECTORS

        headline = None
        for selector in POPUP_SELECTORS.contacts_access_dialog:
            element = self.device.xpath(selector)
            if element.exists:
                headline = (element.get_text() or '').strip()
                break
        if headline is None:
            return 'absent'

        lowered = headline.lower()
        fragments = [f.strip().lower() for f in POPUP_SELECTORS.contacts_access_headline_texts
                     if f and f.strip()]
        if not any(fragment in lowered for fragment in fragments):
            self.logger.warning(f"Alert dialog is not the contacts request "
                                f"('{headline[:60]}') - leaving it untouched")
            return 'other_dialog'

        allow = str(choice).lower() in ('allow', 'allowed', 'accept', 'true', '1')
        selectors = (POPUP_SELECTORS.contacts_access_allow_button if allow
                     else POPUP_SELECTORS.contacts_access_deny_button)
        label = 'allowed' if allow else 'denied'

        for selector in selectors:
            element = self.device.xpath(selector)
            if element.exists:
                if not self._human_tap_element(element):
                    element.click()
                self.logger.info(f"Contacts access dialog: {label}")
                emit_step("tap", action=f"contacts_access_{label}")
                self._human_like_delay('navigation')
                return label

        self.logger.warning("Contacts access dialog visible but its buttons were not found")
        return 'other_dialog'

    def scroll_discover_suggestions(self) -> bool:
        """Descendre d'un ecran dans la liste de suggestions (scroll humanise)."""
        try:
            self.device.human_scroll("down", distance_ratio=0.55)
            self._human_like_delay('scroll')
            return True
        except Exception as exc:
            self.logger.debug(f"Suggestions scroll failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Follow
    # ------------------------------------------------------------------

    def _record_suggestion_follow(self, label: str, social_context: str,
                                  section: str) -> None:
        """Comptabiliser un follow de suggestion comme le fait le moteur d'interaction.

        Meme sequence que ``_do_follow`` : compteur live AU GESTE, ecriture DB,
        compteur de session (qui porte ``total_follows_limit``), telemetrie
        d'etape et event IPC.
        """
        self._count_live('follows')
        provenance = f"Suggestion Instagram ({section})" if section else "Suggestion Instagram"
        if social_context:
            provenance = f"{provenance} - {social_context}"
        self._record_action(label, 'FOLLOW', 1, content=provenance)
        try:
            session = getattr(self, 'session_manager', None)
            if session:
                session.record_action('follow_user', success=True, source=label)
        except Exception as exc:
            self.logger.debug(f"Follow session counter increment failed: {exc}")
        emit_step("follow", action="suggestion_row", target=label)
        IPCEmitter.emit_follow(label, success=True)

    @staticmethod
    def _row_key(row: Dict[str, Any]) -> str:
        """Clef de deduplication d'une ligne entre deux dumps.

        Le libelle suffit dans l'immense majorite des cas ; s'il est vide on
        retombe sur la bande verticale de la ligne, qui reste stable tant qu'on
        n'a pas scrolle.
        """
        label = (row.get("label") or "").strip()
        if label:
            return label.lower()
        bounds = row.get("row_bounds")
        return f"row@{bounds[1] // 50}" if bounds else "row@?"

    def _follow_verified(self, root, row: Dict[str, Any]) -> bool:
        """Le bouton de ``row`` a-t-il bascule apres le tap ?

        Succes si la ligne affiche desormais 'following'/'requested', ou si elle
        a disparu de l'ecran (IG retire parfois une suggestion suivie). Echec si
        elle est toujours proposable.
        """
        key = self._row_key(row)
        for candidate in self.scan_discover_suggestions(root):
            if self._row_key(candidate) != key:
                continue
            state = candidate.get("state")
            if state in ('following', 'requested'):
                return True
            if state == 'follow':
                return False
            return True
        return True

    def follow_discover_suggestions(self, max_follows: int = 20,
                                    delay_range: tuple = (4, 12),
                                    max_scrolls: int = 15) -> Dict[str, Any]:
        """Follow en masse depuis l'ecran Discover people deja ouvert.

        Un seul dump par follow sert a la fois de verification du tap precedent
        et de source pour le suivant. La boucle s'arrete sur le plafond demande,
        sur la limite de session, ou quand la liste ne propose plus de nouvelle
        ligne 'Follow' apres plusieurs scrolls.
        """
        result = {
            'follows': 0, 'attempts': 0, 'scrolls': 0,
            'skipped_follow_back': 0, 'stop_reason': 'max_reached',
        }
        if max_follows <= 0:
            result['stop_reason'] = 'disabled'
            return result

        low, high = (delay_range if delay_range and len(delay_range) == 2 else (4, 12))
        attempted = set()
        # Les 'Follow back' sont comptes par IDENTITE et non par ecran : la meme ligne
        # reste visible sur plusieurs dumps successifs, un simple cumul la compterait
        # autant de fois qu'on la voit.
        seen_follow_back = set()
        empty_dump_streak = 0
        max_attempts = max(max_follows * 3, max_follows + 5)
        root = self._suggestions_dump_root()

        while result['follows'] < max_follows and result['attempts'] < max_attempts:
            if not self._suggestions_session_allows():
                result['stop_reason'] = 'session_limit'
                break

            rows = self.scan_discover_suggestions(root)
            seen_follow_back.update(self._row_key(row) for row in rows
                                    if row.get('state') == 'follow_back')
            result['skipped_follow_back'] = len(seen_follow_back)
            candidates = [row for row in followable_rows(rows)
                          if self._row_key(row) not in attempted]

            if not candidates:
                # Une liste peut aligner plusieurs ecrans entiers de 'Follow back' avant
                # la section suivante : l'absence de candidat ne prouve donc PAS la fin.
                # Seule une suite de dumps SANS aucune ligne signe la fin de liste ; le
                # reste est borne par le plafond de scrolls.
                empty_dump_streak = empty_dump_streak + 1 if not rows else 0
                if empty_dump_streak >= self._SUGGESTIONS_EMPTY_SCROLL_RUNS:
                    result['stop_reason'] = 'list_exhausted'
                    break
                if result['scrolls'] >= max_scrolls:
                    result['stop_reason'] = 'max_scrolls'
                    break
                if not self.scroll_discover_suggestions():
                    result['stop_reason'] = 'scroll_failed'
                    break
                result['scrolls'] += 1
                root = self._suggestions_dump_root()
                continue

            empty_dump_streak = 0
            row = candidates[0]
            attempted.add(self._row_key(row))
            result['attempts'] += 1

            label = row.get('label') or '(sans libelle)'
            if not self.device.human_tap(row['follow_bounds']):
                self.logger.debug(f"Follow tap failed for '{label}'")
                continue

            # Cadence humaine ENTRE deux follows : c'est le geste le plus surveille
            # par Instagram, on ne l'enchaine jamais a vitesse machine.
            time.sleep(random.uniform(min(low, high), max(low, high)))

            root = self._suggestions_dump_root()
            if self._follow_verified(root, row):
                result['follows'] += 1
                self._record_suggestion_follow(
                    label, row.get('social_context', ''), row.get('section', '')
                )
                self.logger.info(f"Followed suggestion '{label}' "
                                 f"({result['follows']}/{max_follows})")
            else:
                self.logger.debug(f"Follow did not register for '{label}'")

        return result

    def _suggestions_session_allows(self) -> bool:
        """La session autorise-t-elle encore UN FOLLOW ?

        Deux garde-fous distincts, et il faut les deux :

        - ``should_continue()`` porte la duree, les plafonds de session et le
          budget d'actions du jour ;
        - le sous-quota ``max_follows_per_day`` n'est deliberement PAS un motif
          d'arret de session : il desactive sa propre intention pour le reste de
          la journee, via ``exhausted_daily_quotas()``. Le moteur d'interaction
          le consulte pour retirer le follow du plan de chaque profil — un
          chemin que ce mode ne traverse pas, puisqu'il ne visite aucun profil.
          Sans cette lecture, une passe de suggestions depenserait le budget de
          follows du jour d'un compte en montee en charge sans jamais le voir.

        Fail-open comme le reste du garde-fou : une erreur de lecture ne doit pas
        tuer le run.
        """
        session = getattr(self, 'session_manager', None)
        if not session:
            return True

        if hasattr(session, 'should_continue'):
            try:
                should_continue, reason = session.should_continue()
                if not should_continue:
                    self.logger.info(f"Suggestions follow stopped by session: {reason}")
                    return False
            except Exception as exc:
                self.logger.debug(f"Session limit check failed: {exc}")

        if hasattr(session, 'exhausted_daily_quotas'):
            try:
                if 'follow' in (session.exhausted_daily_quotas() or set()):
                    self.logger.info("Suggestions follow stopped: daily follow quota spent")
                    return False
            except Exception as exc:
                self.logger.debug(f"Daily quota read failed: {exc}")

        return True

    # ------------------------------------------------------------------
    # Orchestration complete
    # ------------------------------------------------------------------

    def run_feed_suggestions_pass(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Passe complete : carousel du feed -> Discover people -> follows -> retour feed.

        Ne fait rien (et le dit) si le carousel n'est pas a l'ecran : c'est
        l'appelant (la boucle du feed) qui decide quand retenter.
        """
        result = {
            'entered': False, 'follows': 0, 'attempts': 0, 'scrolls': 0,
            'skipped_follow_back': 0, 'contacts_dialog': 'absent',
            'stop_reason': 'carousel_absent', 'returned_to_feed': False,
        }

        carousel = self.detect_feed_suggestions_carousel()
        if not carousel.get('present'):
            return result

        if not self.open_suggestions_see_all():
            result['stop_reason'] = 'cta_tap_failed'
            return result

        result['contacts_dialog'] = self.handle_contacts_access_dialog(
            config.get('suggestions_contacts_choice', 'deny')
        )
        if result['contacts_dialog'] == 'other_dialog':
            # Une autre alerte Instagram (soft-ban, mise a jour...) : on ne la
            # traite pas ici et on ne follow surtout pas derriere.
            result['stop_reason'] = 'blocked_by_dialog'
            self._return_to_feed()
            result['returned_to_feed'] = True
            return result

        if not self._wait_for_discover_screen():
            result['stop_reason'] = 'discover_screen_not_reached'
            self._return_to_feed()
            result['returned_to_feed'] = True
            return result

        result['entered'] = True
        title = read_screen_title(self._suggestions_dump_root())
        self.logger.info(f"On suggestions screen '{title or 'Discover people'}' - mass follow")

        follow_result = self.follow_discover_suggestions(
            max_follows=int(config.get('max_suggestion_follows', 20) or 0),
            delay_range=config.get('suggestion_follow_delay_range', (4, 12)),
            max_scrolls=int(config.get('max_suggestion_scrolls', 15) or 0),
        )
        result.update({k: follow_result[k] for k in
                       ('follows', 'attempts', 'scrolls', 'skipped_follow_back', 'stop_reason')})

        result['returned_to_feed'] = self._return_to_feed()
        return result

    def find_feed_suggestions_carousel(self, max_scrolls: int = 12) -> Dict[str, Any]:
        """Scroller le feed jusqu'a faire apparaitre le carousel de suggestions.

        Volontairement un scroll HUMANISE simple, et non l'avance "vers le prochain
        vrai post" du crawl : cette derniere saute justement par-dessus les blocs
        non-organiques, donc elle passerait au-dessus du carousel qu'on cherche.
        Ici on ne lit ni ne like rien, on cherche un bloc.
        """
        result = {'found': False, 'scrolls': 0}
        if self.has_feed_suggestions_carousel():
            result['found'] = True
            return result

        for _ in range(max(int(max_scrolls), 0)):
            try:
                self.device.human_scroll("down", distance_ratio=0.7)
            except Exception as exc:
                self.logger.debug(f"Feed scroll failed while looking for suggestions: {exc}")
                break
            self._human_like_delay('scroll')
            result['scrolls'] += 1
            if self.has_feed_suggestions_carousel():
                result['found'] = True
                break

        if not result['found']:
            self.logger.info(f"No suggestions carousel after {result['scrolls']} scroll(s)")
        return result

    def run_suggestions_only(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run "suggestions seules" : chercher le carousel, follow, s'arreter.

        Aucune interaction avec le fil : ni like, ni commentaire, ni story. C'est le
        mode a utiliser quand on veut UNIQUEMENT aller chercher des comptes dans les
        suggestions ; le feed n'est alors qu'un couloir vers le carousel.
        """
        result = {'follows': 0, 'passes': 0, 'carousel_scrolls': 0,
                  'skipped_follow_back': 0, 'stop_reason': 'carousel_not_found',
                  'returned_to_feed': True}
        passes_left = max(int(config.get('max_suggestion_passes', 1) or 0), 0)
        max_scrolls = int(config.get('max_carousel_scrolls', 12) or 0)

        while passes_left > 0:
            search = self.find_feed_suggestions_carousel(max_scrolls)
            result['carousel_scrolls'] += search['scrolls']
            if not search['found']:
                break

            pass_result = self.run_feed_suggestions_pass(config)
            result['passes'] += 1
            passes_left -= 1
            result['follows'] += pass_result.get('follows', 0)
            result['skipped_follow_back'] += pass_result.get('skipped_follow_back', 0)
            # Le motif d'arret reste celui de la boucle de FOLLOW ('max_reached',
            # 'list_exhausted'...). Ne pas l'ecraser par un probleme de retour :
            # sinon un run parfaitement abouti se lit comme un echec.
            result['stop_reason'] = pass_result.get('stop_reason', 'unknown')
            result['returned_to_feed'] = bool(pass_result.get('returned_to_feed'))

            if not pass_result.get('entered') or not result['returned_to_feed']:
                break

        return result

    def _wait_for_discover_screen(self, timeout: float = 8.0) -> bool:
        """Attendre l'ecran Discover people (wait conditionnel, pas un sleep fixe)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_on_discover_people_screen():
                return True
            time.sleep(0.5)
        self.logger.warning("Discover people screen never appeared")
        return False

    def _return_to_feed(self) -> bool:
        """Revenir au feed apres la passe de suggestions.

        On tape la FLECHE de la barre d'action, pas la touche back materielle.
        QA device du 2026-07-26 : l'ecran Discover people n'expose aucune barre
        d'onglets, et il n'a repondu ni a notre `press('back')` ni aux backs
        incrementaux de `navigate_to_home()` — le run finissait bloque sur la
        liste, et `navigate_to_home` cherchait un `feed_tab` absent de l'ecran.
        La fleche, elle, est un element reel : cible par resource-id (donc
        langue-neutre) et tapee sur ses bounds vivantes.
        """
        from taktik.core.social_media.instagram.ui.selectors import NAVIGATION_SELECTORS

        for _ in range(3):
            if not self.is_on_discover_people_screen():
                break
            if not self._tap_first_present(NAVIGATION_SELECTORS.back_buttons):
                # Plus de fleche a l'ecran : la touche back redevient le meilleur essai.
                try:
                    self.device.press('back')
                except Exception as exc:
                    self.logger.debug(f"Back key failed: {exc}")
                    break
            self._human_like_delay('navigation')

        if self.is_on_discover_people_screen():
            self.logger.warning("Still on the suggestions screen after the back attempts")
            return False

        try:
            return bool(self.nav_actions.navigate_to_home())
        except Exception as exc:
            self.logger.debug(f"Return to feed failed: {exc}")
            return False

    def _tap_first_present(self, selectors) -> bool:
        """Taper le premier element present parmi ``selectors`` (tap humanise)."""
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if not element.exists:
                    continue
                if not self._human_tap_element(element):
                    element.click()
                return True
            except Exception as exc:
                self.logger.debug(f"Tap on {selector} failed: {exc}")
        return False
