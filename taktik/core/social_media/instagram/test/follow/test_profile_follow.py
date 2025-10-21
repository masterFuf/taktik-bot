#!/usr/bin/env python3
"""
Script de test pour valider la fonctionnalité de follow d'un profil Instagram.

Usage:
    python test_profile_follow.py <username>

Exemple:
    python test_profile_follow.py outside_the_box_films
"""

import sys
import os
import time
import argparse
from pathlib import Path
from loguru import logger

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(root_dir))

# Imports relatifs basés sur la structure du projet
from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.follower.follower_interaction_manager import FollowerInteractionManager
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.core.session_manager import SessionManager
from taktik.core.database import db_service

# Configuration des logs
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG")

class ProfileFollowTest:
    """Classe de test pour le follow de profil."""
    
    def __init__(self):
        self.device = None
        self.device_manager = None
        self.navigation_manager = None
        self.follow_manager = None
        self.session_manager = None
        
    def setup(self, username: str):
        """
        Initialise les composants nécessaires pour le test.
        
        Args:
            username: Nom d'utilisateur du profil à tester
        """
        logger.info(f"🧪 [TEST] Initialisation du test de follow pour @{username}")
        
        try:
            # Initialiser le gestionnaire d'appareil
            self.device_manager = DeviceManager()
            self.device_manager.connect()
            self.device = self.device_manager.device
            
            if not self.device:
                logger.error("❌ [TEST] Impossible de se connecter à l'appareil")
                return False
                
            logger.info(f"✅ [TEST] Device connecté: {self.device.serial}")

            
            # Initialiser le gestionnaire de session avec une configuration de test
            test_config = {
                'session_settings': {
                    'session_duration_minutes': 30,
                    'max_likes': 10,
                    'max_follows': 5
                }
            }
            self.session_manager = SessionManager(test_config)
            
            # Initialiser le gestionnaire de navigation
            self.navigation_manager = NavigationManager(self.device)
            
            # Créer un objet mock automation pour FollowerInteractionManager
            class MockAutomation:
                def __init__(self, device, nav_actions, session_manager):
                    self.device = device
                    self.nav_actions = nav_actions
                    self.session_manager = session_manager
            
            mock_automation = MockAutomation(self.device, self.navigation_manager, self.session_manager)
            
            # Initialiser le gestionnaire de follow avec l'automation mock
            self.follow_manager = FollowerInteractionManager(mock_automation, self.session_manager)
            
            logger.info("✅ [TEST] Composants initialisés avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors de l'initialisation: {e}")
            return False
    
    def test_profile_follow(self, username: str):
        """
        Teste la fonctionnalité de follow sur un profil.
        
        Args:
            username: Nom d'utilisateur du profil à tester
            
        Returns:
            bool: True si le test réussit, False sinon
        """
        logger.info(f"🎯 [TEST] Début du test de follow pour @{username}")
        
        try:
            # Navigation vers le profil
            logger.info(f"📍 [TEST] Navigation vers le profil @{username}")
            navigation_success = self.navigation_manager.navigate_to_profile(username)
            
            if not navigation_success:
                logger.error(f"❌ [TEST] Échec de la navigation vers @{username}")
                return False
                
            logger.success(f"✅ [TEST] Navigation réussie vers @{username}")
            
            # Attendre que le profil se charge
            time.sleep(2)
            
            # Effectuer le follow
            logger.info(f"👥 [TEST] Début du processus de follow")
            
            # Vérifier d'abord si on suit déjà ce profil
            is_already_following = self._is_already_following()
            
            if is_already_following:
                logger.info(f"ℹ️ [TEST] Profil @{username} déjà suivi")
                return True
            
            # Effectuer le follow
            follow_success = self._perform_follow()
            
            if follow_success:
                logger.success(f"✅ [TEST] Follow effectué avec succès pour @{username}")
                return True
            else:
                logger.error(f"❌ [TEST] Échec du follow pour @{username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors du test de follow: {e}")
            return False
    
    def _is_already_following(self) -> bool:
        """
        Vérifie si on suit déjà ce profil.
        
        Returns:
            bool: True si on suit déjà le profil, False sinon
        """
        logger.info("🔍 [TEST] Vérification si le profil est déjà suivi...")
        
        # Sélecteurs pour détecter si on suit déjà le profil
        following_selectors = [
            '//android.widget.Button[contains(@text, "Suivi")]',
            '//android.widget.Button[contains(@text, "Following")]',
            '//android.widget.Button[contains(@text, "Abonné")]',
            '//*[contains(@resource-id, "profile_header_follow_button") and contains(@text, "Suivi")]',
            '//*[contains(@resource-id, "profile_header_follow_button") and contains(@text, "Following")]',
        ]
        
        for selector in following_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    logger.info(f"✅ [TEST] Profil déjà suivi détecté avec le sélecteur: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"Erreur lors de la vérification du sélecteur {selector}: {str(e)}")
        
        logger.info("ℹ️ [TEST] Le profil n'est pas encore suivi")
        return False
    
    def _perform_follow(self) -> bool:
        """
        Effectue l'action de follow.
        
        Returns:
            bool: True si le follow a réussi, False sinon
        """
        logger.info("👥 [TEST] Recherche du bouton follow...")
        
        # Sélecteurs pour le bouton follow
        follow_selectors = [
            '//android.widget.Button[contains(@text, "Suivre")]',
            '//android.widget.Button[contains(@text, "Follow")]',
            '//android.widget.Button[contains(@text, "S\'abonner")]',
            '//*[contains(@resource-id, "profile_header_follow_button")]',
            '//*[contains(@resource-id, "follow_button")]',
        ]
        
        for selector in follow_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    logger.info(f"🎯 [TEST] Bouton follow trouvé avec le sélecteur: {selector}")
                    element.click()
                    time.sleep(2)
                    
                    # Vérifier que le follow a bien fonctionné
                    if self._is_already_following():
                        logger.success("✅ [TEST] Follow effectué avec succès")
                        return True
                    else:
                        logger.warning("⚠️ [TEST] Follow cliqué mais statut non confirmé")
                        return False
                        
            except Exception as e:
                logger.debug(f"Erreur lors du clic sur le sélecteur {selector}: {str(e)}")
        
        logger.error("❌ [TEST] Aucun bouton follow trouvé")
        return False
    
    def cleanup(self):
        """Nettoie les ressources utilisées."""
        logger.info("🧹 [TEST] Nettoyage des ressources")
        
        try:
            if self.device_manager:
                # Fermer la connexion au device si nécessaire
                pass
        except Exception as e:
            logger.debug(f"Erreur lors du nettoyage: {e}")
        
        logger.info("✅ [TEST] Nettoyage terminé")


def main():
    """Fonction principale du script de test."""
    parser = argparse.ArgumentParser(description="Test de follow d'un profil Instagram")
    parser.add_argument("username", help="Nom d'utilisateur du profil à tester")
    
    args = parser.parse_args()
    username = args.username
    
    logger.info("=" * 80)
    logger.info(f"🧪 DÉBUT DU TEST - Follow profil @{username}")
    logger.info("=" * 80)
    
    # Initialiser le test
    test = ProfileFollowTest()
    
    try:
        # Setup
        if not test.setup(username):
            logger.error("❌ [TEST] Échec de l'initialisation")
            return False
        
        # Exécuter le test
        success = test.test_profile_follow(username)
        
        if success:
            logger.success(f"✅ TEST RÉUSSI - Follow @{username}")
        else:
            logger.error(f"❌ TEST ÉCHOUÉ - Follow @{username}")
            
        return success
        
    except KeyboardInterrupt:
        logger.warning("⚠️ [TEST] Test interrompu par l'utilisateur")
        return False
    except Exception as e:
        logger.error(f"❌ [TEST] Erreur inattendue: {e}")
        return False
    finally:
        # Cleanup
        test.cleanup()
        
        logger.info("=" * 80)
        if 'success' in locals():
            if success:
                logger.info(f"✅ TEST RÉUSSI - Follow @{username}")
            else:
                logger.info(f"❌ TEST ÉCHOUÉ - Follow @{username}")
        logger.info("=" * 80)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
