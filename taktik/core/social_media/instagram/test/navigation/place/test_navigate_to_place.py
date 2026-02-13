#!/usr/bin/env python3
"""
Script de test pour valider la navigation vers l'onglet "Places" et l'interaction avec les posts d'un lieu Instagram.

Usage:
    python test_navigate_to_place.py <place_name> [max_posts]

Exemple:
    python test_navigate_to_place.py "Lausanne, Switzerland" 10
    python test_navigate_to_place.py "Paris" 15

Ce test effectue :
1. Recherche d'un lieu dans la barre de recherche Instagram
2. Navigation vers l'onglet "Places"
3. Sélection du premier résultat de lieu
4. Navigation dans les posts du lieu (Top/Récents)
5. Interaction avec les posts disponibles
"""

import sys
import argparse
import time
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(root_dir))

from loguru import logger
from taktik.core.social_media.instagram.actions.core.device import DeviceManager
from taktik.core.social_media.instagram.workflows.management.session import SessionManager
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.views.place_view import PlaceView
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector


class NavigateToPlaceTest:
    """Test de navigation vers l'onglet Places et interaction avec les posts d'un lieu."""
    
    def __init__(self):
        self.device_manager = None
        self.session_manager = None
        self.navigation_manager = None
        self.place_view = None
        self.scroll_detector = None
        
    def setup(self, place_name: str):
        """
        Initialise les composants nécessaires pour le test.
        
        Args:
            place_name: Nom du lieu à rechercher
        """
        logger.info(f"🧪 [TEST] Initialisation du test de navigation vers place pour '{place_name}'")
        
        # Initialiser le gestionnaire de périphérique
        self.device_manager = DeviceManager()
        self.device_manager.connect()
        logger.success(f"✅ Device connecté: {self.device_manager.device_id}")
        
        # Initialiser le gestionnaire de session
        test_config = {
            'session_settings': {
                'session_duration_minutes': 30,
                'max_likes': 10,
                'max_follows': 5
            }
        }
        self.session_manager = SessionManager(test_config)
        logger.success("✅ SessionManager initialisé")
        
        # Initialiser le gestionnaire de navigation
        self.navigation_manager = NavigationManager(self.device_manager.device)
        logger.success("✅ NavigationManager initialisé")
        
        # Initialiser la vue des lieux
        self.place_view = PlaceView(self.device_manager.device)
        logger.success("✅ PlaceView initialisé")
        
        # Initialiser le détecteur de fin de scroll
        self.scroll_detector = ScrollEndDetector(device=self.device_manager.device)
        logger.success("✅ ScrollEndDetector initialisé")
        
    def test_navigate_to_search(self) -> bool:
        """
        Teste la navigation vers la barre de recherche.
        
        Returns:
            bool: True si la navigation réussit, False sinon
        """
        logger.info("🔍 [TEST] Test de navigation vers la barre de recherche")
        
        try:
            # Naviguer vers la page de recherche
            if self.navigation_manager.navigate_to_search():
                logger.success("✅ Navigation vers la recherche réussie")
                time.sleep(2)  # Attendre le chargement
                return True
            else:
                logger.error("❌ Impossible de naviguer vers la recherche")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la navigation vers la recherche: {e}")
            return False
    
    def test_search_place(self, place_name: str) -> bool:
        """
        Teste la recherche d'un lieu et la navigation vers l'onglet Places.
        
        Args:
            place_name: Nom du lieu à rechercher
            
        Returns:
            bool: True si la recherche réussit, False sinon
        """
        logger.info(f"🏙️ [TEST] Test de recherche de lieu: '{place_name}'")
        
        try:
            # Effectuer la recherche
            if self.navigation_manager.search_place(place_name):
                logger.success(f"✅ Recherche de lieu '{place_name}' réussie")
                time.sleep(2)  # Attendre les résultats
                
                # Cliquer sur la suggestion de recherche (premier résultat avec loupe)
                if self.navigation_manager.click_search_suggestion(place_name):
                    logger.success("✅ Clic sur la suggestion de recherche réussi")
                    time.sleep(2)  # Attendre le chargement de la page avec les onglets
                    
                    # Naviguer vers l'onglet Places
                    if self.navigation_manager.navigate_to_places_tab():
                        logger.success("✅ Navigation vers l'onglet Places réussie")
                        time.sleep(2)  # Attendre le chargement
                        return True
                    else:
                        logger.error("❌ Impossible de naviguer vers l'onglet Places")
                        return False
                else:
                    logger.error("❌ Impossible de cliquer sur la suggestion de recherche")
                    return False
            else:
                logger.error(f"❌ Impossible de rechercher le lieu '{place_name}'")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la recherche de lieu: {e}")
            return False
    
    def test_select_first_place_result(self) -> bool:
        """
        Teste la sélection du premier résultat de lieu.
        
        Returns:
            bool: True si la sélection réussit, False sinon
        """
        logger.info("🎯 [TEST] Test de sélection du premier résultat de lieu")
        
        try:
            if self.navigation_manager.select_first_place_result():
                logger.success("✅ Sélection du premier résultat de lieu réussie")
                time.sleep(3)  # Attendre le chargement de la page du lieu
                return True
            else:
                logger.error("❌ Impossible de sélectionner le premier résultat")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sélection du résultat: {e}")
            return False
    
    def test_navigate_to_top_posts(self) -> bool:
        """
        Teste la navigation vers les posts "Top" du lieu.
        
        Returns:
            bool: True si la navigation réussit, False sinon
        """
        logger.info("🔝 [TEST] Test de navigation vers les posts Top")
        
        try:
            if self.place_view.switch_to_top_posts():
                logger.success("✅ Navigation vers les posts Top réussie")
                time.sleep(2)  # Attendre le chargement
                return True
            else:
                logger.error("❌ Impossible de naviguer vers les posts Top")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la navigation vers Top: {e}")
            return False
    
    def test_navigate_to_recent_posts(self) -> bool:
        """
        Teste la navigation vers les posts "Recent" du lieu.
        
        Returns:
            bool: True si la navigation réussit, False sinon
        """
        logger.info("📅 [TEST] Test de navigation vers les posts Recent")
        
        try:
            if self.place_view.switch_to_recent_posts():
                logger.success("✅ Navigation vers les posts Recent réussie")
                time.sleep(2)  # Attendre le chargement
                return True
            else:
                logger.error("❌ Impossible de naviguer vers les posts Recent")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la navigation vers Recent: {e}")
            return False
    
    def test_detect_posts_in_place(self, max_posts: int = 10) -> int:
        """
        Teste la détection des posts dans la page du lieu.
        
        Args:
            max_posts: Nombre maximum de posts à détecter
            
        Returns:
            int: Nombre de posts détectés
        """
        logger.info(f"🎬 [TEST] Test de détection des posts (max: {max_posts})")
        
        try:
            posts_detected = 0
            posts_list = []
            
            def post_callback(post_element, post_info) -> bool:
                nonlocal posts_detected
                posts_detected += 1
                posts_list.append(post_info)
                
                if posts_detected % 3 == 0:
                    logger.info(f"🎬 Post {posts_detected}: {post_info.get('caption', 'Sans légende')[:50]}...")
                
                return posts_detected < max_posts
            
            processed_count = self.place_view.iterate_over_posts(
                iteration_callback=post_callback
            )
            
            logger.info(f"📊 [RÉSULTAT] {posts_detected} posts détectés sur {processed_count} traités")
            
            if posts_detected > 0:
                logger.info("🎬 Premiers posts:")
                for i, post in enumerate(posts_list[:3]):
                    logger.info(f"  - Post {i+1}: {post.get('caption', 'Sans légende')[:30]}...")
            
            return posts_detected
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection des posts: {e}")
            return 0
    
    def test_scroll_place_posts(self) -> bool:
        """
        Teste le scroll dans les posts du lieu.
        
        Returns:
            bool: True si le scroll réussit, False sinon
        """
        logger.info("📜 [TEST] Test du scroll dans les posts du lieu")
        
        try:
            self.scroll_detector.reset()
            
            posts_before_scroll = self.place_view.count_visible_posts()
            logger.info(f"📊 Posts visibles avant scroll: {posts_before_scroll}")
            
            # Effectuer un scroll
            self.place_view.scroll_down()
            time.sleep(2)  # Attendre le chargement
            
            posts_after_scroll = self.place_view.count_visible_posts()
            logger.info(f"📊 Posts visibles après scroll: {posts_after_scroll}")
            
            if posts_after_scroll > posts_before_scroll:
                logger.success("✅ Scroll réussi - nouveaux posts détectés")
                return True
            else:
                logger.warning("⚠️ Scroll effectué mais pas de nouveaux posts détectés")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du scroll: {e}")
            return False
    
    def cleanup(self):
        """
        Nettoie les ressources après le test.
        """
        logger.info("🧹 [TEST] Nettoyage des ressources")
        
        try:
            if self.device_manager:
                # Utiliser la méthode correcte pour nettoyer le device
                if hasattr(self.device_manager, 'cleanup'):
                    self.device_manager.cleanup()
                    logger.info("✅ Device nettoyé avec cleanup()")
                elif hasattr(self.device_manager, 'disconnect'):
                    self.device_manager.disconnect()
                    logger.info("✅ Device déconnecté avec disconnect()")
                else:
                    logger.warning("⚠️ Aucune méthode de nettoyage trouvée pour le device")
        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage: {e}")


def main():
    """Point d'entrée principal du script de test."""
    parser = argparse.ArgumentParser(
        description="Test de navigation vers l'onglet Places et interaction avec les posts d'un lieu"
    )
    parser.add_argument("place_name", help="Nom du lieu à rechercher")
    parser.add_argument("max_posts", type=int, nargs="?", default=10, 
                        help="Nombre maximum de posts à détecter (défaut: 10)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Mode verbeux pour plus de détails")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.add(sys.stdout, level="DEBUG")
    
    place_name = args.place_name
    max_posts = args.max_posts
    
    logger.info(f"🚀 [TEST] Démarrage du test de navigation place pour '{place_name}' (max: {max_posts})")
    
    test_runner = NavigateToPlaceTest()
    
    try:
        # Initialisation
        test_runner.setup(place_name)
        
        # Tests séquentiels
        tests = [
            ("Navigation vers recherche", lambda: test_runner.test_navigate_to_search()),
            ("Recherche de lieu", lambda: test_runner.test_search_place(place_name)),
            ("Sélection du lieu", lambda: test_runner.test_select_first_place_result()),
            ("Navigation vers Top", lambda: test_runner.test_navigate_to_top_posts()),
            ("Détection posts Top", lambda: test_runner.test_detect_posts_in_place(max_posts) > 0),
            ("Scroll dans les posts", lambda: test_runner.test_scroll_place_posts()),
            ("Navigation vers Recent", lambda: test_runner.test_navigate_to_recent_posts()),
            ("Détection posts Recent", lambda: test_runner.test_detect_posts_in_place(5) > 0),
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"🧪 [TEST] Exécution: {test_name}")
            try:
                result = test_func()
                results.append((test_name, result))
                if result:
                    logger.success(f"✅ {test_name}: RÉUSSI")
                else:
                    logger.error(f"❌ {test_name}: ÉCHEC")
            except Exception as e:
                logger.error(f"❌ {test_name}: ERREUR - {e}")
                results.append((test_name, False))
        
        # Résumé final
        success_count = sum(1 for _, result in results if result)
        total_count = len(results)
        
        logger.info(f"📊 [RÉSUMÉ] {success_count}/{total_count} tests réussis")
        
        if success_count == total_count:
            logger.success("✅ [TEST] Test de navigation place terminé avec succès")
        else:
            logger.error(f"❌ [TEST] Test terminé avec {total_count - success_count} échecs")
            
    except Exception as e:
        logger.error(f"❌ Erreur critique lors du test: {e}")
    finally:
        test_runner.cleanup()


if __name__ == "__main__":
    main()
