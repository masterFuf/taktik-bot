"""
Détecteur et gestionnaire des pages problématiques Instagram qui interrompent le workflow.
"""
import time
from typing import Optional, Dict, Any
from loguru import logger
from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot
from ..selectors import POPUP_SELECTORS


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
        self.detection_patterns = {
            'qr_code_page': {
                'indicators': [
                    'Partager le profil',
                    'QR code',
                    'Copier le lien',
                    '@dkabdo.videography'
                ],
                'close_methods': ['back_button', 'x_button', 'tap_outside']
            },
            'story_qr_code_page': {
                'indicators': [
                    'Enregistrer le code QR',
                    'Terminé',
                    'Tout le monde peut scanner ce code QR',
                    'smartphone pour voir ce contenu'
                ],
                'close_methods': ['terminate_button', 'back_button', 'tap_outside']
            },
            'message_contacts_page': {
                'indicators': [
                    'Write a message...',
                    'Écrivez un message…',
                    'Send separately',
                    'Envoyer',
                    'Search',
                    'Rechercher',
                    'Discussion non sélectionnée',
                    'New group',
                    'Nouveau groupe',
                    'direct_private_share_container_view',
                    'direct_share_sheet_grid_view_pog'
                ],
                'close_methods': ['swipe_down_handle', 'tap_outside', 'back_button']
            },
            'profile_share_page': {
                'indicators': [
                    'WhatsApp',
                    'Ajouter à la story',
                    'Partager',
                    'Texto',
                    'Threads'
                ],
                'close_methods': ['swipe_down_handle', 'swipe_down', 'tap_outside', 'back_button']
            },
            'try_again_later_page': {
                'indicators': [
                    # Titres (multilingue)
                    'Réessayer plus tard',
                    'Try Again Later',
                    # Messages (multilingue)
                    'Nous limitons la fréquence',
                    'We limit how often',
                    'certaines actions que vous pouvez effectuer',
                    'certain things on Instagram',
                    'protéger notre communauté',
                    'protect our community',
                    # Resource IDs
                    'igds_alert_dialog_headline',
                    'igds_alert_dialog_subtext',
                    'igds_alert_dialog_primary_button',
                    # Boutons
                    'Contactez-nous',
                    'Tell us'
                ],
                'close_methods': ['ok_button', 'back_button'],
                'is_soft_ban': True,  # Indique qu'il faut arrêter la session
                'track_stats': True   # Active le tracking des statistiques
            },
            'notifications_popup': {
                'indicators': [
                    'Notifications',
                    'Get notifications when',
                    'shares photos, videos or channels',
                    'Goes live',
                    'Some',
                    # Suppression de 'Posts' car trop générique
                    'Stories',
                    'Reels'
                ],
                'close_methods': ['back_button', 'tap_outside', 'swipe_down']
            },
            'follow_notification_popup': {
                'indicators': [
                    'Turn on notifications?',
                    'Get notifications when',
                    'Turn On',
                    'Not Now',
                    'posts a photo or video'
                ],
                'close_methods': ['not_now_button', 'back_button', 'tap_outside']
            },
            'instagram_update_popup': {
                'indicators': [
                    'Update Instagram',
                    'Get the latest version',
                    'Update',
                    'Not Now',
                    'available on Google Play'
                ],
                'close_methods': ['not_now_button', 'back_button', 'tap_outside']
            },
            'follow_options_bottom_sheet': {
                'indicators': [
                    'Ajouter à la liste Ami(e)s proches',
                    'Ajouter aux favoris',
                    'Sourdine',
                    'Restreindre',
                    'Ne plus suivre',
                    'bottom_sheet_container',
                    'background_dimmer'
                ],
                'close_methods': ['tap_background_dimmer', 'swipe_down_handle', 'back_button']
            },
            'mute_notifications_popup': {
                'indicators': [
                    'Sourdine',
                    'Publications',
                    'Stories',
                    'Bulles d\'activité sur le contenu',
                    'Notes',
                    'Notes sur la carte',
                    'Mute',
                    'Posts',
                    'Activity bubbles about content',
                    'bottom_sheet_start_nav_button_icon'
                ],
                'close_methods': ['swipe_down_handle', 'swipe_down', 'tap_outside']
            }
        }
    
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
            
            # Dump de l'UI actuelle pour analyse (seulement si debug activé)
            if self.debug_mode:
                dump_path = dump_ui_hierarchy(self.device, "debug_ui/problematic_pages")
                if not dump_path:
                    logger.warning("Impossible de dumper l'UI pour la détection")
                    return False
                
                # Lire le contenu du dump
                with open(dump_path, 'r', encoding='utf-8') as f:
                    ui_content = f.read()
            else:
                # En mode production, utiliser directement l'API uiautomator2
                try:
                    ui_content = self.device.dump_hierarchy()
                except Exception as e:
                    logger.error(f"Erreur lors du dump UI: {e}")
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
                    # Chercher un bouton X ou close avec uiautomator2
                    close_selectors = [
                        {'resourceId': 'com.instagram.android:id/action_bar_button_back'},
                        {'description': 'Close'},
                        {'description': 'Dismiss'},
                        {'description': 'Cancel'},
                        {'text': '×'},
                        {'text': '✕'},
                        {'className': 'android.widget.ImageView', 'description': 'Back'}
                    ]
                    
                    button_found = False
                    for selector in close_selectors:
                        element = self.device(**selector)
                        if element.exists():
                            element.click()
                            button_found = True
                            break
                    
                    if not button_found:
                        continue
                            
                elif method == 'tap_outside':
                    # Taper dans la zone supérieure (zone des followers)
                    info = self.device.info
                    screen_width = info['displayWidth']
                    screen_height = info['displayHeight']
                    
                    # Cliquer dans la zone des followers (partie haute de l'écran)
                    self.device.click(screen_width // 2, screen_height // 4)
                    
                elif method == 'swipe_down':
                    # Swipe vers le bas sur le trait gris pour fermer la popup
                    info = self.device.info
                    screen_width = info['displayWidth']
                    screen_height = info['displayHeight']
                    
                    # Chercher le trait gris (handle) de la popup
                    # Il est généralement au centre horizontal, vers le haut de la popup
                    start_x = screen_width // 2
                    start_y = int(screen_height * 0.65)  # Position approximative du trait
                    end_x = screen_width // 2
                    end_y = int(screen_height * 0.95)  # Vers le bas de l'écran
                    
                    logger.info(f"Swipe du trait gris: ({start_x}, {start_y}) → ({end_x}, {end_y})")
                    self.device.swipe(start_x, start_y, end_x, end_y, duration=0.3)
                
                elif method == 'swipe_down_handle':
                    # Méthode spécifique pour le trait gris (handle) - cibler l'élément directement
                    # Chercher le drag handle avec son resource-id
                    drag_handle_selectors = [
                        {'resourceId': 'com.instagram.android:id/bottom_sheet_drag_handle_prism'},
                        {'resourceId': 'com.instagram.android:id/bottom_sheet_drag_handle_frame'}
                    ]
                    
                    handle_found = False
                    for selector in drag_handle_selectors:
                        element = self.device(**selector)
                        if element.exists():
                            # Récupérer les coordonnées du handle
                            info = element.info
                            bounds = info.get('bounds', {})
                            if bounds:
                                # Centre du handle
                                handle_x = (bounds['left'] + bounds['right']) // 2
                                handle_y = (bounds['top'] + bounds['bottom']) // 2
                                
                                # Swipe vers le bas de l'écran
                                screen_height = self.device.info['displayHeight']
                                end_y = int(screen_height * 0.95)
                                
                                logger.info(f"Swipe handle trouvé: ({handle_x}, {handle_y}) → ({handle_x}, {end_y})")
                                self.device.swipe(handle_x, handle_y, handle_x, end_y, duration=0.3)
                                handle_found = True
                                break
                    
                    if not handle_found:
                        # Fallback: utiliser des coordonnées approximatives
                        logger.warning("Handle non trouvé, utilisation de coordonnées approximatives")
                        info = self.device.info
                        screen_width = info['displayWidth']
                        screen_height = info['displayHeight']
                        
                        handle_x = screen_width // 2
                        handle_y = int(screen_height * 0.55)  # Position approximative
                        end_y = int(screen_height * 0.95)
                        
                        logger.info(f"Swipe handle approximatif: ({handle_x}, {handle_y}) → ({handle_x}, {end_y})")
                        self.device.swipe(handle_x, handle_y, handle_x, end_y, duration=0.3)
                
                elif method == 'terminate_button':
                    # Chercher et cliquer sur le bouton "Terminé"
                    terminate_selectors = [
                        {'text': 'Terminé'},
                        {'text': 'Done'},
                        {'text': 'Fermer'},
                        {'text': 'Close'},
                        {'description': 'Terminé'},
                        {'description': 'Done'}
                    ]
                    
                    button_found = False
                    for selector in terminate_selectors:
                        element = self.device(**selector)
                        if element.exists():
                            logger.info(f"Bouton trouvé avec sélecteur: {selector}")
                            element.click()
                            button_found = True
                            break
                    
                    if not button_found:
                        logger.warning("Bouton 'Terminé' non trouvé")
                        continue
                
                elif method == 'ok_button':
                    # Chercher et cliquer sur le bouton "OK" pour les popups de limitation
                    ok_selectors = [
                        {'text': 'OK'},
                        {'resourceId': 'com.instagram.android:id/igds_alert_dialog_primary_button'},
                        {'text': 'Ok'},
                        {'description': 'OK'},
                        {'description': 'Ok'}
                    ]
                    
                    button_found = False
                    for selector in ok_selectors:
                        element = self.device(**selector)
                        if element.exists():
                            logger.info(f"Bouton OK trouvé avec sélecteur: {selector}")
                            element.click()
                            button_found = True
                            break
                    
                    if not button_found:
                        logger.warning("Bouton 'OK' non trouvé")
                        continue
                
                elif method == 'tap_background_dimmer':
                    # Cliquer sur le background dimmer pour fermer la bottom sheet
                    dimmer_selectors = [
                        {'resourceId': 'com.instagram.android:id/background_dimmer'},
                        {'description': '@2131954182'}  # Description spécifique du dimmer
                    ]
                    
                    button_found = False
                    for selector in dimmer_selectors:
                        element = self.device(**selector)
                        if element.exists():
                            logger.info(f"Background dimmer trouvé avec sélecteur: {selector}")
                            element.click()
                            button_found = True
                            break
                    
                    if not button_found:
                        logger.warning("Background dimmer non trouvé")
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
            # Vérification optimisée selon le mode
            if self.debug_mode:
                # En mode debug, sauvegarder un dump pour analyse
                dump_path = dump_ui_hierarchy(self.device, "debug_ui/problematic_pages")
                if not dump_path:
                    return False
                
                with open(dump_path, 'r', encoding='utf-8') as f:
                    ui_content = f.read()
            else:
                # En mode production, utiliser directement l'API sans sauvegarder
                try:
                    ui_content = self.device.dump_hierarchy()
                except Exception as e:
                    logger.error(f"Erreur lors du dump UI pour vérification: {e}")
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
