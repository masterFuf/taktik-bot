#!/usr/bin/env python3
"""
Script de test pour valider la fonctionnalité de like des posts d'un profil Instagram.

Usage:
    python test_profile_likes.py <username> [max_likes]

Exemple:
    python test_profile_likes.py outside_the_box_films 2
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
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.actions.like.like_profile_posts import LikeProfilePostsManager
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.core.session_manager import SessionManager
from taktik.core.database import db_service

# Configuration des logs
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG")

class ProfileLikeTest:
    """Classe de test pour les likes de posts de profil."""
    
    def __init__(self):
        self.device = None
        self.navigation_manager = None
        self.like_manager = None
        self.session_manager = None
        
    def setup(self, username: str):
        """
        Initialise les composants nécessaires pour le test.
        
        Args:
            username: Nom d'utilisateur du profil à tester
        """
        logger.info(f"🧪 [TEST] Initialisation du test de likes pour @{username}")
        
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
            
            # Créer un objet mock automation pour LikeProfilePostsManager
            class MockAutomation:
                def __init__(self, nav_actions):
                    self.nav_actions = nav_actions
            
            mock_automation = MockAutomation(self.navigation_manager)
            
            # Initialiser le gestionnaire de likes avec l'automation mock
            self.like_manager = LikeProfilePostsManager(self.device, self.session_manager, mock_automation)
            
            logger.info("✅ [TEST] Composants initialisés avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors de l'initialisation: {e}")
            return False
    
    def test_profile_likes(self, username: str, max_likes: int = 2):
        """
        Teste la fonctionnalité de like sur les posts d'un profil.
        
        Args:
            username: Nom d'utilisateur du profil à tester
            max_likes: Nombre maximum de likes à effectuer
            
        Returns:
            bool: True si le test réussit, False sinon
        """
        logger.info(f"🎯 [TEST] Début du test de likes pour @{username}")
        
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
            
            # Effectuer les likes
            logger.info(f"❤️ [TEST] Début du processus de like (max: {max_likes})")
            
            stats = self.like_manager.like_profile_posts(
                username=username,
                max_posts=9,  # Analyser jusqu'à 9 posts
                like_posts=True,
                max_likes=max_likes,
                scroll_attempts=2
            )
            
            # Analyser les résultats
            logger.info(f"📊 [TEST] Statistiques des likes:")
            logger.info(f"  - Posts traités: {stats.get('posts_processed', 0)}")
            logger.info(f"  - Posts likés: {stats.get('posts_liked', 0)}")
            logger.info(f"  - Erreurs: {stats.get('errors', 0)}")
            
            if stats.get('posts_liked', 0) > 0:
                logger.success(f"✅ [TEST] Likes effectués avec succès pour @{username}")
                return True
            elif stats.get('errors', 0) > 0:
                logger.warning(f"⚠️ [TEST] Erreurs détectées lors du processus de like")
                return False
            else:
                logger.info(f"ℹ️ [TEST] Aucun nouveau like effectué (posts déjà likés ou autres raisons)")
                return True
                
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors du test de likes: {e}")
            return False
    
    def cleanup(self):
        """Nettoie les ressources utilisées."""
        logger.info("🧹 [TEST] Nettoyage des ressources")
        
        try:
            if self.device:
                # Retourner à l'écran d'accueil
                self.device.press("home")
                time.sleep(1)
                
        except Exception as e:
            logger.warning(f"⚠️ [TEST] Erreur lors du nettoyage: {e}")
            
        logger.info("✅ [TEST] Nettoyage terminé")

def main():
    """Fonction principale du script de test."""
    if len(sys.argv) < 2:
        print("Usage: python test_profile_likes.py <username> [max_likes]")
        print("Exemple: python test_profile_likes.py outside_the_box_films 2")
        sys.exit(1)
    
    username = sys.argv[1]
    max_likes = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    
    # Créer l'instance de test
    test_instance = ProfileLikeTest()
    
    try:
        logger.info("=" * 80)
        logger.info(f"🧪 DÉBUT DU TEST - Likes profil @{username}")
        logger.info("=" * 80)
        
        # Initialisation
        if not test_instance.setup(username):
            logger.error("❌ [TEST] Échec de l'initialisation")
            return False
        
        # Exécution du test
        success = test_instance.test_profile_likes(username, max_likes)
        
        if success:
            logger.success(f"✅ TEST RÉUSSI - Likes @{username}")
        else:
            logger.error(f"❌ TEST ÉCHOUÉ - Likes @{username}")
            
        return success
        
    except KeyboardInterrupt:
        logger.warning("⚠️ [TEST] Test interrompu par l'utilisateur")
        return False
        
    except Exception as e:
        logger.error(f"❌ [TEST] Erreur inattendue: {e}")
        return False
        
    finally:
        # Nettoyage
        test_instance.cleanup()
        
        logger.info("=" * 80)
        if 'success' in locals():
            result = "✅ TEST RÉUSSI" if success else "❌ TEST ÉCHOUÉ"
            logger.info(f"{result} - Likes @{username}")
        logger.info("=" * 80)

def run():
    """Point d'entrée pour l'exécution du test."""
    return main()

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
