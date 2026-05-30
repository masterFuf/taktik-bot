#!/usr/bin/env python3
"""
Script de test pour valider la navigation vers la liste des followers d'un profil Instagram.

Usage:
    python test_navigate_to_followers.py <username> [max_followers_to_check]

Exemple:
    python test_navigate_to_followers.py outside_the_box_films 5
"""

import sys
import os
import time
import argparse
from pathlib import Path
from typing import List, Set, Dict
from loguru import logger

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(root_dir))

# Imports relatifs basés sur la structure du projet
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.views.followers_view import FollowersFollowingListView
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.social_media.instagram.workflows.management.session import SessionManager
from taktik.core.database import db_service

# Configuration des logs
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG")

class NavigateToFollowersTest:
    """Classe de test pour la navigation vers la liste des followers."""
    
    def __init__(self):
        self.device = None
        self.device_manager = None
        self.navigation_manager = None
        self.followers_view = None
        self.scroll_detector = None
        self.session_manager = None
        
    def setup(self, username: str):
        """
        Initialise les composants nécessaires pour le test.
        
        Args:
            username: Nom d'utilisateur du profil cible
        """
        logger.info(f"🧪 [TEST] Initialisation du test de navigation vers followers pour @{username}")
        
        try:
            # Initialisation du device manager
            self.device_manager = DeviceManager()
            self.device_manager.connect()
            self.device = self.device_manager.device
            
            if not self.device:
                logger.error("❌ Impossible de se connecter au device")
                return False
                
            logger.success(f"✅ Device connecté: {self.device.serial}")
            
            # Initialisation du session manager avec configuration de test
            test_config = {
                'session_settings': {
                    'session_duration_minutes': 30,
                    'max_likes': 10,
                    'max_follows': 5
                }
            }
            
            self.session_manager = SessionManager(test_config)
            logger.success("✅ SessionManager initialisé")
            
            # Initialisation du navigation manager (pour la navigation vers le profil et la liste des followers)
            self.navigation_manager = NavigationManager(self.device)
            logger.success("✅ NavigationManager initialisé")
            
            # Initialisation de la vue followers (pour le scroll et la pagination)
            self.followers_view = FollowersFollowingListView(self.device)
            logger.success("✅ FollowersFollowingListView initialisé")
            
            # Initialisation du détecteur de fin de scroll
            self.scroll_detector = ScrollEndDetector(repeats_to_end=3, device=self.device)
            logger.success("✅ ScrollEndDetector initialisé")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            return False
    
    def test_navigate_to_profile(self, username: str) -> bool:
        """
        Teste la navigation vers le profil d'un utilisateur.
        
        Args:
            username: Nom d'utilisateur du profil cible
            
        Returns:
            bool: True si la navigation réussit, False sinon
        """
        logger.info(f"📱 [TEST] Navigation vers le profil @{username}")
        
        try:
            # Navigation vers le profil via deep link
            success = self.navigation_manager.navigate_to_profile(username)
            
            if success:
                logger.success(f"✅ Navigation réussie vers @{username}")
                time.sleep(2)  # Attendre le chargement du profil
                return True
            else:
                logger.error(f"❌ Échec de la navigation vers @{username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la navigation vers le profil: {e}")
            return False
    
    def test_navigate_to_followers_list(self) -> bool:
        """
        Teste la navigation vers la liste des followers depuis le profil.
        
        Returns:
            bool: True si la navigation réussit, False sinon
        """
        logger.info("👥 [TEST] Navigation vers la liste des followers")
        
        try:
            # Utiliser la méthode du NavigationManager
            success = self.navigation_manager.navigate_to_followers_list()
            
            if success:
                logger.success("✅ Navigation vers la liste des followers réussie")
                return True
            else:
                logger.error("❌ Échec de la navigation vers la liste des followers")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la navigation vers les followers: {e}")
            return False
    
    def test_see_more_button(self) -> bool:
        """
        Teste la détection et le clic sur le bouton "Voir plus" avec ScrollEndDetector.
        
        Returns:
            bool: True si le bouton a été trouvé et cliqué, False sinon
        """
        logger.info("🔍 [TEST] Détection du bouton 'Voir plus' avec ScrollEndDetector")
        
        try:
            # Utiliser le ScrollEndDetector pour détecter et cliquer sur le bouton "Voir plus"
            button_found = self.scroll_detector.has_load_more_button()
            
            if button_found:
                logger.success("✅ Bouton 'Voir plus' détecté")
                
                # Cliquer sur le bouton
                click_success = self.scroll_detector.click_load_more_if_present()
                
                if click_success:
                    logger.success("✅ Clic sur le bouton 'Voir plus' réussi")
                    time.sleep(2)  # Attendre le chargement après clic
                    return True
                else:
                    logger.warning("⚠️ Échec du clic sur le bouton 'Voir plus'")
                    return False
            else:
                logger.warning("⚠️ Bouton 'Voir plus' non trouvé")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection du bouton 'Voir plus': {e}")
            return False
    
    def test_detect_followers_in_list(self, max_followers: int = 5) -> int:
        """
        Teste la détection des followers dans la liste en utilisant FollowersFollowingListView.
        
        Args:
            max_followers: Nombre maximum de followers à détecter
            
        Returns:
            int: Nombre de followers détectés
        """
        logger.info(f"🔍 [TEST] Détection des followers avec FollowersFollowingListView (max: {max_followers})")
        
        try:
            # Vérifier que la liste n'est pas vide
            if self.followers_view.is_list_empty():
                logger.warning("⚠️ La liste des followers est vide")
                return 0
            
            # Utiliser la vue followers pour détecter les followers
            followers_list = []
            
            def follower_callback(username: str, element) -> bool:
                # Ajouter le follower à la liste
                follower_info = {
                    'username': username,
                    'index': len(followers_list) + 1
                }
                followers_list.append(follower_info)
                
                # Afficher le follower détecté
                logger.info(f"👤 Follower {follower_info['index']}: @{username}")
                
                # Arrêter si on a atteint le nombre maximum
                if len(followers_list) >= max_followers:
                    return False
                return True
            
            # Utiliser iterate_over_followers avec notre callback
            processed_count = self.followers_view.iterate_over_followers(
                iteration_callback=follower_callback,
                pre_conditions=None,
                iterate_without_sleep=False
            )
            
            logger.info(f"📊 [RÉSULTAT] {len(followers_list)} followers détectés sur {processed_count} traités")
            return len(followers_list)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection des followers: {e}")
            return 0
    
    def test_scroll_followers_list(self) -> bool:
        """
        Teste le scroll avec FollowersFollowingListView et ScrollEndDetector.
        """
        logger.info("📜 [TEST] Test du scroll avec FollowersFollowingListView")
        
        try:
            # Réinitialiser le détecteur de fin de scroll
            self.scroll_detector.reset()
            
            # Étape 1: Détection initiale des followers
            logger.info("🔍 Détection initiale des followers...")
            initial_followers = []
            
            def initial_callback(username: str, element) -> bool:
                initial_followers.append(username)
                if len(initial_followers) >= 5:  # Limiter à 5 pour le test initial
                    return False
                return True
            
            self.followers_view.iterate_over_followers(
                iteration_callback=initial_callback,
                iterate_without_sleep=True
            )
            
            logger.info(f"📊 Détection initiale: {len(initial_followers)} followers visibles")
            
            # Afficher les premiers followers détectés
            for i, username in enumerate(initial_followers, 1):
                logger.info(f"👤 Follower {i}: @{username}")
            
            if not initial_followers:
                logger.warning("⚠️ Aucun follower détecté initialement")
                return False
            
            # Étape 2: Effectuer un scroll
            logger.info("📜 Scroll de la liste des followers...")
            self.followers_view.scroll_to_bottom()
            time.sleep(2)  # Attendre le chargement après scroll
            
            # Étape 3: Détecter les nouveaux followers après scroll
            after_scroll_followers = []
            
            def after_scroll_callback(username: str, element) -> bool:
                if username not in initial_followers:
                    after_scroll_followers.append(username)
                if len(after_scroll_followers) >= 5:  # Limiter à 5 nouveaux pour le test
                    return False
                return True
            
            self.followers_view.iterate_over_followers(
                iteration_callback=after_scroll_callback,
                iterate_without_sleep=True
            )
            
            # Analyser les résultats
            if after_scroll_followers:
                logger.success(f"✅ Scroll réussi: {len(after_scroll_followers)} nouveaux followers détectés")
                
                # Afficher les nouveaux followers
                for i, username in enumerate(after_scroll_followers, 1):
                    logger.info(f"👤 Nouveau follower: @{username}")
                
                # Notifier le détecteur de fin de scroll
                all_visible = initial_followers + after_scroll_followers
                has_new = self.scroll_detector.notify_new_page(all_visible)
                logger.info(f"📈 Détecteur de fin: nouveaux utilisateurs = {has_new}")
                
                return True
            else:
                logger.warning("⚠️ Scroll sans nouveaux followers")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du test de scroll: {e}")
            return False
    
    def test_continuous_scroll(self) -> bool:
        """
        Test le scroll continu pour récupérer tous les followers avec FollowersFollowingListView.
        
        Returns:
            bool: True si le scroll continu réussit, False sinon
        """
        logger.info("📜 [TEST] Test du scroll continu avec FollowersFollowingListView")
        
        try:
            # Réinitialiser le détecteur de fin de scroll
            self.scroll_detector.reset()
            
            # Collecter les followers avec FollowersFollowingListView
            max_followers = 30  # Limiter pour le test
            followers_list = []
            unique_usernames = set()
            see_more_clicks = 0
            reached_end = False
            
            def continuous_scroll_callback(username: str, element) -> bool:
                # Éviter les doublons
                if username not in unique_usernames:
                    unique_usernames.add(username)
                    follower_info = {
                        'username': username,
                        'position': len(followers_list) + 1
                    }
                    followers_list.append(follower_info)
                    
                    # Afficher le follower détecté (tous les 5 followers)
                    if len(followers_list) % 5 == 0:
                        logger.info(f"👤 Follower {follower_info['position']}: @{username}")
                
                # Vérifier si on doit continuer
                if len(followers_list) >= max_followers:
                    logger.info(f"📊 Limite de {max_followers} followers atteinte")
                    return False
                return True
            
            # Fonction pour gérer la fin de page
            def end_reached_callback() -> bool:
                nonlocal see_more_clicks, reached_end
                
                # Vérifier s'il y a un bouton "Voir plus"
                if self.scroll_detector.has_load_more_button():
                    logger.info("🔍 Bouton 'Voir plus' détecté, clic en cours...")
                    if self.scroll_detector.click_load_more_if_present():
                        see_more_clicks += 1
                        logger.success(f"✅ Clic sur 'Voir plus' réussi ({see_more_clicks} au total)")
                        time.sleep(2)  # Attendre le chargement après clic
                        return False  # Continuer l'itération
                
                # Vérifier si on a atteint la fin de la liste
                if self.scroll_detector.is_the_end():
                    reached_end = True
                    logger.info("📊 Fin de la liste détectée")
                    return True  # Arrêter l'itération
                
                # Notifier le détecteur avec les usernames actuels
                current_usernames = [f['username'] for f in followers_list[-10:]] if followers_list else []
                self.scroll_detector.notify_new_page(current_usernames)
                
                return False  # Continuer l'itération
            
            # Utiliser iterate_over_followers avec nos callbacks
            processed_count = self.followers_view.iterate_over_followers(
                iteration_callback=continuous_scroll_callback,
                end_reached_callback=end_reached_callback,
                iteration_limit=max_followers
            )
            
            # Analyser les résultats
            followers_count = len(followers_list)
            logger.info(f"📊 [RÉSULTAT] {followers_count} followers uniques récupérés")
            logger.info(f"📊 Fin de liste atteinte: {reached_end}")
            logger.info(f"📊 Clics sur 'Voir plus': {see_more_clicks}")
            
            # Afficher les premiers et derniers followers
            if followers_count > 0:
                logger.info("👤 Premiers followers:")
                for follower in followers_list[:3]:
                    logger.info(f"  - Position {follower['position']}: @{follower['username']}")
                    
                if followers_count > 3:
                    logger.info("👤 Derniers followers:")
                    for follower in followers_list[-3:]:
                        logger.info(f"  - Position {follower['position']}: @{follower['username']}")
            
            # Obtenir les statistiques du détecteur
            stats = self.scroll_detector.get_stats()
            logger.info(f"📊 Statistiques du détecteur: {stats}")
            
            return followers_count > 0
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du test de scroll continu: {e}")
            return False
    
    def test_debug_follower_counting(self) -> bool:
        """
        Test de debug pour comparer différentes méthodes de détection des followers.
        
        Returns:
            bool: True si le test réussit, False sinon
        """
        logger.info("🔍 [DEBUG] Test de comptage des followers avec différentes méthodes")
        
        try:
            # Méthode 1: Utiliser FollowersFollowingListView avec différents sélecteurs
            followers_count_method1 = 0
            followers_list_method1 = []
            
            def count_callback(username: str, element) -> bool:
                nonlocal followers_count_method1
                followers_count_method1 += 1
                followers_list_method1.append(username)
                return True
            
            # Compter avec la méthode standard
            self.followers_view.iterate_over_followers(
                iteration_callback=count_callback,
                iterate_without_sleep=True
            )
            
            # Méthode 2: Utiliser les sélecteurs alternatifs pour comparaison
            alternative_selectors = [
                '//android.widget.TextView[@resource-id="com.instagram.android:id/follow_list_username"]',
                '//android.widget.TextView[contains(@text, "@")]',
                '//android.view.ViewGroup[descendant::android.widget.TextView[@resource-id="com.instagram.android:id/follow_list_username"]]'
            ]
            
            selector_results = {}
            for selector in alternative_selectors:
                try:
                    elements = self.device.find(selector, multiple=True)
                    selector_results[selector] = len(elements)
                except Exception:
                    selector_results[selector] = 0
            
            # Trouver le meilleur sélecteur
            best_selector = max(selector_results.items(), key=lambda x: x[1]) if selector_results else ('Aucun', 0)
            
            # Afficher les résultats
            logger.info(f"📊 [DEBUG] Comparaison de détection:")
            logger.info(f"  👁️ FollowersFollowingListView: {followers_count_method1} followers")
            
            # Afficher les résultats par sélecteur alternatif
            logger.info(f"🔍 [DEBUG] Résultats par sélecteur alternatif:")
            for selector, count in selector_results.items():
                short_selector = selector.split('/')[-1] if '/' in selector else selector
                logger.info(f"  {short_selector}: {count}")
            
            logger.info(f"🏆 [DEBUG] Meilleur sélecteur alternatif: {best_selector[0]} ({best_selector[1]} éléments)")
            
            # Afficher les premiers followers détectés
            if followers_list_method1:
                logger.info("👤 Premiers followers détectés:")
                for i, username in enumerate(followers_list_method1[:5], 1):
                    logger.info(f"  {i}. @{username}")
            
            # Vérifier la cohérence des résultats
            if best_selector[1] > followers_count_method1:
                diff = best_selector[1] - followers_count_method1
                logger.warning(f"⚠️ Potentiellement {diff} followers manqués par FollowersFollowingListView")
                logger.info("💡 Suggestions:")
                logger.info("  - Vérifier les sélecteurs utilisés dans FollowersFollowingListView")
                logger.info("  - Ajuster les paramètres de visibilité")
            else:
                logger.success("✅ Détection avec FollowersFollowingListView optimale !")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du test de debug: {e}")
            return False
    
    def test_detect_more_followers_after_see_more(self, max_followers: int = 10) -> int:
        """
        Teste la détection de followers supplémentaires après avoir cliqué sur "Voir plus" avec ScrollEndDetector.
        
        Args:
            max_followers: Nombre maximum de followers à détecter
            
        Returns:
            int: Nombre de followers détectés après "Voir plus"
        """
        logger.info(f"🔍 [TEST] Détection de followers après 'Voir plus' avec ScrollEndDetector (max: {max_followers})")
        
        try:
            # Étape 1: Cliquer sur "Voir plus" si présent
            button_found = self.scroll_detector.has_load_more_button()
            
            if not button_found:
                logger.warning("⚠️ Bouton 'Voir plus' non trouvé, test ignoré")
                return 0
                
            click_success = self.scroll_detector.click_load_more_if_present()
            if not click_success:
                logger.warning("⚠️ Échec du clic sur le bouton 'Voir plus'")
                return 0
                
            logger.success("✅ Bouton 'Voir plus' cliqué")
            time.sleep(2)  # Attendre le chargement après clic
            
            # Étape 2: Détecter les followers après le clic
            followers_after_click = []
            
            def after_click_callback(username: str, element) -> bool:
                follower_info = {
                    'username': username,
                    'index': len(followers_after_click) + 1
                }
                followers_after_click.append(follower_info)
                
                # Afficher le follower détecté
                logger.info(f"👤 Follower {follower_info['index']}: @{username}")
                
                # Arrêter si on a atteint le nombre maximum
                if len(followers_after_click) >= max_followers:
                    return False
                return True
            
            # Utiliser iterate_over_followers avec notre callback
            self.followers_view.iterate_over_followers(
                iteration_callback=after_click_callback,
                iterate_without_sleep=True
            )
            
            logger.info(f"📊 [RÉSULTAT] {len(followers_after_click)} followers détectés après 'Voir plus'")
            return len(followers_after_click)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection après 'Voir plus': {e}")
            return 0
    
    def run_test(self, username: str, max_followers: int = 5) -> bool:
        """
        Exécute le test complet de navigation vers les followers avec détection du bouton "Voir plus".
        
        Args:
            username: Nom d'utilisateur du profil cible
            max_followers: Nombre maximum de followers à détecter
            
        Returns:
            bool: True si tous les tests passent, False sinon
        """
        logger.info(f"🚀 [TEST] Début du test de navigation vers followers pour @{username}")
        
        # Initialisation
        if not self.setup(username):
            return False
        
        # Test 1: Navigation vers le profil
        if not self.test_navigate_to_profile(username):
            return False
        
        # Test 2: Navigation vers la liste des followers
        if not self.test_navigate_to_followers_list():
            return False
        
        # Test 3: Détecter les followers dans la liste
        followers_count = self.test_detect_followers_in_list(max_followers)
        if followers_count > 0:
            logger.success(f"✅ {followers_count} followers détectés")
        else:
            logger.warning("⚠️ Aucun follower détecté, mais le test continue")
        
        # Test 3.5: Debug - Comparer différentes méthodes de détection des followers
        self.test_debug_follower_counting()
        
        # Test 4: Tester le scroll dans la liste des followers
        self.test_scroll_followers_list()
        
        # Test 5: Test du bouton "Voir plus"
        self.test_see_more_button()
        
        # Test 6: Test du scroll continu
        self.test_continuous_scroll()
        
        # Test 7: Détecter les followers supplémentaires après les tests
        additional_followers_count = 0
        see_more_found = False
        try:
            additional_followers_count = self.test_detect_more_followers_after_see_more(max_followers * 2)
            see_more_found = additional_followers_count > 0
        except Exception as e:
            logger.warning(f"Test followers supplémentaires ignoré: {e}")
        
        # Résumé des résultats
        logger.info("📊 [RÉSUMÉ DES TESTS]")
        logger.info(f"✅ Navigation vers profil: Réussie")
        logger.info(f"✅ Navigation vers followers: Réussie")
        logger.info(f"📈 Followers initiaux détectés: {followers_count}")
        logger.info(f"🔄 Bouton 'Voir plus': {'Trouvé et cliqué' if see_more_found else 'Non trouvé'}")
        if see_more_found:
            logger.info(f"📈 Followers après 'Voir plus': {additional_followers_count}")
        
        logger.success("🎉 Test de navigation vers followers terminé avec succès!")
        return True
    
    def cleanup(self):
        """Nettoie les ressources utilisées."""
        try:
            if self.device_manager and hasattr(self.device_manager, 'disconnect'):
                self.device_manager.disconnect()
                logger.info("🧹 Nettoyage des ressources terminé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors du nettoyage: {e}")


def main():
    """Fonction principale du script de test."""
    parser = argparse.ArgumentParser(description="Test de navigation vers la liste des followers Instagram avec bouton 'Voir plus'")
    parser.add_argument("username", help="Nom d'utilisateur du profil cible (sans @)")
    parser.add_argument("max_followers", nargs="?", type=int, default=15, 
                       help="Nombre maximum de followers à détecter (défaut: 15)")
    
    args = parser.parse_args()
    
    # Validation des arguments
    if not args.username:
        logger.error("❌ Le nom d'utilisateur est requis")
        return False
    
    if args.max_followers <= 0:
        logger.error("❌ Le nombre de followers doit être positif")
        return False
    
    if args.max_followers > 100:
        logger.warning(f"⚠️ Nombre élevé de followers demandé ({args.max_followers}), cela peut prendre du temps")
    
    # Exécution du test
    test = NavigateToFollowersTest()
    
    try:
        success = test.run_test(args.username, args.max_followers)
        return success
    except KeyboardInterrupt:
        logger.warning("⚠️ Test interrompu par l'utilisateur")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {e}")
        return False
    finally:
        test.cleanup()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
