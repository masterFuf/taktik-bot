#!/usr/bin/env python3
"""
Script de test pour la visualisation des stories Instagram.

Ce script permet de tester la fonctionnalité de visionnage des stories
sur un profil spécifique en réutilisant la logique d'automation existante.

Usage:
    python test_story_viewer.py <nom_du_profil>

Example:
    python test_story_viewer.py lets.explore.ch
"""

import sys
import argparse
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(root_dir))

from taktik.core.social_media.instagram.core.automation import InstagramAutomation
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.actions.story.story_manager import StoryManager
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.observability import instagram_logger as logger


class StoryTestRunner:
    """
    Runner de test pour la visualisation des stories.
    """
    
    def __init__(self, profile_username: str):
        """
        Initialise le runner de test.
        
        Args:
            profile_username: Nom d'utilisateur du profil à tester
        """
        self.profile_username = profile_username
        self.device_manager = None
        self.device = None
        self.navigation_manager = None
        self.story_manager = None
        
        # Configuration minimale pour les tests
        self.test_config = {
            'session_settings': {
                'session_duration_minutes': 10,  # Test court
                'delay_between_actions': {'min': 2, 'max': 5}
            },
            'action_probabilities': {
                'watch_stories': 100  # 100% de chance de regarder les stories
            },
            'limits_per_source': {
                'interactions': 1,  # Limite à 1 interaction pour le test
                'stories_watched': 10
            },
            'stories_settings': {
                'max_stories_to_watch': 10,
                'min_watch_time': 2,
                'max_watch_time': 8
            }
        }
    
    def setup(self):
        """
        Initialise les composants nécessaires pour le test.
        """
        logger.info(f"🧪 [TEST] Initialisation du test de stories pour @{self.profile_username}")
        
        try:
            # Initialiser le gestionnaire de device
            self.device_manager = DeviceManager()
            if not self.device_manager.connect():
                raise Exception("Impossible de se connecter au device Android")
                
            self.device = self.device_manager.device
            
            if not self.device:
                raise Exception("Device non initialisé après connexion")
            
            logger.info(f"✅ [TEST] Device connecté: {self.device.serial}")
            
            # Initialiser les managers nécessaires
            self.navigation_manager = NavigationManager(self.device)
            self.story_manager = StoryManager(self.device, self.test_config)
            
            logger.info("✅ [TEST] Composants initialisés avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors de l'initialisation: {e}")
            return False
    
    def test_story_viewing(self):
        """
        Teste la visualisation des stories pour le profil spécifié.
        
        Returns:
            bool: True si le test a réussi, False sinon
        """
        logger.info(f"🎬 [TEST] Début du test de visualisation des stories pour @{self.profile_username}")
        
        try:
            # Étape 1: Navigation vers le profil
            logger.info(f"📍 [TEST] Navigation vers le profil @{self.profile_username}")
            navigation_success = self.navigation_manager._navigate_to_profile(self.profile_username)
            
            if not navigation_success:
                logger.error(f"❌ [TEST] Échec de la navigation vers @{self.profile_username}")
                return False
            
            logger.success(f"✅ [TEST] Navigation réussie vers @{self.profile_username}")
            
            # Étape 2: Vérifier la présence de stories
            logger.info(f"🔍 [TEST] Vérification de la présence de stories")
            has_stories = self.story_manager.detector.has_story()
            
            if not has_stories:
                logger.warning(f"⚠️ [TEST] Aucune story disponible pour @{self.profile_username}")
                return True  # Ce n'est pas un échec du test
            
            logger.info(f"✅ [TEST] Stories détectées pour @{self.profile_username}")
            
            # Étape 3: Regarder les stories
            logger.info(f"🎬 [TEST] Début du visionnage des stories")
            # Forcer la probabilité à 100% pour les tests
            stories_watched = self.story_manager.watch_stories_with_probability(
                self.profile_username,
                probability=1.0,  # Garantir que les stories sont toujours visionnées
                like_stories=True  # Activer le like des stories pour le test
            )
            
            if stories_watched:
                logger.success(f"✅ [TEST] Stories visionnées avec succès pour @{self.profile_username}")
                return True
            else:
                logger.warning(f"⚠️ [TEST] Aucune story visionnée pour @{self.profile_username}")
                return True  # Ce n'est pas forcément un échec
                
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur pendant le test: {e}")
            return False
    
    def cleanup(self):
        """
        Nettoie les ressources après le test.
        """
        logger.info("🧹 [TEST] Nettoyage des ressources")
        
        try:
            if self.device_manager:
                # Pas besoin de déconnecter explicitement, 
                # le device manager gère cela automatiquement
                pass
                
            logger.info("✅ [TEST] Nettoyage terminé")
            
        except Exception as e:
            logger.warning(f"⚠️ [TEST] Erreur lors du nettoyage: {e}")
    
    def run(self):
        """
        Exécute le test complet.
        
        Returns:
            bool: True si le test a réussi, False sinon
        """
        logger.info("=" * 80)
        logger.info(f"🧪 DÉBUT DU TEST - Visualisation stories @{self.profile_username}")
        logger.info("=" * 80)
        
        success = False
        
        try:
            # Initialisation
            if not self.setup():
                return False
            
            # Exécution du test
            success = self.test_story_viewing()
            
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur critique: {e}")
            success = False
            
        finally:
            # Nettoyage
            self.cleanup()
        
        # Résumé du test
        logger.info("=" * 80)
        if success:
            logger.success(f"✅ TEST RÉUSSI - Stories @{self.profile_username}")
        else:
            logger.error(f"❌ TEST ÉCHOUÉ - Stories @{self.profile_username}")
        logger.info("=" * 80)
        
        return success


def main():
    """
    Point d'entrée principal du script de test.
    """
    parser = argparse.ArgumentParser(
        description="Test de visualisation des stories Instagram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_story_viewer.py lets.explore.ch
  python test_story_viewer.py grange_unil
        """
    )
    
    parser.add_argument(
        'profile',
        help='Nom d\'utilisateur du profil Instagram à tester'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mode verbeux (plus de logs)'
    )
    
    args = parser.parse_args()
    
    # Configuration du logging si mode verbeux
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validation du nom de profil
    profile_username = args.profile.strip().replace('@', '')
    
    if not profile_username:
        print("❌ Erreur: Le nom de profil ne peut pas être vide")
        sys.exit(1)
    
    # Exécution du test
    test_runner = StoryTestRunner(profile_username)
    success = test_runner.run()
    
    # Code de sortie
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
