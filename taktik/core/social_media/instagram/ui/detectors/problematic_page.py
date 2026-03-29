"""
Détecteur et gestionnaire des pages problématiques Instagram qui interrompent le workflow.
"""
import time
from typing import Optional, Dict, Any
from loguru import logger
from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot
from ..selectors import POPUP_SELECTORS, PROBLEMATIC_PAGE_SELECTORS


class ProblematicPageDetector:
    """
    Détecte et ferme automatiquement les pages problématiques qui peuvent interrompre le workflow.
    """
    
    def __init__(self, device, debug_mode: bool = False):
        """
        Initialise le détecteur.
        
        Args:
            device: Instance de DeviceFacade
            debug_mode: Si True, sauvegarde les dumps et screenshots pour debug
        """
        self.device = device
        self.debug_mode = debug_mode
        
        # Statistiques de détection des popups de rate limiting
        self.rate_limit_stats = {
            'detected_count': 0,  # Nombre de fois détectée
            'closed_count': 0,    # Nombre de fois fermée avec succès
            'failed_count': 0,    # Nombre de fois où la fermeture a échoué
            'last_detection': None  # Timestamp de la dernière détection
        }
        
        # Utiliser les patterns centralisés depuis selectors.py
        self.detection_patterns = PROBLEMATIC_PAGE_SELECTORS.detection_patterns
    
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
        Détecte et ferme automatiquement les pages problématiques.
        
        Returns:
            dict: {
                'detected': bool,  # True si une page problématique a été détectée
                'closed': bool,    # True si la page a été fermée avec succès
                'soft_ban': bool,  # True si c'est un soft ban qui nécessite l'arrêt de la session
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
                    
                    # Tracking des statistiques pour les popups de rate limiting
                    if config.get('track_stats', False):
                        self._update_rate_limit_stats('detected')
                    
                    # Vérifier si c'est un soft ban
                    is_soft_ban = config.get('is_soft_ban', False)
                    if is_soft_ban:
                        logger.error(f"🛑 SOFT BAN DÉTECTÉ ({page_type}) - La session doit être arrêtée")
                        logger.warning(f"📊 Statistiques rate limiting: {self.get_rate_limit_stats()}")
                    
                    # Essayer de fermer la page
                    if self._close_problematic_page(page_type, config['close_methods']):
                        logger.success(f"✅ Page {page_type} fermée avec succès")
                        
                        # Tracking de la fermeture réussie
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
        Vérifie si une page est détectée basée sur ses indicateurs.
        
        Args:
            ui_content: Contenu XML de l'UI
            indicators: Liste des indicateurs à rechercher
        
        Returns:
            bool: True si la page est détectée
        """
        # Compter combien d'indicateurs sont présents
        found_indicators = 0
        found_list = []
        
        # Indicateurs génériques à ignorer dans certains contextes
        generic_indicators = ['Posts', 'Stories', 'Reels', 'Some']
        
        for indicator in indicators:
            if indicator.lower() in ui_content.lower():
                # Si c'est un indicateur générique, vérifier le contexte
                if indicator in generic_indicators:
                    # Ignorer si on trouve aussi des éléments de navigation normale
                    if any(nav in ui_content.lower() for nav in ['home', 'search', 'profile', 'following', 'followers']):
                        logger.debug(f"Indicateur générique '{indicator}' ignoré (contexte navigation normale)")
                        continue
                
                found_indicators += 1
                found_list.append(indicator)
                logger.debug(f"Indicateur trouvé: {indicator}")
        
        logger.debug(f"Indicateurs trouvés: {found_list} ({found_indicators}/{len(indicators)})")
        
        # Logique de seuil améliorée pour éviter les faux positifs
        if len(indicators) <= 3:
            # Pour les petites listes, nécessiter au moins 1 indicateur
            threshold = 1
        elif len(indicators) <= 6:
            # Pour les listes moyennes, nécessiter au moins 2 indicateurs
            threshold = 2
        else:
            # Pour les grandes listes, nécessiter au moins 25% des indicateurs
            threshold = max(2, len(indicators) // 4)
        
        is_detected = found_indicators >= threshold
        
        if is_detected:
            logger.warning(f"🚨 Page détectée avec {found_indicators}/{len(indicators)} indicateurs: {found_list}")
        else:
            logger.debug(f"Page non détectée ({found_indicators}/{len(indicators)} indicateurs trouvés)")
        
        return is_detected
    
    def _close_problematic_page(self, page_type: str, close_methods: list) -> bool:
        """
        Tente de fermer une page problématique avec différentes méthodes.
        
        Args:
            page_type: Type de page à fermer
            close_methods: Liste des méthodes de fermeture à essayer
        
        Returns:
            bool: True si la fermeture a réussi
        """
        logger.info(f"🔧 Tentative de fermeture de la page {page_type}")
        
        for method in close_methods:
            try:
                logger.info(f"Essai de la méthode: {method}")
                
                if method == 'back_button':
                    # Utiliser l'API uiautomator2 pour le bouton retour
                    self.device.press("back")
                    
                elif method == 'not_now_button':
                    # Chercher un bouton "Not Now" / "Pas maintenant"
                    for selector in POPUP_SELECTORS.not_now_selectors:
                        elements = self.device.xpath(selector)
                        if elements.exists:
                            elements.click()
                            logger.info(f"✅ Bouton 'Not Now' cliqué avec: {selector}")
                            break
                
                elif method == 'x_button':
                    if not self._click_button_from_selectors(
                        PROBLEMATIC_PAGE_SELECTORS.close_button_selectors, "X/Close"
                    ):
                        continue
                            
                elif method == 'tap_outside':
                    # Taper dans la zone supérieure (zone des followers)
                    info = self.device.info
                    screen_width = info['displayWidth']
                    screen_height = info['displayHeight']
                    
                    # Cliquer dans la zone des followers (partie haute de l'écran)
                    self.device.click(screen_width // 2, screen_height // 4)
                    
                elif method == 'swipe_down':
                    # Swipe vers le bas pour fermer la popup
                    # Tente d'abord de trouver le drag handle pour un swipe précis
                    info = self.device.info
                    screen_width = info.get('displayWidth', 1080)
                    screen_height = info.get('displayHeight', 1920)

                    handle_swiped = False
                    for sel in [{'resourceId': 'com.instagram.android:id/bottom_sheet_drag_handle_prism'}]:
                        try:
                            el = self.device(**sel)
                            if el.exists():
                                b = el.info.get('bounds', {})
                                if b:
                                    hx = (b['left'] + b['right']) // 2
                                    hy = (b['top'] + b['bottom']) // 2
                                    # Only swipe if handle is NOT in top 10% (would open notifications)
                                    if hy >= int(screen_height * 0.10):
                                        end_y = int(screen_height * 0.95)
                                        logger.info(f"swipe_down handle found: ({hx},{hy}) → ({hx},{end_y})")
                                        self.device.swipe_coordinates(hx, hy, hx, end_y, 0.3)
                                        handle_swiped = True
                                    else:
                                        logger.info(f"Handle in top 10% (y={hy}), using press back instead")
                                        self.device.press('back')
                                        handle_swiped = True
                                    break
                        except Exception:
                            pass

                    if not handle_swiped:
                        # Fallback: swipe from screen center-ish (safe zone, never from top)
                        start_x = screen_width // 2
                        start_y = int(screen_height * 0.50)
                        end_y = int(screen_height * 0.92)
                        logger.info(f"swipe_down fallback: ({start_x},{start_y}) → ({start_x},{end_y})")
                        self.device.swipe_coordinates(start_x, start_y, start_x, end_y, 0.3)
                
                elif method == 'swipe_down_handle':
                    # Méthode spécifique pour le trait gris (handle) - cibler l'élément directement
                    handle_found = False
                    screen_info = self.device.info
                    screen_height = screen_info.get('displayHeight', 1920)
                    screen_width = screen_info.get('displayWidth', 1080)

                    for selector in PROBLEMATIC_PAGE_SELECTORS.drag_handle_selectors:
                        try:
                            element = self.device(**selector)
                            if element.exists():
                                bounds = element.info.get('bounds', {})
                                if bounds:
                                    handle_x = (bounds['left'] + bounds['right']) // 2
                                    handle_y = (bounds['top'] + bounds['bottom']) // 2
                                    end_y = int(screen_height * 0.95)

                                    if handle_y < int(screen_height * 0.10):
                                        # Handle fully expanded — swipe would open notifications, use back
                                        logger.info(f"Handle in top 10% (y={handle_y}), pressing back")
                                        self.device.press('back')
                                    else:
                                        logger.info(f"Swipe handle: ({handle_x},{handle_y}) → ({handle_x},{end_y})")
                                        self.device.swipe_coordinates(handle_x, handle_y, handle_x, end_y, 0.3)
                                    handle_found = True
                                    break
                        except Exception:
                            pass

                    if not handle_found:
                        logger.warning("Handle non trouvé, utilisation de coordonnées sûres (50% → 92%)")
                        handle_x = screen_width // 2
                        handle_y = int(screen_height * 0.50)
                        end_y = int(screen_height * 0.92)
                        logger.info(f"Swipe handle approximatif: ({handle_x},{handle_y}) → ({handle_x},{end_y})")
                        self.device.swipe_coordinates(handle_x, handle_y, handle_x, end_y, 0.3)
                
                elif method == 'terminate_button':
                    if not self._click_button_from_selectors(
                        PROBLEMATIC_PAGE_SELECTORS.terminate_button_selectors, "Terminé"
                    ):
                        continue
                
                elif method == 'ok_button':
                    if not self._click_button_from_selectors(
                        PROBLEMATIC_PAGE_SELECTORS.ok_button_selectors, "OK"
                    ):
                        continue
                
                elif method == 'tap_background_dimmer':
                    if not self._click_button_from_selectors(
                        PROBLEMATIC_PAGE_SELECTORS.background_dimmer_selectors, "Background dimmer"
                    ):
                        continue
                
                elif method == 'allow_permission_button':
                    # Click the Android permission "Allow" button
                    allow_selectors = [
                        {'resourceId': 'com.android.packageinstaller:id/permission_allow_button'},
                        {'text': 'AUTORISER'},
                        {'text': 'ALLOW'},
                        {'text': 'Autoriser'},
                        {'text': 'Allow'},
                    ]
                    if not self._click_button_from_selectors(allow_selectors, "Allow permission"):
                        continue
                
                # Attendre moins longtemps pour accélérer le processus
                time.sleep(1.0)
                
                # Vérifier si la fermeture a fonctionné
                if self._verify_page_closed(page_type):
                    logger.success(f"✅ Méthode {method} réussie")
                    return True
                else:
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
            bool: True si la page est fermée
        """
        try:
            ui_content = self._get_ui_content("vérification")
            if not ui_content:
                return False
            
            # Vérifier que les indicateurs ne sont plus présents
            config = self.detection_patterns[page_type]
            return not self._is_page_detected(ui_content, config['indicators'])
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de fermeture: {e}")
            return False
    
    def monitor_and_handle_continuously(self, check_interval: int = 5) -> None:
        """
        Surveille en continu les pages problématiques et les ferme automatiquement.
        
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
        Met à jour les statistiques de rate limiting.
        
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
        Récupère les statistiques de rate limiting.
        
        Returns:
            dict: Statistiques complètes avec taux de succès
        """
        stats = self.rate_limit_stats.copy()
        
        # Calculer le taux de succès
        total_attempts = stats['closed_count'] + stats['failed_count']
        if total_attempts > 0:
            stats['success_rate'] = (stats['closed_count'] / total_attempts) * 100
        else:
            stats['success_rate'] = 0.0
        
        return stats
    
    def reset_rate_limit_stats(self) -> None:
        """
        Réinitialise les statistiques de rate limiting.
        """
        self.rate_limit_stats = {
            'detected_count': 0,
            'closed_count': 0,
            'failed_count': 0,
            'last_detection': None
        }
        logger.info("📊 Statistiques de rate limiting réinitialisées")
    
    def should_stop_session(self) -> bool:
        """
        Détermine si la session doit être arrêtée en fonction du nombre de rate limits.
        
        Règle de sécurité: Arrêter si on détecte plus de 3 rate limits dans une session
        pour éviter un bannissement permanent.
        
        Returns:
            bool: True si la session doit être arrêtée
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
    Factory function pour créer un détecteur de pages problématiques.
    
    Args:
        device: Instance de DeviceFacade
        debug_mode: Si True, active les dumps et screenshots pour debug
    
    Returns:
        ProblematicPageDetector: Instance du détecteur
    """
    return ProblematicPageDetector(device, debug_mode)
