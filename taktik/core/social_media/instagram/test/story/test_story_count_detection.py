"""
Script de test pour la détection du nombre de stories.

Usage:
    python -m taktik.core.social_media.instagram.test.test_story_count_detection --device emulator-5566
"""

import sys
import argparse
from pathlib import Path

from loguru import logger
from taktik.core.device import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot


def test_story_count_detection(device_serial: str = None):
    """
    Teste la détection du nombre de stories depuis le viewer.
    
    Args:
        device_serial: ID de l'appareil (optionnel)
    """
    logger.info("🧪 Test de détection du nombre de stories")
    logger.info("=" * 80)
    
    try:
        # Connexion à l'appareil
        if device_serial:
            logger.info(f"Connexion à l'appareil: {device_serial}")
            device = DeviceManager.connect_to_device(device_serial)
        else:
            logger.info("Connexion à l'appareil par défaut")
            # Récupérer le premier appareil disponible
            devices = DeviceManager.get_connected_devices()
            if not devices:
                logger.error("❌ Aucun appareil connecté trouvé")
                return False
            device_serial = devices[0]
            logger.info(f"Appareil détecté: {device_serial}")
            device = DeviceManager.connect_to_device(device_serial)
        
        if device is None:
            logger.error("❌ Échec de connexion à l'appareil")
            return False
        
        logger.success(f"✅ Connecté à l'appareil")
        
        # Créer l'instance DetectionActions
        detection = DetectionActions(device)
        
        # Instructions pour l'utilisateur
        logger.info("\n" + "=" * 80)
        logger.info("📋 INSTRUCTIONS:")
        logger.info("1. Ouvre Instagram sur l'émulateur/appareil")
        logger.info("2. Va sur un profil qui a des stories")
        logger.info("3. Clique sur l'avatar pour ouvrir les stories")
        logger.info("4. Attends que la première story soit chargée")
        logger.info("5. Appuie sur ENTRÉE ici pour lancer le test...")
        logger.info("=" * 80 + "\n")
        
        input("Appuie sur ENTRÉE quand tu es prêt...")
        
        # Capturer screenshot et dump UI
        logger.info("\n📸 Capture de l'écran actuel...")
        project_root = Path(__file__).parent.parent.parent.parent.parent.parent
        output_dir = project_root / "debug_ui" / "story_test"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        screenshot_path = capture_screenshot(device, output_dir=output_dir)
        dump_path = dump_ui_hierarchy(device, output_dir=output_dir)
        
        logger.success(f"Screenshot: {screenshot_path}")
        logger.success(f"Dump UI: {dump_path}")
        
        # Test 1: Vérifier si on est sur une story
        logger.info("\n🔍 Test 1: Vérification écran story...")
        is_on_story = detection.is_story_viewer_open()
        if is_on_story:
            logger.success("✅ On est bien sur l'écran story")
        else:
            logger.warning("⚠️ Pas sur l'écran story (normal si tu n'as pas ouvert les stories)")
        
        # Test 2: Détecter le nombre de stories
        logger.info("\n🔍 Test 2: Détection du nombre de stories...")
        current_story, total_stories = detection.get_story_count_from_viewer()
        
        if total_stories > 0:
            logger.success(f"✅ Stories détectées: {current_story}/{total_stories}")
            logger.info(f"   📊 Position actuelle: Story #{current_story}")
            logger.info(f"   📊 Total de stories: {total_stories}")
            
            # Info sur le défilement automatique
            if current_story < total_stories:
                logger.info(f"\n💡 Il reste {total_stories - current_story} stories à voir")
                logger.info(f"ℹ️  Les stories défilent automatiquement dans Instagram")
                logger.info(f"ℹ️  Le système détectera automatiquement chaque nouvelle story")
        else:
            logger.warning("⚠️ Impossible de détecter le nombre de stories")
            logger.info("   Causes possibles:")
            logger.info("   - Tu n'es pas sur l'écran de story")
            logger.info("   - Le format du content-desc a changé")
            logger.info("   - Regarde le dump UI pour débugger")
        
        # Résumé
        logger.info("\n" + "=" * 80)
        logger.info("📊 RÉSUMÉ DU TEST")
        logger.info("=" * 80)
        logger.info(f"Écran story détecté: {'✅ OUI' if is_on_story else '❌ NON'}")
        logger.info(f"Nombre de stories détecté: {'✅ OUI' if total_stories > 0 else '❌ NON'}")
        if total_stories > 0:
            logger.info(f"Position: {current_story}/{total_stories}")
        logger.info("=" * 80)
        
        logger.success("\n✅ Test terminé !")
        
    except Exception as e:
        logger.error(f"❌ Erreur pendant le test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test de détection du nombre de stories")
    parser.add_argument("--device", type=str, help="ID de l'appareil (ex: emulator-5566)")
    
    args = parser.parse_args()
    
    success = test_story_count_detection(device_serial=args.device)
    sys.exit(0 if success else 1)
