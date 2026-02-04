"""
Détecteur et gestionnaire des pages problématiques TikTok qui interrompent le workflow.
"""
import time
from typing import Optional, Dict, Any, Tuple
from loguru import logger
from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot


class TikTokProblematicPageDetector:
    """
    Détecte et ferme automatiquement les pages problématiques TikTok.
    Gère les popups, bannières de notification, et autres interruptions.
    """
    
    def __init__(self, device, debug_mode: bool = False):
        """
        Initialise le détecteur.
        
        Args:
            device: Instance uiautomator2 device
            debug_mode: Si True, sauvegarde les dumps et screenshots pour debug
        """
        self.device = device
        self.debug_mode = debug_mode
        
        # Statistiques
        self.stats = {
            'popups_detected': 0,
            'popups_closed': 0,
            'failed_closes': 0,
        }
        
        # Patterns de détection des pages problématiques TikTok
        self.detection_patterns = {
            'link_email_popup': {
                'indicators': [
                    'text="Link email"',
                    'linking your Android email',
                ],
                'close_selectors': [
                    {'text': 'Not now'},
                    {'text': 'Pas maintenant'},
                ],
                'description': 'Link email popup',
            },
            'follow_friends_popup': {
                'indicators': [
                    'text="Follow your friends"',
                    'text="Suivez vos amis"',
                    'resource-id="com.zhiliaoapp.musically:id/dga"',
                ],
                'close_selectors': [
                    {'description': 'Close'},
                    {'resourceId': 'com.zhiliaoapp.musically:id/dga', 'description': 'Close'},
                ],
                'description': 'Follow your friends popup',
            },
            'collections_popup': {
                'indicators': [
                    'text="Create shared collections"',
                    'text="Créer des collections partagées"',
                ],
                'close_selectors': [
                    {'text': 'Not now'},
                    {'text': 'Pas maintenant'},
                    {'description': 'Close'},
                ],
                'description': 'Collections popup',
            },
            'notification_banner': {
                'indicators': [
                    'sent you new messages',
                    'sent you a message',
                    'vous a envoyé',
                ],
                'close_selectors': [],  # Use back button
                'use_back': True,
                'description': 'Notification banner',
            },
            'inbox_page': {
                'indicators': [
                    'text="Inbox"',
                    'text="New followers"',
                    'text="System notifications"',
                ],
                'close_selectors': [],  # Use back button
                'use_back': True,
                'description': 'Inbox page (accidental navigation)',
            },
            'system_popup_input_method': {
                'indicators': [
                    'text="Sélectionnez le mode de saisie"',
                    'text="Select input method"',
                    'text="Choose input method"',
                ],
                'close_selectors': [],  # Use back button
                'use_back': True,
                'description': 'System input method popup',
            },
            'permission_popup': {
                'indicators': [
                    'resource-id="com.android.permissioncontroller:id/permission_deny_button"',
                    'resource-id="com.android.packageinstaller:id/permission_deny_button"',
                    'text="REFUSER"',
                    'text="DENY"',
                ],
                'close_selectors': [
                    {'text': 'REFUSER'},
                    {'text': 'Refuser'},
                    {'text': 'Ne pas autoriser'},
                    {'text': 'DENY'},
                    {'text': 'Deny'},
                    {'text': "Don't allow"},
                ],
                'description': 'Permission popup',
            },
            'promo_banner': {
                'indicators': [
                    'resource-id="com.zhiliaoapp.musically:id/faf"',
                    'Hatch a Streak Pet',
                ],
                'close_selectors': [
                    {'resourceId': 'com.zhiliaoapp.musically:id/fad'},
                    {'resourceId': 'com.zhiliaoapp.musically:id/fac', 'description': 'Close'},
                ],
                'description': 'Promo banner',
            },
            'suggestion_page': {
                'indicators': [
                    'text="Swipe up to skip"',
                    'text="Not interested"',
                ],
                'close_selectors': [
                    {'text': 'Not interested'},
                ],
                'description': 'Suggestion page',
            },
        }
    
    def _get_ui_content(self, context: str = "detection") -> Optional[str]:
        """Get UI content based on debug mode."""
        if self.debug_mode:
            dump_path = dump_ui_hierarchy(self.device, "debug_ui/tiktok_problematic_pages")
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
    
    def _is_page_detected(self, ui_content: str, indicators: list) -> bool:
        """Check if any indicator is present in UI content."""
        for indicator in indicators:
            if indicator.lower() in ui_content.lower():
                return True
        return False
    
    def _click_button(self, selectors: list, button_name: str) -> bool:
        """Try to click a button from a list of selectors."""
        logger.debug(f"Recherche du bouton '{button_name}' avec {len(selectors)} sélecteurs")
        for selector in selectors:
            try:
                logger.debug(f"Essai du sélecteur: {selector}")
                element = self.device(**selector)
                if element.exists(timeout=1):
                    logger.info(f"Bouton {button_name} trouvé avec sélecteur: {selector}")
                    element.click()
                    time.sleep(0.5)
                    return True
            except Exception as e:
                logger.debug(f"Erreur avec sélecteur {selector}: {e}")
        logger.warning(f"Bouton '{button_name}' non trouvé après {len(selectors)} tentatives")
        return False
    
    def _press_back(self) -> bool:
        """Press back button."""
        try:
            self.device.press("back")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'appui sur back: {e}")
            return False
    
    def detect_and_handle_problematic_pages(self) -> Dict[str, Any]:
        """
        Détecte et ferme automatiquement les pages problématiques TikTok.
        
        Returns:
            dict: {
                'detected': bool,  # True si une page problématique a été détectée
                'closed': bool,    # True si la page a été fermée avec succès
                'page_type': str   # Type de page détectée (si applicable)
            }
        """
        result = {
            'detected': False,
            'closed': False,
            'page_type': None
        }
        
        try:
            logger.info("🔍 Vérification des pages problématiques TikTok...")
            
            ui_content = self._get_ui_content("detection")
            if not ui_content:
                return result
            
            # Vérifier chaque type de page problématique
            for page_type, config in self.detection_patterns.items():
                if self._is_page_detected(ui_content, config['indicators']):
                    logger.warning(f"🚨 Page problématique TikTok détectée: {config['description']}")
                    self.stats['popups_detected'] += 1
                    result['detected'] = True
                    result['page_type'] = page_type
                    
                    # Tenter de fermer
                    closed = False
                    
                    if config.get('use_back', False):
                        # Use back button
                        closed = self._press_back()
                    elif config.get('close_selectors'):
                        # Use close button selectors
                        closed = self._click_button(config['close_selectors'], config['description'])
                    
                    if closed:
                        logger.info(f"✅ {config['description']} fermée avec succès")
                        self.stats['popups_closed'] += 1
                        result['closed'] = True
                    else:
                        logger.warning(f"⚠️ Impossible de fermer {config['description']}")
                        self.stats['failed_closes'] += 1
                        # Try back as fallback
                        if self._press_back():
                            result['closed'] = True
                    
                    return result
            
            logger.info("✅ Aucune page problématique TikTok détectée")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la détection: {e}")
            return result
    
    def get_stats(self) -> Dict[str, int]:
        """Return detection statistics."""
        return self.stats.copy()
