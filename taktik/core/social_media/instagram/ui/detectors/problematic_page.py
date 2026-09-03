"""
Detector and handler for the Instagram pages that interrupt a workflow.
"""
import time
from typing import Optional, Dict, Any
from loguru import logger
from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot
from ..selectors import POPUP_SELECTORS, PROBLEMATIC_PAGE_SELECTORS


class ProblematicPageDetector:
    """
    Detects and closes the pages that can interrupt a workflow.
    """
    
    def __init__(self, device, debug_mode: bool = False):
        """
        Initialise the detector.
        
        Args:
            device: Instance de DeviceFacade
                debug_mode: when True, save dumps and screenshots for debugging
        """
        self.device = device
        self.debug_mode = debug_mode
        
        # Detection statistics for the rate-limiting popups
        self.rate_limit_stats = {
            'detected_count': 0,  # Nombre de fois détectée
            'closed_count': 0,    # Times closed successfully
            'failed_count': 0,    # Nombre de fois où la fermeture a échoué
            'last_detection': None  # Timestamp of the last detection
        }
        
        # Use the centralized patterns
        self.detection_patterns = PROBLEMATIC_PAGE_SELECTORS.detection_patterns
    
    def _swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3):
        """Swipe compatible with both DeviceFacade and raw u2 Device."""
        if hasattr(self.device, 'swipe_coordinates'):
            self.device.swipe_coordinates(x1, y1, x2, y2, duration)
        else:
            self.device.swipe(x1, y1, x2, y2, duration=duration)
    
    def _get_ui_content(self, context: str = "detection") -> Optional[str]:
        """Get UI content based on debug mode."""
        if self.debug_mode:
            dump_path = dump_ui_hierarchy(self.device, "debug_ui/problematic_pages")
            if not dump_path:
                logger.warning(f"Impossible de dumper l'UI pour {context}")
                return None
            with open(dump_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            try:
                return self.device.dump_hierarchy()
            except Exception as e:
                logger.error(f"Erreur lors du dump UI pour {context}: {e}")
                return None
    
    def _click_button_from_selectors(self, selectors: list, button_name: str) -> bool:
        """Try to click a button from a list of selectors."""
        logger.debug(f"Recherche du bouton '{button_name}' avec {len(selectors)} sélecteurs")
        for selector in selectors:
            try:
                logger.debug(f"Essai du sélecteur: {selector}")
                element = self.device(**selector)
                if element.exists():
                    logger.info(f"Bouton {button_name} trouvé avec sélecteur: {selector}")
                    element.click()
                    return True
            except Exception as e:
                logger.debug(f"Erreur avec sélecteur {selector}: {e}")
        logger.warning(f"Bouton '{button_name}' non trouvé après {len(selectors)} tentatives")
        return False
    
    def detect_and_handle_problematic_pages(self) -> dict:
        """
        Detect and close a problematic page.
        
        Returns:
            dict: {
                'detected': bool,  # True si une page problématique a été détectée
                    'closed': bool,    # True when the page was closed successfully
                    'soft_ban': bool,  # True when the restriction requires stopping the session
                'page_type': str   # Type de page détectée (si applicable)
            }
        """
        try:
            logger.info("🔍 Vérification des pages problématiques...")
            logger.debug(f"Mode debug activé: {self.debug_mode}")
            
            ui_content = self._get_ui_content("detection")
            if not ui_content:
                return False
            
            # Vérifier chaque type de page problématique
            for page_type, config in self.detection_patterns.items():
                if self._is_page_detected(ui_content, config['indicators']):
                    logger.warning(f"🚨 Page problématique détectée: {page_type}")
                    
                    # Track the rate-limiting popup statistics
                    if config.get('track_stats', False):
                        self._update_rate_limit_stats('detected')
                    
                    # Check whether this is a restriction
                    is_soft_ban = config.get('is_soft_ban', False)
                    if is_soft_ban:
                        logger.error(f"🛑 SOFT BAN DÉTECTÉ ({page_type}) - La session doit être arrêtée")
                        logger.warning(f"📊 Statistiques rate limiting: {self.get_rate_limit_stats()}")
                    
                    # Try to close the page
                    if self._close_problematic_page(page_type, config['close_methods']):
                        logger.success(f"✅ Page {page_type} fermée avec succès")
                        
                        # Track the successful close
                        if config.get('track_stats', False):
                            self._update_rate_limit_stats('closed')
                        
                        return {
                            'detected': True,
                            'closed': True,
                            'soft_ban': is_soft_ban,
                            'page_type': page_type
                        }
                    else:
                        logger.error(f"❌ Impossible de fermer la page {page_type}")
                        
                        # Tracking de l'échec de fermeture
                        if config.get('track_stats', False):
                            self._update_rate_limit_stats('failed')
                        
                        return {
                            'detected': True,
                            'closed': False,
                            'soft_ban': is_soft_ban,
                            'page_type': page_type
                        }
            
            logger.debug("✅ Aucune page problématique détectée")
            return {
                'detected': False,
                'closed': False,
                'soft_ban': False,
                'page_type': None
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la détection des pages problématiques: {e}")
            return {
                'detected': False,
                'closed': False,
                'soft_ban': False,
                'page_type': None
            }
    
    def _is_page_detected(self, ui_content: str, indicators: list) -> bool:
        """
        Is a page detected, based on its markers?
        
        Args:
            ui_content: Contenu XML de l'UI
                indicators: markers to look for
        
        Returns:
                bool: True when the page is detected
        """
        # Count how many markers are present
        found_indicators = 0
        found_list = []
        
        # Generic markers to ignore in some contexts
        generic_indicators = ['Posts', 'Stories', 'Reels', 'Some']
        
        for indicator in indicators:
            if indicator.lower() in ui_content.lower():
                # For a generic marker, check the context
                if indicator in generic_indicators:
                    # Ignorer si on trouve aussi des éléments de navigation normale
                    if any(nav in ui_content.lower() for nav in ['home', 'search', 'profile', 'following', 'followers']):
                        logger.debug(f"Indicateur générique '{indicator}' ignoré (contexte navigation normale)")
                        continue
                
                found_indicators += 1
                found_list.append(indicator)
                logger.debug(f"Indicateur trouvé: {indicator}")
        
        logger.debug(f"Indicateurs trouvés: {found_list} ({found_indicators}/{len(indicators)})")
        
        # Threshold logic tuned to avoid false positives
        if len(indicators) <= 3:
            # Small lists: require at least one marker
            threshold = 1
        elif len(indicators) <= 6:
            # Medium lists: require at least two markers
            threshold = 2
        else:
            # Large lists: require at least a quarter of the markers
            threshold = max(2, len(indicators) // 4)
        
        is_detected = found_indicators >= threshold
        
        if is_detected:
            logger.warning(f"🚨 Page détectée avec {found_indicators}/{len(indicators)} indicateurs: {found_list}")
        else:
            logger.debug(f"Page non détectée ({found_indicators}/{len(indicators)} indicateurs trouvés)")
        
        return is_detected
    
    # ── Fermetures, une par méthode ───────────────────────────────────────────────────────────
    #
    # Ces onze gestes vivaient dans une cascade `if method == … elif …` à l'intérieur d'un `for`
    # et d'un `try` : cinq niveaux d'imbrication avant d'atteindre le travail utile, et la cascade
    # continuait. Mesuré : 13 niveaux de profondeur, score de complexité 261, dans un corpus dont
    # la médiane est 1.
    #
    # Chacune rend True quand elle a TENTÉ quelque chose — l'appelant vérifie alors si la page
    # s'est fermée — et False quand elle n'était pas applicable, auquel cas l'appelant passe à la
    # suivante. C'est ce que les `continue` de la cascade exprimaient.

    def _close_via_back(self) -> bool:
        self.device.press("back")
        return True

    def _close_via_not_now(self) -> bool:
        for selector in POPUP_SELECTORS.not_now_selectors:
            elements = self.device.xpath(selector)
            if elements.exists:
                elements.click()
                logger.info(f"✅ Bouton 'Not Now' cliqué avec: {selector}")
                break
        return True

    def _close_via_x(self) -> bool:
        return self._click_button_from_selectors(
            PROBLEMATIC_PAGE_SELECTORS.close_button_selectors, "X/Close")

    def _close_via_tap_outside(self) -> bool:
        """Taper la page DERRIÈRE la feuille, dans la bande laissée visible au-dessus d'elle.

        Ce geste tapait autrefois au quart de l'écran, sans condition. Sur une feuille qui remplit
        l'écran — la feuille de partage Direct le fait une fois déployée — ce point tombe dans sa
        propre grille de destinataires : le tap SÉLECTIONNAIT UN DESTINATAIRE au lieu de fermer
        quoi que ce soit, armant un « envoyer ce post à quelqu'un » qu'un tap de confirmation
        aurait pu compléter.

        Quand il n'y a pas de bande au-dessus de la feuille, il n'y a rien à taper dehors : on rend
        False et l'appelant passe à la méthode suivante.
        """
        from ...actions.atomic.interaction.bottom_sheet import sheet_outside_tap_point

        point = sheet_outside_tap_point(self.device)
        if point is None:
            logger.debug("tap_outside: sheet covers the screen, nothing outside to tap")
            return False
        self.device.click(point[0], point[1])
        return True

    def _swipe_handle_down(self, selectors, etiquette: str) -> bool:
        """Faire glisser la poignée d'une feuille vers le bas. Rend False si aucune n'est trouvée.

        La garde des 10 % du haut n'est pas cosmétique : une poignée tout en haut signifie une
        feuille déployée à fond, et un glissement partant de là ouvrirait le panneau de
        notifications d'Android au lieu de fermer la feuille. Dans ce cas on appuie sur retour.
        """
        info = self.device.info
        hauteur = info.get('displayHeight', 1920)
        for selector in selectors:
            try:
                element = self.device(**selector)
                if not element.exists():
                    continue
                bounds = element.info.get('bounds', {})
                if not bounds:
                    continue
                hx = (bounds['left'] + bounds['right']) // 2
                hy = (bounds['top'] + bounds['bottom']) // 2
                if hy < int(hauteur * 0.10):
                    logger.info(f"{etiquette}: poignée dans les 10% du haut (y={hy}) — retour arrière")
                    self.device.press('back')
                else:
                    fin_y = int(hauteur * 0.95)
                    logger.info(f"{etiquette}: ({hx},{hy}) → ({hx},{fin_y})")
                    self._swipe(hx, hy, hx, fin_y, 0.3)
                return True
            except Exception:
                continue
        return False

    def _swipe_from_middle(self, etiquette: str) -> bool:
        """Repli sans poignée : partir du MILIEU de l'écran, jamais du haut."""
        info = self.device.info
        largeur = info.get('displayWidth', 1080)
        hauteur = info.get('displayHeight', 1920)
        x = largeur // 2
        depart_y = int(hauteur * 0.50)
        fin_y = int(hauteur * 0.92)
        logger.info(f"{etiquette} (repli): ({x},{depart_y}) → ({x},{fin_y})")
        self._swipe(x, depart_y, x, fin_y, 0.3)
        return True

    def _close_via_swipe_down(self) -> bool:
        if self._swipe_handle_down([{'resourceIdMatches': '.*bottom_sheet_drag_handle_prism'}],
                                   "swipe_down handle"):
            return True
        return self._swipe_from_middle("swipe_down")

    def _close_via_swipe_down_handle(self) -> bool:
        if self._swipe_handle_down(PROBLEMATIC_PAGE_SELECTORS.drag_handle_selectors, "swipe handle"):
            return True
        logger.warning("Handle non trouvé, utilisation de coordonnées sûres (50% → 92%)")
        return self._swipe_from_middle("swipe handle approximatif")

    def _close_via_terminate(self) -> bool:
        return self._click_button_from_selectors(
            PROBLEMATIC_PAGE_SELECTORS.terminate_button_selectors, "Terminé")

    def _close_via_ok(self) -> bool:
        return self._click_button_from_selectors(
            PROBLEMATIC_PAGE_SELECTORS.ok_button_selectors, "OK")

    def _close_via_background_dimmer(self) -> bool:
        return self._click_button_from_selectors(
            PROBLEMATIC_PAGE_SELECTORS.background_dimmer_selectors, "Background dimmer")

    def _close_via_allow_permission(self) -> bool:
        return self._click_button_from_selectors(
            PROBLEMATIC_PAGE_SELECTORS.allow_permission_button_selectors, "Allow permission")

    def _close_via_ad_consent(self) -> bool:
        """Popup de consentement publicitaire Meta : deux pages (choix, puis accord)."""
        return self._handle_ad_consent_flow()

    def _closers(self) -> dict:
        """La table qui remplace la cascade : un nom de méthode, le geste qui la réalise.

        Construite ici plutôt qu'en attribut de classe : les valeurs sont des méthodes liées, et
        une table de classe les capturerait non liées.
        """
        return {
            'back_button': self._close_via_back,
            'not_now_button': self._close_via_not_now,
            'x_button': self._close_via_x,
            'tap_outside': self._close_via_tap_outside,
            'swipe_down': self._close_via_swipe_down,
            'swipe_down_handle': self._close_via_swipe_down_handle,
            'terminate_button': self._close_via_terminate,
            'ok_button': self._close_via_ok,
            'tap_background_dimmer': self._close_via_background_dimmer,
            'allow_permission_button': self._close_via_allow_permission,
            'ad_consent_flow': self._close_via_ad_consent,
        }

    def _close_problematic_page(self, page_type: str, close_methods: list) -> bool:
        """Essayer de fermer une page problématique par les méthodes disponibles.

        La boucle ne fait plus que trois choses : choisir le geste, le tenter, vérifier. Ce qui
        était onze branches imbriquées est devenu onze méthodes plates et une table.
        """
        logger.info(f"🔧 Tentative de fermeture de la page {page_type}")
        closers = self._closers()

        for method in close_methods:
            geste = closers.get(method)
            if geste is None:
                logger.warning(f"Méthode de fermeture inconnue: {method}")
                continue
            try:
                logger.info(f"Essai de la méthode: {method}")
                if not geste():
                    continue

                # Attente courte, pour garder le processus rapide.
                time.sleep(1.0)

                if self._verify_page_closed(page_type):
                    logger.success(f"✅ Méthode {method} réussie")
                    return True
                logger.warning(f"⚠️ Méthode {method} n'a pas fermé la page")
            except Exception as e:
                logger.error(f"Erreur avec la méthode {method}: {e}")
                continue

        logger.error(f"❌ Toutes les méthodes de fermeture ont échoué pour {page_type}")
        return False

    def _verify_page_closed(self, page_type: str) -> bool:
        """
        Vérifie si une page problématique a été fermée.
        
        Args:
            page_type: Type de page à vérifier
        
        Returns:
                bool: True when the page is closed
        """
        try:
            ui_content = self._get_ui_content("vérification")
            if not ui_content:
                return False
            
            # Verify the markers are gone
            config = self.detection_patterns[page_type]
            return not self._is_page_detected(ui_content, config['indicators'])
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de fermeture: {e}")
            return False
    
    def _handle_ad_consent_flow(self) -> bool:
        """Handle the Meta ad consent 2-page flow.
        
        Page 1: Select "Use free of charge with ads" -> Click "Continue"
        Page 2: Click "Agree"
        
        Returns True if the flow was completed successfully.
        """
        try:
            # Page 1: Click "Use free of charge with ads" radio option
            free_option_selectors = POPUP_SELECTORS.ad_consent_free_option
            for sel in free_option_selectors:
                el = self.device.xpath(sel)
                if el.exists:
                    el.click()
                    logger.info("✅ Selected 'Use free of charge with ads'")
                    time.sleep(1)
                    break
            
            # Page 1: Click "Continue"
            continue_selectors = POPUP_SELECTORS.ad_consent_continue_button
            clicked_continue = False
            for sel in continue_selectors:
                el = self.device.xpath(sel)
                if el.exists:
                    el.click()
                    logger.info("✅ Clicked Continue on ad consent page 1")
                    clicked_continue = True
                    time.sleep(2)
                    break
            
            if not clicked_continue:
                logger.warning("⚠️ Could not find Continue button on ad consent page 1")
                return False
            
            # Page 2: Click "Agree"
            agree_selectors = POPUP_SELECTORS.ad_consent_agree_button
            for sel in agree_selectors:
                el = self.device.xpath(sel)
                if el.exists:
                    el.click()
                    logger.info("✅ Ad consent popup dismissed (clicked Agree)")
                    time.sleep(1.5)
                    return True
            
            # Page 2 may not have appeared yet, wait a bit more
            time.sleep(1)
            for sel in agree_selectors:
                el = self.device.xpath(sel)
                if el.exists:
                    el.click()
                    logger.info("✅ Ad consent popup dismissed (clicked Agree, retry)")
                    time.sleep(1.5)
                    break
            
            # Page 3: "You can manage your ad experience" → Click OK
            time.sleep(1)
            page3_selectors = POPUP_SELECTORS.ad_consent_page3_indicators
            for sel in page3_selectors:
                if self.device.xpath(sel).exists:
                    logger.info("🪟 Meta ad consent page 3 (ad experience) detected")
                    ok_selectors = POPUP_SELECTORS.ad_consent_ok_button
                    for ok_sel in ok_selectors:
                        el = self.device.xpath(ok_sel)
                        if el.exists:
                            el.click()
                            logger.info("✅ Ad experience page dismissed (clicked OK)")
                            time.sleep(1.5)
                            return True
                    break
            
            return True
            
        except Exception as e:
            logger.error(f"Error in ad consent flow: {e}")
            return False

    def monitor_and_handle_continuously(self, check_interval: int = 5) -> None:
        """
        Watch continuously for problematic pages and close them.
        
        Args:
            check_interval: Intervalle de vérification en secondes
        """
        logger.info(f"🔄 Démarrage de la surveillance continue (intervalle: {check_interval}s)")
        
        while True:
            try:
                if self.detect_and_handle_problematic_pages():
                    logger.info("Page problématique traitée, poursuite de la surveillance...")
                
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("Arrêt de la surveillance demandé par l'utilisateur")
                break
            except Exception as e:
                logger.error(f"Erreur dans la surveillance continue: {e}")
                time.sleep(check_interval)
    
    def _update_rate_limit_stats(self, action: str) -> None:
        """
        Update the rate-limiting statistics.
        
        Args:
            action: Type d'action ('detected', 'closed', 'failed')
        """
        import datetime
        
        if action == 'detected':
            self.rate_limit_stats['detected_count'] += 1
            self.rate_limit_stats['last_detection'] = datetime.datetime.now().isoformat()
            logger.info(f"📊 Rate limit détecté #{self.rate_limit_stats['detected_count']}")
        elif action == 'closed':
            self.rate_limit_stats['closed_count'] += 1
        elif action == 'failed':
            self.rate_limit_stats['failed_count'] += 1
    
    def get_rate_limit_stats(self) -> dict:
        """
        Read the rate-limiting statistics.
        
        Returns:
                dict: full statistics, including the success rate
        """
        stats = self.rate_limit_stats.copy()
        
        # Compute the success rate
        total_attempts = stats['closed_count'] + stats['failed_count']
        if total_attempts > 0:
            stats['success_rate'] = (stats['closed_count'] / total_attempts) * 100
        else:
            stats['success_rate'] = 0.0
        
        return stats
    
    def reset_rate_limit_stats(self) -> None:
        """
        Reset the rate-limiting statistics.
        """
        self.rate_limit_stats = {
            'detected_count': 0,
            'closed_count': 0,
            'failed_count': 0,
            'last_detection': None
        }
        logger.info("📊 Statistiques de rate limiting réinitialisées")
    
    def is_action_blocked(self) -> bool:
        """Is Instagram showing its rate-limit dialog right now? Reads only, closes nothing.

        `detect_and_handle_problematic_pages` would CLOSE this one (`close_methods: ok_button`)
        and let the run carry on — which is acting again immediately after being told to stop,
        the surest way to turn a temporary limit into a lasting one. A caller that needs to
        decide whether to keep going has to be able to ask without touching the screen.
        """
        pattern = self.detection_patterns.get('try_again_later_page') or {}
        indicators = pattern.get('indicators') or []
        if not indicators:
            return False
        content = self._get_ui_content(context="action_blocked")
        if not content:
            return False
        return self._is_page_detected(content, indicators)

    def should_stop_session(self) -> bool:
        """
        Should the session stop, given how many rate limits were seen?
        
        Safety rule: stop past a few rate limits in one session, to avoid a
        permanent restriction.
        
        Returns:
                bool: True when the session must stop
        """
        threshold = 3
        detected = self.rate_limit_stats['detected_count']
        
        if detected >= threshold:
            logger.error(f"🛑 SEUIL DE SÉCURITÉ ATTEINT: {detected} rate limits détectés (seuil: {threshold})")
            logger.error("⚠️ Arrêt de la session pour éviter un bannissement permanent")
            return True
        
        return False


def create_problematic_page_detector(device, debug_mode: bool = False) -> ProblematicPageDetector:
    """
    Factory building a problematic-page detector.
    
    Args:
        device: Instance de DeviceFacade
            debug_mode: when True, enable dumps and screenshots for debugging
    
    Returns:
            ProblematicPageDetector: the detector instance
    """
    return ProblematicPageDetector(device, debug_mode)
