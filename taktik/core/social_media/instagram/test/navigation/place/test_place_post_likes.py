#!/usr/bin/env python3
"""
Script de test pour naviguer vers un lieu, ouvrir un post, et interagir avec ses likers.

Usage:
    python test_place_post_likes.py <place_name> [max_interactions]

Exemple:
    python test_place_post_likes.py "Lausanne, Switzerland" 5
"""

import sys
import time
import random
import argparse
from pathlib import Path
from loguru import logger

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(root_dir))

# Imports relatifs basés sur la structure du projet
from taktik.core.social_media.instagram.actions.core.device import DeviceManager
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.views.place_view import PlaceView
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.social_media.instagram.workflows.management.session import SessionManager
from taktik.core.database import db_service
from taktik.core.social_media.instagram.actions.like.like_profile_posts import LikeProfilePostsManager

# Configuration des logs
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG")

class PlacePostLikesTest:
    """
    Test pour naviguer vers un lieu, collecter ses posts, ouvrir un post,
    ouvrir la liste des likes et interagir avec les personnes ayant liké.
    """
    
    def __init__(self):
        self.device_manager = None
        self.device = None
        self.session_manager = None
        self.navigation_manager = None
        self.place_view = None
        self.scroll_detector = None
        self.posts = []
        self.like_manager = None
        
    def setup(self, place_name: str, max_interactions: int):
        """
        Initialise les composants nécessaires pour le test.
        
        Args:
            place_name: Nom du lieu à rechercher
            max_interactions: Nombre maximum d'interactions
        """
        logger.info(f"🧪 [TEST] Initialisation du test place post likes pour '{place_name}'")
        
        try:
            # Initialiser le gestionnaire de périphérique
            self.device_manager = DeviceManager()
            self.device_manager.connect()
            self.device = self.device_manager.device
            
            if not self.device:
                logger.error("❌ [TEST] Impossible de se connecter à l'appareil")
                return False
                
            logger.success(f"✅ Device connecté: {self.device.serial}")
            
            # Initialiser le gestionnaire de session
            test_config = {
                'session_settings': {
                    'session_duration_minutes': 60,
                    'max_likes': max_interactions,
                    'max_follows': 5
                }
            }
            self.session_manager = SessionManager(test_config)
            logger.success("✅ SessionManager initialisé")
            
            # Initialiser le gestionnaire de navigation
            self.navigation_manager = NavigationManager(self.device)
            logger.success("✅ NavigationManager initialisé")
            
            # Initialiser la vue des lieux
            self.place_view = PlaceView(self.device)
            logger.success("✅ PlaceView initialisé")
            
            # Initialiser le détecteur de fin de scroll
            self.scroll_detector = ScrollEndDetector(self.device)
            logger.success("✅ ScrollEndDetector initialisé")
            
            # Créer un mock automation pour LikeProfilePostsManager
            class MockAutomation:
                def __init__(self, nav_actions):
                    self.nav_actions = nav_actions
                    
            # Initialiser le gestionnaire de likes de posts
            mock_automation = MockAutomation(self.navigation_manager)
            self.like_manager = LikeProfilePostsManager(mock_automation, self.session_manager)
            logger.success("✅ LikeProfilePostsManager initialisé")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors de l'initialisation: {e}")
            return False
    
    def test_navigate_to_place(self, place_name: str):
        """Teste la navigation vers le lieu."""
        logger.info(f"🔍 [TEST] Navigation vers le lieu: '{place_name}'")
        
        try:
            # Navigation vers la recherche
            if not self.navigation_manager.navigate_to_search():
                logger.error("❌ Échec navigation vers recherche")
                return False
            
            # Recherche du lieu
            if not self.navigation_manager.search_place(place_name):
                logger.error(f"❌ Échec recherche lieu '{place_name}'")
                return False
            
            # Clic sur la suggestion
            if not self.navigation_manager.click_search_suggestion(place_name):
                logger.error("❌ Échec clic suggestion")
                return False
            
            # Navigation vers Places tab
            if not self.navigation_manager.navigate_to_places_tab():
                logger.error("❌ Échec navigation Places tab")
                return False
            
            # Sélection du premier lieu
            if not self.navigation_manager.select_first_place_result():
                logger.error("❌ Échec sélection lieu")
                return False
            
            # Navigation vers Top posts
            if not self.place_view.switch_to_top_posts():
                logger.error("❌ Échec navigation Top posts")
                return False
            
            logger.success(f"✅ Navigation vers lieu '{place_name}' réussie")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur navigation lieu: {e}")
            return False
    
    def test_collect_posts(self, max_posts: int = 5):
        """Collecte les posts disponibles dans le lieu."""
        logger.info(f"📦 [TEST] Collecte des posts (max: {max_posts})")
        
        try:
            self.detected_posts = []
            
            def collect_callback(post_element, post_info):
                """Callback pour collecter les informations des posts."""
                try:
                    # Stocker les informations du post
                    post_data = {
                        'element': post_element,
                        'index': post_info.get('index', len(self.detected_posts) + 1),
                        'caption': post_info.get('caption', ''),
                        'location': post_info.get('location', ''),
                        'likes_count': post_info.get('likes_count', 0)
                    }
                    self.detected_posts.append(post_data)
                    
                    logger.info(f"📋 Post {len(self.detected_posts)} collecté: {post_data['caption'][:30]}...")
                    
                    # Continuer la collecte jusqu'au max
                    return len(self.detected_posts) < max_posts
                    
                except Exception as e:
                    logger.error(f"❌ Erreur collecte post: {e}")
                    return True  # Continuer malgré l'erreur
            
            # Utiliser iterate_over_posts pour collecter
            processed_count = self.place_view.iterate_over_posts(
                iteration_callback=collect_callback,
                max_posts=max_posts
            )
            
            logger.success(f"✅ {len(self.detected_posts)} posts collectés sur {processed_count} traités")
            return len(self.detected_posts) > 0
            
        except Exception as e:
            logger.error(f"❌ Erreur collecte posts: {e}")
            return False
    
    def test_open_post(self, post_index: int = 0):
        """Ouvre un post spécifique."""
        logger.info(f"📱 [TEST] Ouverture du post {post_index + 1}")
        
        try:
            if not self.detected_posts or post_index >= len(self.detected_posts):
                logger.error(f"❌ Post {post_index + 1} non disponible")
                return False
            
            post_data = self.detected_posts[post_index]
            post_element = post_data['element']
            
            # Cliquer sur le post pour l'ouvrir
            post_element.click()
            time.sleep(3)  # Attendre l'ouverture
            
            logger.success(f"✅ Post {post_index + 1} ouvert")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur ouverture post: {e}")
            return False
    
    def test_open_likes_list(self):
        """Ouvre la liste des likes d'un post."""
        logger.info("❤️ [TEST] Ouverture de la liste des likes")
        
        try:
            # Attendre que le post soit complètement chargé
            time.sleep(2)
            
            # Essayer de trouver le bouton des likes avec différentes méthodes
            
            # Méthode 1: Recherche par pattern de nombre de likes (13.5K, 1.2M, 847, etc.)
            try:
                import re
                # Chercher tous les TextView avec du texte
                text_elements = self.device(className="android.widget.TextView")
                if text_elements.exists():
                    for i in range(text_elements.count):
                        try:
                            element = text_elements[i]
                            text = element.get_text() if hasattr(element, 'get_text') else str(element.text) if hasattr(element, 'text') else ""
                            
                            # Pattern pour détecter les nombres de likes (13.5K, 1.2M, 847, etc.)
                            if re.match(r'^\d+(?:\.\d+)?[KMkmBb]?$', text.strip()):
                                logger.info(f"❤️ Clic sur le nombre de likes: {text}")
                                element.click()
                                time.sleep(2)
                                return True
                        except Exception as elem_e:
                            continue
            except Exception as e:
                logger.debug(f"Recherche par pattern de nombres échouée: {e}")
            
            # Méthode 2: Recherche par texte de nombres sans pattern
            try:
                # Chercher des textes qui sont des nombres purs
                for potential_count in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    # Chercher les éléments qui commencent par un chiffre
                    elements = self.device(textStartsWith=potential_count)
                    if elements.exists():
                        for i in range(min(elements.count, 3)):  # Limiter à 3 pour éviter les faux positifs
                            try:
                                element = elements[i]
                                text = element.get_text() if hasattr(element, 'get_text') else str(element.text) if hasattr(element, 'text') else ""
                                # Vérifier que c'est bien un compteur de likes (pas trop long, contient des chiffres)
                                if len(text) < 10 and any(c.isdigit() for c in text) and not any(word in text.lower() for word in ['comment', 'share', 'send']):
                                    logger.info(f"❤️ Clic sur le nombre de likes (méthode 2): {text}")
                                    element.click()
                                    time.sleep(2)
                                    return True
                            except Exception as elem_e:
                                continue
            except Exception as e:
                logger.debug(f"Recherche par nombres échouée: {e}")
            
            # Méthode 3: Recherche par ID de ressource
            try:
                resource_ids = ['com.instagram.android:id/row_feed_button_like', 'com.instagram.android:id/like_button']
                for res_id in resource_ids:
                    elements = self.device(resourceId=res_id)
                    if elements.exists():
                        logger.info(f"❤️ Clic sur le bouton des likes avec ID: {res_id}")
                        elements.click()
                        time.sleep(2)
                        return True
            except Exception as e:
                logger.debug(f"Recherche par ID échouée: {e}")
            
            logger.error("❌ Impossible d'ouvrir la liste des likes")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur ouverture likes: {e}")
            return False
    
    def test_interact_with_likers(self, max_interactions):
        """Interagit avec les personnes qui ont liké."""
        logger.info(f"👥 [TEST] Interaction avec les likers (max: {max_interactions})")
        
        try:
            # Attendre que la liste des likes soit chargée
            time.sleep(2)
            
            # Rechercher des éléments de profil utilisateur
            interactions_count = 0
            processed_users = set()
            
            # Méthode 1: Recherche par description
            try:
                profile_elements = self.device(descriptionContains="Profile picture")
                if profile_elements.exists() and profile_elements.count > 0:
                    logger.info(f"👥 {profile_elements.count} profils trouvés par description")
                    
                    # Limiter le nombre d'interactions
                    for i in range(min(profile_elements.count, max_interactions)):
                        if interactions_count >= max_interactions:
                            break
                            
                        try:
                            # Cliquer sur le profil
                            profile_elements[i].click()
                            time.sleep(random.uniform(1, 2))
                            
                            # Simuler une interaction (visite de profil)
                            logger.info(f"👤 Interaction {interactions_count + 1}: Visite profil")
                            time.sleep(random.uniform(1, 2))
                            
                            # Revenir à la liste des likes
                            self.device.press('back')
                            time.sleep(1)
                            
                            interactions_count += 1
                        except Exception as e:
                            logger.debug(f"Erreur interaction profil {i}: {e}")
                            continue
            except Exception as e:
                logger.debug(f"Recherche par description échouée: {e}")
            
            # Méthode 2: Recherche par ID de ressource
            if interactions_count == 0:
                try:
                    resource_ids = ['com.instagram.android:id/row_user_imageview', 'com.instagram.android:id/profile_image']
                    for res_id in resource_ids:
                        profile_elements = self.device(resourceId=res_id)
                        if profile_elements.exists() and profile_elements.count > 0:
                            logger.info(f"👥 {profile_elements.count} profils trouvés par ID: {res_id}")
                            
                            # Limiter le nombre d'interactions
                            for i in range(min(profile_elements.count, max_interactions)):
                                if interactions_count >= max_interactions:
                                    break
                                    
                                try:
                                    # Cliquer sur le profil
                                    profile_elements[i].click()
                                    time.sleep(random.uniform(1, 2))
                                    
                                    # Simuler une interaction (visite de profil)
                                    logger.info(f"👤 Interaction {interactions_count + 1}: Visite profil")
                                    time.sleep(random.uniform(1, 2))
                                    
                                    # Revenir à la liste des likes
                                    self.device.press('back')
                                    time.sleep(1)
                                    
                                    interactions_count += 1
                                except Exception as e:
                                    logger.debug(f"Erreur interaction profil {i}: {e}")
                                    continue
                            
                            if interactions_count > 0:
                                break
                except Exception as e:
                    logger.debug(f"Recherche par ID échouée: {e}")
            
            logger.success(f"✅ {interactions_count} interactions réalisées")
            return interactions_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erreur interactions likers: {e}")
            return False
    
    def cleanup(self):
        """Nettoie les ressources utilisées pendant le test."""
        logger.info("🧹 [TEST] Nettoyage des ressources")
        
        try:
            # Retourner à l'accueil Instagram
            if self.device_manager and self.device:
                for _ in range(3):
                    self.device.press('back')
                    time.sleep(1)
                    
            # Fermer la connexion appareil
            if self.device_manager:
                try:
                    if hasattr(self.device_manager, 'disconnect'):
                        self.device_manager.disconnect()
                    elif hasattr(self.device_manager, 'cleanup'):
                        self.device_manager.cleanup()
                    else:
                        logger.warning("Aucune méthode de déconnexion trouvée")
                except Exception as cleanup_e:
                    logger.warning(f"Erreur lors de la déconnexion: {cleanup_e}")
                logger.success("✅ Device nettoyé")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage: {e}")

def main():
    """Fonction principale du test."""
    parser = argparse.ArgumentParser(description="Test d'interaction avec les likers d'un post de lieu")
    parser.add_argument("place_name", help="Nom du lieu à rechercher")
    parser.add_argument("max_interactions", nargs='?', type=int, default=5, 
                       help="Nombre maximum d'interactions (défaut: 5)")
    
    args = parser.parse_args()
    
    logger.info(f"🚀 [TEST] Démarrage du test place post likes pour '{args.place_name}' (max: {args.max_interactions})")
    
    test = PlacePostLikesTest()
    
    try:
        # Étapes du test
        test_steps = [
            ("Initialisation", lambda: test.setup(args.place_name, args.max_interactions)),
            ("Navigation vers lieu", lambda: test.test_navigate_to_place(args.place_name)),
            ("Collecte des posts", lambda: test.test_collect_posts(5)),
            ("Ouverture d'un post", lambda: test.test_open_post(0)),
            ("Ouverture liste likes", lambda: test.test_open_likes_list()),
            ("Interaction avec likers", lambda: test.test_interact_with_likers(args.max_interactions))
        ]
        
        success_count = 0
        
        for step_name, step_func in test_steps:
            logger.info(f"🧪 [TEST] Exécution: {step_name}")
            
            if step_func():
                logger.success(f"✅ {step_name}: RÉUSSI")
                success_count += 1
                time.sleep(2)  # Délai entre les étapes
            else:
                logger.error(f"❌ {step_name}: ÉCHEC")
        
        # Résumé
        total_steps = len(test_steps)
        logger.info(f"📊 [RÉSUMÉ] {success_count}/{total_steps} tests réussis")
        
        if success_count == total_steps:
            logger.success("🎉 [TEST] Tous les tests ont réussi !")
            return True
        else:
            logger.error(f"❌ [TEST] Test terminé avec {total_steps - success_count} échecs")
            return False
            
    except Exception as e:
        logger.error(f"❌ [TEST] Erreur critique: {e}")
        return False
        
    finally:
        test.cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
