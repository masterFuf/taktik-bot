#!/usr/bin/env python3
"""
Test pour la récupération de l'image de profil Instagram.

Usage:
    python test_profile_image.py <username>

Exemple:
    python test_profile_image.py instagram
"""

import sys
import os
import time
import argparse
from pathlib import Path
from loguru import logger
import requests
import base64
from dotenv import load_dotenv

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(root_dir))

# Charger les variables d'environnement
load_dotenv()

# Imports relatifs basés sur la structure du projet
from taktik.core.social_media.instagram.actions.core.device import DeviceManager
from taktik.core.social_media.instagram.actions.profile.profile_manager import ProfileManager
from taktik.core.social_media.instagram.actions.navigation.navigation_manager import NavigationManager
from taktik.core.social_media.instagram.workflows.management.session import SessionManager
from taktik.core.database import db_service

# Configuration des logs
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG")

class ProfileImageTest:
    """Classe de test pour l'extraction d'image de profil."""
    
    def __init__(self):
        self.device = None
        self.navigation_manager = None
        self.profile_manager = None
        self.session_manager = None
        
    def setup(self, username: str):
        """
        Initialise les composants nécessaires pour le test.
        
        Args:
            username: Nom d'utilisateur du profil à tester
        """
        logger.info(f"🧪 [TEST] Initialisation du test d'image de profil pour @{username}")
        
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
            
            # Initialiser le gestionnaire de profil
            self.profile_manager = ProfileManager(self.device, self.session_manager)
            
            logger.info("✅ [TEST] Composants initialisés avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors de l'initialisation: {e}")
            return False
    
    def test_profile_image_dump(self, username: str):
        """
        Effectue un dump de l'interface utilisateur de la page de profil pour analyser
        la structure et identifier les sélecteurs de l'image de profil.
        
        Args:
            username: Nom d'utilisateur Instagram à tester
            
        Returns:
            bool: True si le dump a été réalisé avec succès, False sinon
        """
        logger.info(f"🔍 [TEST] Début du dump UI pour le profil @{username}")
        
        try:
            # Navigation vers le profil
            logger.info(f"📍 [TEST] Navigation vers le profil @{username}")
            navigation_success = self.navigation_manager.navigate_to_profile(username)
            
            if not navigation_success:
                logger.error(f"❌ [TEST] Échec de la navigation vers @{username}")
                return False
                
            logger.success(f"✅ [TEST] Navigation réussie vers @{username}")
            
            # Attendre que le profil se charge complètement
            logger.info("⏳ [TEST] Attente du chargement complet du profil...")
            time.sleep(5)
            
            # Effectuer le dump UI
            logger.info("📊 [TEST] Création du dump UI pour analyse...")
            self.profile_manager._dump_ui_for_debug()
            
            logger.success("✅ [TEST] Dump UI réalisé avec succès")
            return True
                
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors du dump UI: {e}")
            return False
    
    def test_profile_image_extraction(self, username: str):
        """
        Teste l'extraction de l'URL de l'image de profil pour un utilisateur donné.
        Se concentre uniquement sur l'extraction de l'URL sans téléchargement.
        
        Args:
            username: Nom d'utilisateur Instagram à tester
            
        Returns:
            bool: True si le test réussit, False sinon
        """
        logger.info(f"🎯 [TEST] Début du test d'extraction d'URL d'image de profil pour @{username}")
        
        try:
            # Navigation vers le profil
            logger.info(f"📍 [TEST] Navigation vers le profil @{username}")
            navigation_success = self.navigation_manager.navigate_to_profile(username)
            
            if not navigation_success:
                logger.error(f"❌ [TEST] Échec de la navigation vers @{username}")
                return False
                
            logger.success(f"✅ [TEST] Navigation réussie vers @{username}")
            
            # Attendre que le profil se charge complètement
            logger.info("⏳ [TEST] Attente du chargement complet du profil...")
            time.sleep(5)
            
            # Extraire uniquement l'URL de l'image de profil
            logger.info("🖼️ [TEST] Extraction de l'URL de l'image de profil...")
            image_url = self.profile_manager.get_profile_image_url()
            
            if not image_url:
                logger.error("❌ [TEST] Impossible de récupérer l'URL de l'image de profil")
                return False
            
            # Analyser le résultat
            logger.info(f"📊 [TEST] Résultat de l'extraction:")
            logger.info(f"  - URL image: {image_url}")
            
            # Vérifier le type de résultat
            if image_url.startswith('http'):
                logger.success(f"✅ [TEST] URL d'image valide trouvée: {image_url}")
                return True
            elif image_url.startswith('coordinates:'):
                logger.info(f"📍 [TEST] Coordonnées pour screenshot: {image_url}")
                return True
            elif os.path.exists(image_url):
                logger.success(f"✅ [TEST] Image de profil capturée localement: {image_url}")
                # Vérifier que c'est bien un fichier image
                if image_url.lower().endswith(('.png', '.jpg', '.jpeg')):
                    file_size = os.path.getsize(image_url)
                    logger.info(f"📊 [TEST] Taille du fichier: {file_size} bytes")
                    return True
                else:
                    logger.warning(f"⚠️ [TEST] Format de fichier non reconnu: {image_url}")
                    return False
            else:
                logger.warning(f"⚠️ [TEST] Format d'URL inattendu: {image_url}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors du test d'extraction d'URL: {e}")
            return False
    
    def test_profile_image_upload_api(self, username: str):
        """
        Teste la récupération d'image de profil et son upload via l'API.
        Combine screenshot, capture d'image et upload vers le serveur.
        
        Args:
            username: Nom d'utilisateur Instagram à tester
            
        Returns:
            bool: True si le test réussit, False sinon
        """
        logger.info(f"🚀 [TEST] Début du test d'upload d'image de profil via API pour @{username}")
        
        try:
            # Navigation vers le profil
            logger.info(f"📍 [TEST] Navigation vers le profil @{username}")
            navigation_success = self.navigation_manager.navigate_to_profile(username)
            
            if not navigation_success:
                logger.error(f"❌ [TEST] Échec de la navigation vers @{username}")
                return False
                
            logger.success(f"✅ [TEST] Navigation réussie vers @{username}")
            
            # Attendre que le profil se charge complètement
            logger.info("⏳ [TEST] Attente du chargement complet du profil...")
            time.sleep(5)
            
            # Récupérer l'image de profil (screenshot + capture)
            logger.info("🖼️ [TEST] Capture de l'image de profil...")
            image_result = self.profile_manager.get_profile_image_url()
            
            if not image_result:
                logger.error("❌ [TEST] Impossible de capturer l'image de profil")
                return False
            
            # Vérifier si on a un fichier image local
            image_path = None
            if os.path.exists(image_result) and image_result.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = image_result
                logger.success(f"✅ [TEST] Image capturée localement: {image_path}")
            else:
                logger.error(f"❌ [TEST] Résultat inattendu pour l'image: {image_result}")
                return False
            
            # Upload de l'image via l'API
            logger.info("📤 [TEST] Upload de l'image via l'API...")
            upload_success = self._upload_image_to_api(username, image_path)
            
            if upload_success:
                logger.success(f"✅ [TEST] Upload réussi pour @{username}")
                return True
            else:
                logger.error(f"❌ [TEST] Échec de l'upload pour @{username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [TEST] Erreur lors du test d'upload API: {e}")
            return False
    
    def _upload_image_to_api(self, username: str, image_path: str) -> bool:
        """
        Upload une image de profil vers l'API.
        
        Args:
            username: Nom d'utilisateur Instagram
            image_path: Chemin vers le fichier image local
            
        Returns:
            bool: True si l'upload réussit, False sinon
        """
        try:
            # Configuration API
            from .....config.api_endpoints import get_api_url
            api_url = get_api_url()
            api_key = os.getenv('TAKTIK_API_KEY')
            
            if not api_key:
                logger.error("❌ [API] Clé API manquante dans les variables d'environnement")
                return False
            
            # Encoder l'image en base64
            logger.info(f"🔄 [API] Encodage de l'image: {image_path}")
            try:
                with open(image_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            except Exception as e:
                logger.error(f"❌ [API] Erreur lors de l'encodage de l'image: {e}")
                return False
            
            # Déterminer le type d'image
            image_type = image_path.split('.')[-1].lower()
            if image_type not in ['jpg', 'jpeg', 'png', 'gif']:
                logger.error(f"❌ [API] Type d'image non supporté: {image_type}")
                return False
            
            # Préparer les données pour l'API
            data = {
                'username': username,
                'image_data': encoded_image,
                'image_type': image_type
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            
            logger.info(f"📡 [API] Envoi vers {api_url}/upload/profile-image")
            
            # Effectuer la requête
            response = requests.post(
                f"{api_url}/upload/profile-image",
                headers=headers,
                json=data,
                timeout=30
            )
            
            logger.info(f"📊 [API] Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    logger.success(f"✅ [API] Upload réussi:")
                    logger.info(f"  - Image URL: {response_data.get('image_url', 'N/A')}")
                    logger.info(f"  - File Path: {response_data.get('file_path', 'N/A')}")
                    logger.info(f"  - Username: {response_data.get('username', 'N/A')}")
                    return True
                except Exception as e:
                    logger.error(f"❌ [API] Erreur lors du parsing de la réponse: {e}")
                    logger.info(f"Réponse brute: {response.text}")
                    return False
            else:
                logger.error(f"❌ [API] Échec de l'upload: {response.status_code}")
                logger.error(f"Réponse: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ [API] Timeout lors de la requête")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ [API] Erreur de requête: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ [API] Erreur inattendue lors de l'upload: {e}")
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
    parser = argparse.ArgumentParser(description="Test d'extraction d'image de profil Instagram")
    parser.add_argument("username", help="Nom d'utilisateur Instagram à tester")
    parser.add_argument("--dump", "-d", action="store_true", help="Effectuer uniquement un dump UI pour analyse")
    parser.add_argument("--upload", "-u", action="store_true", help="Tester la capture et l'upload d'image via l'API")
    args = parser.parse_args()
    
    username = args.username
    dump_only = args.dump
    upload_test = args.upload
    
    # Créer l'instance de test
    test_instance = ProfileImageTest()
    
    try:
        logger.info("=" * 80)
        if dump_only:
            logger.info(f"🔍 DÉBUT DU DUMP UI - Profil @{username}")
        elif upload_test:
            logger.info(f"🚀 DÉBUT DU TEST UPLOAD API - Profil @{username}")
        else:
            logger.info(f"🧪 DÉBUT DU TEST - Image profil @{username}")
        logger.info("=" * 80)
        
        # Initialisation
        if not test_instance.setup(username):
            logger.error("❌ [TEST] Échec de l'initialisation")
            return False
        
        # Exécution du test ou du dump selon l'option
        if dump_only:
            success = test_instance.test_profile_image_dump(username)
            result_msg = "DUMP UI RÉUSSI" if success else "DUMP UI ÉCHOUÉ"
        elif upload_test:
            success = test_instance.test_profile_image_upload_api(username)
            result_msg = "TEST UPLOAD API RÉUSSI" if success else "TEST UPLOAD API ÉCHOUÉ"
        else:
            success = test_instance.test_profile_image_extraction(username)
            result_msg = "TEST RÉUSSI" if success else "TEST ÉCHOUÉ"
        
        if success:
            logger.success(f"✅ {result_msg} - @{username}")
        else:
            logger.error(f"❌ {result_msg} - @{username}")
            
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
            logger.info(f"{result} - Image @{username}")
        logger.info("=" * 80)

def run():
    """Point d'entrée pour l'exécution du test."""
    return main()

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
