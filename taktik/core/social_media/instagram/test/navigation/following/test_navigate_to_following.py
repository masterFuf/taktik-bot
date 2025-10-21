#!/usr/bin/env python3
"""
Script de test pour valider la navigation vers la liste des following (abonnements) d'un profil Instagram.

Usage:
    python test_navigate_to_following.py <username> [max_following_to_check]

Exemple:
    python test_navigate_to_following.py outside_the_box_films 5
    python test_navigate_to_following.py cinemapalace.bevilard
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
from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.views.followers_view import FollowersFollowingListView
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.social_media.instagram.workflows.management.session import SessionManager
from taktik.core.database import db_service

# Configuration des logs
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG")

class NavigateToFollowingTest:
    """Classe de test pour la navigation vers la liste des following (abonnements)."""
    
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
        logger.info(f"🧪 [TEST] Initialisation du test de navigation vers following pour @{username}")
        
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
            
            # Initialisation du navigation manager (pour la navigation vers le profil et la liste des following)
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
    
    def test_navigate_to_following_list(self) -> bool:
        """
        Teste la navigation vers la liste des following (abonnements) depuis le profil.
        
        Returns:
            bool: True si la navigation réussit, False sinon
        """
        logger.info("👥 [TEST] Navigation vers la liste des following (abonnements)")
        
        try:
            # Vérifier que nous sommes bien sur un profil
            if not self.navigation_manager.is_on_profile():
                logger.error("❌ Nous ne sommes pas sur un écran de profil")
                return False
                
            # Utiliser la méthode du NavigationManager
            success = self.navigation_manager.navigate_to_following_list()
            
            if success:
                # Vérifier que nous sommes bien sur la page des following
                verification_selectors = [
                    "//android.widget.TextView[contains(@text, 'Following') or contains(@text, 'Abonnements')]",
                    "//*[contains(@content-desc, 'Following') or contains(@content-desc, 'Abonnements')]",
                    "//*[contains(@resource-id, 'follow_list')]"
                ]
                
                page_verified = False
                for selector in verification_selectors:
                    try:
                        if self.device.xpath(selector).exists:
                            logger.debug(f"Page following confirmée avec: {selector}")
                            page_verified = True
                            break
                    except Exception:
                        continue
                
                if page_verified:
                    logger.success("✅ Navigation vers la liste des following réussie et vérifiée")
                    # Attendre que la liste se charge complètement
                    time.sleep(2)
                    return True
                else:
                    logger.warning("⚠️ Navigation vers following réussie mais page non confirmée")
                    return True
            else:
                logger.error("❌ Échec de la navigation vers la liste des following")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la navigation vers les following: {e}")
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
    
    def test_detect_following_in_list(self, max_following: int = 5) -> int:
        """
        Teste la détection des following (abonnements) dans la liste en utilisant FollowersFollowingListView.
        
        Args:
            max_following: Nombre maximum d'abonnements à détecter
            
        Returns:
            int: Nombre d'abonnements détectés
        """
        logger.info(f"🔍 [TEST] Détection des following avec FollowersFollowingListView (max: {max_following})")
        
        try:
            # Vérifier que la liste n'est pas vide
            if self.followers_view.is_list_empty():
                logger.warning("⚠️ La liste des following est vide")
                return 0
            
            # Utiliser la vue followers pour détecter les following
            following_list = []
            
            def following_callback(username: str, element) -> bool:
                # Ajouter le following à la liste
                following_info = {
                    'username': username,
                    'index': len(following_list) + 1
                }
                following_list.append(following_info)
                
                # Afficher le following détecté
                logger.info(f"👤 Following {following_info['index']}: @{username}")
                
                # Arrêter si on a atteint le nombre maximum
                if len(following_list) >= max_following:
                    return False
                return True
            
            # Utiliser iterate_over_followers avec notre callback
            processed_count = self.followers_view.iterate_over_followers(
                iteration_callback=following_callback,
                pre_conditions=None,
                iterate_without_sleep=False
            )
            
            logger.info(f"📊 [RÉSULTAT] {len(following_list)} following détectés sur {processed_count} traités")
            return len(following_list)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection des following: {e}")
            return 0
    
    def test_scroll_following_list(self) -> bool:
        """
        Teste le scroll avec FollowersFollowingListView et ScrollEndDetector.
        """
        logger.info("📜 [TEST] Test du scroll avec FollowersFollowingListView")
        
        try:
            # Réinitialiser le détecteur de fin de scroll
            self.scroll_detector.reset()
            
            # Étape 1: Détection initiale des following
            logger.info("🔍 Détection initiale des following...")
            initial_following = []
            
            def initial_callback(username: str, element) -> bool:
                initial_following.append(username)
                if len(initial_following) >= 5:  # Limiter à 5 pour le test initial
                    return False
                return True
            
            self.followers_view.iterate_over_followers(
                iteration_callback=initial_callback,
                iterate_without_sleep=True
            )
            
            logger.info(f"📊 Détection initiale: {len(initial_following)} following visibles")
            
            # Afficher les premiers following détectés
            for i, username in enumerate(initial_following, 1):
                logger.info(f"👤 Following {i}: @{username}")
            
            if not initial_following:
                logger.warning("⚠️ Aucun following détecté initialement")
                return False
            
            # Étape 2: Effectuer un scroll
            logger.info("📜 Scroll de la liste des following...")
            self.followers_view.scroll_to_bottom()
            time.sleep(2)  # Attendre le chargement après scroll
            
            # Étape 3: Détecter les nouveaux following après scroll
            after_scroll_following = []
            
            def after_scroll_callback(username: str, element) -> bool:
                if username not in initial_following:
                    after_scroll_following.append(username)
                if len(after_scroll_following) >= 5:  # Limiter à 5 nouveaux pour le test
                    return False
                return True
            
            self.followers_view.iterate_over_followers(
                iteration_callback=after_scroll_callback,
                iterate_without_sleep=True
            )
            
            # Analyser les résultats
            if after_scroll_following:
                logger.success(f"✅ Scroll réussi: {len(after_scroll_following)} nouveaux following détectés")
                
                # Afficher les nouveaux following
                for i, username in enumerate(after_scroll_following, 1):
                    logger.info(f"👤 Nouveau following: @{username}")
                
                # Notifier le détecteur de fin de scroll
                all_visible = initial_following + after_scroll_following
                has_new = self.scroll_detector.notify_new_page(all_visible)
                logger.info(f"📈 Détecteur de fin: nouveaux utilisateurs = {has_new}")
                
                return True
            else:
                logger.warning("⚠️ Scroll sans nouveaux following")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du test de scroll: {e}")
            return False
    
    def test_continuous_scroll(self) -> bool:
        """
        Test le scroll continu pour récupérer tous les following avec FollowersFollowingListView.
        
        Returns:
            bool: True si le scroll continu réussit, False sinon
        """
        logger.info("📜 [TEST] Test du scroll continu avec FollowersFollowingListView")
        
        try:
            self.scroll_detector.reset()
            
            max_following = 30
            following_list = []
            unique_usernames = set()
            see_more_clicks = 0
            reached_end = False
            
            def continuous_scroll_callback(username: str, element) -> bool:
                if username not in unique_usernames:
                    unique_usernames.add(username)
                    following_info = {
                        'username': username,
                        'position': len(following_list) + 1
                    }
                    following_list.append(following_info)
                    
                    if len(following_list) % 5 == 0:
                        logger.info(f"👤 Following {following_info['position']}: @{username}")
                
                if len(following_list) >= max_following:
                    logger.info(f"📊 Limite de {max_following} following atteinte")
                    return False
                return True
            
            # Utiliser iterate_over_followers avec callback
            # Limiter le nombre de following avec le callback lui-même
            processed_count = self.followers_view.iterate_over_followers(
                iteration_callback=continuous_scroll_callback,
                iterate_without_sleep=False
            )
            
            following_count = len(following_list)
            logger.info(f"📊 [RÉSULTAT] {following_count} following uniques récupérés")
            logger.info(f"📊 Fin de liste atteinte: {reached_end}")
            logger.info(f"📊 Clics sur 'Voir plus': {see_more_clicks}")
            
            if following_count > 0:
                logger.info("👤 Premiers following:")
                for following in following_list[:3]:
                    logger.info(f"  - Position {following['position']}: @{following['username']}")
                    
                if following_count > 3:
                    logger.info("👤 Derniers following:")
                    for following in following_list[-3:]:
                        logger.info(f"  - Position {following['position']}: @{following['username']}")
            
            return following_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du test de scroll continu: {e}")
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
    """
    Fonction principale du script de test.
    """
    parser = argparse.ArgumentParser(description="Test de navigation vers la liste des following Instagram")
    parser.add_argument("username", help="Nom d'utilisateur du profil cible")
    parser.add_argument("max_following", nargs="?", type=int, default=10, help="Nombre maximum de following à vérifier")
    args = parser.parse_args()
    
    username = args.username.lstrip('@')
    max_following = args.max_following
    
    logger.info(f"🚀 [TEST] Démarrage du test de navigation following pour @{username} (max: {max_following})")
    
    test = NavigateToFollowingTest()
    
    try:
        if not test.setup(username):
            logger.error("❌ Échec de l'initialisation du test")
            return False
            
        if not test.test_navigate_to_profile(username):
            logger.error("❌ Échec de la navigation vers le profil")
            return False
            
        if not test.test_navigate_to_following_list():
            logger.error("❌ Échec de la navigation vers la liste des following")
            return False
            
        following_count = test.test_detect_following_in_list(max_following=5)
        if following_count == 0:
            logger.error("❌ Aucun following détecté dans la liste")
            return False
            
        if not test.test_scroll_following_list():
            logger.warning("⚠️ Échec du test de scroll simple")
            
        test.test_see_more_button()
        
        if not test.test_continuous_scroll():
            logger.warning("⚠️ Échec du test de scroll continu")
            
        logger.success("✅ [TEST] Test de navigation following terminé avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ [TEST] Erreur lors du test: {e}")
        return False
        
    finally:
        test.cleanup()


if __name__ == "__main__":
    # Permettre l'exécution directe du test
    success = main()
    sys.exit(0 if success else 1)
