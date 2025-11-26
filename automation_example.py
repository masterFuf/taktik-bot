"""
Exemple d'utilisation du module Taktik Automation
==================================================

Ce script montre comment utiliser le module automation de manière programmatique.
"""

from taktik.core.automation import SessionRunner, ConfigLoader, DeviceRegistry

def example_1_from_json():
    """Exemple 1: Charger depuis un fichier JSON"""
    print("\n" + "="*60)
    print("EXEMPLE 1: Charger depuis JSON")
    print("="*60)
    
    # Charger la config
    runner = SessionRunner.from_config("configs/example_instagram.json")
    
    print(f"✅ Config chargée")
    print(f"   Platform: {runner.config.platform}")
    print(f"   Username: {runner.config.account.username}")
    print(f"   Device: {runner.config.device_id}")
    
    # Exécuter (commenté pour l'exemple)
    # result = runner.execute()
    # print(result.summary())


def example_2_from_dict():
    """Exemple 2: Créer depuis un dictionnaire"""
    print("\n" + "="*60)
    print("EXEMPLE 2: Créer depuis un dictionnaire")
    print("="*60)
    
    config = {
        "platform": "instagram",
        "device_id": "emulator-5566",
        "api_key": "tk_live_your_api_key",
        "account": {
            "username": "my_account",
            "password": "my_password",
            "save_session": True
        },
        "workflow": {
            "type": "automation",
            "target_type": "hashtag",
            "hashtag": "travel",
            "actions": {
                "like": True,
                "follow": True,
                "comment": False
            },
            "limits": {
                "max_interactions": 50,
                "max_follows": 20
            }
        }
    }
    
    runner = SessionRunner.from_dict(config)
    
    print(f"✅ Runner créé")
    print(f"   Session ID: {runner.session_id}")
    print(f"   Target: #{runner.config.workflow.hashtag}")
    
    # Exécuter (commenté pour l'exemple)
    # result = runner.execute()


def example_3_device_registry():
    """Exemple 3: Utiliser le Device Registry"""
    print("\n" + "="*60)
    print("EXEMPLE 3: Device Registry")
    print("="*60)
    
    registry = DeviceRegistry()
    
    # Assigner des devices
    registry.assign_device(
        device_id="emulator-5566",
        client_id="client_123",
        platform="instagram",
        username="account1",
        notes="Client VIP"
    )
    
    registry.assign_device(
        device_id="emulator-5568",
        client_id="client_456",
        platform="instagram",
        username="account2",
        notes="Client standard"
    )
    
    print(f"✅ Devices assignés")
    
    # Récupérer le device d'un client
    device = registry.get_device_for_client("client_123")
    print(f"   Client 123 → Device: {device}")
    
    # Récupérer le device d'un compte
    device = registry.get_device_for_account("account1", "instagram")
    print(f"   Account1 → Device: {device}")
    
    # Lister les devices disponibles
    available = registry.get_available_devices()
    print(f"   Devices disponibles: {len(available)}")
    
    # Lister toutes les assignations
    assignments = registry.list_assignments()
    print(f"   Total assignations: {len(assignments)}")


def example_4_multi_accounts():
    """Exemple 4: Gérer plusieurs comptes"""
    print("\n" + "="*60)
    print("EXEMPLE 4: Multi-comptes")
    print("="*60)
    
    accounts = [
        {
            "username": "account1",
            "password": "pass1",
            "device": "emulator-5566",
            "hashtag": "travel"
        },
        {
            "username": "account2",
            "password": "pass2",
            "device": "emulator-5568",
            "hashtag": "food"
        },
        {
            "username": "account3",
            "password": "pass3",
            "device": "emulator-5570",
            "hashtag": "fitness"
        }
    ]
    
    registry = DeviceRegistry()
    
    for account in accounts:
        # Assigner le device
        registry.assign_device(
            device_id=account['device'],
            username=account['username'],
            platform="instagram"
        )
        
        # Créer la config
        config = {
            "platform": "instagram",
            "device_id": account['device'],
            "account": {
                "username": account['username'],
                "password": account['password']
            },
            "workflow": {
                "type": "automation",
                "target_type": "hashtag",
                "hashtag": account['hashtag'],
                "actions": {"like": True, "follow": True},
                "limits": {"max_interactions": 50}
            }
        }
        
        # Créer le runner (ne pas exécuter pour l'exemple)
        runner = SessionRunner.from_dict(config)
        print(f"✅ Runner créé pour @{account['username']} → #{account['hashtag']}")
        
        # Pour exécuter réellement:
        # result = runner.execute()
        # print(f"   Status: {result.status.value}")


def example_5_config_validation():
    """Exemple 5: Validation de configuration"""
    print("\n" + "="*60)
    print("EXEMPLE 5: Validation de configuration")
    print("="*60)
    
    # Config valide
    valid_config = {
        "platform": "instagram",
        "device_id": "emulator-5566",
        "account": {
            "username": "test",
            "password": "test"
        },
        "workflow": {
            "type": "automation",
            "target_type": "hashtag",
            "hashtag": "test"
        }
    }
    
    try:
        config = ConfigLoader.from_dict(valid_config)
        print(f"✅ Config valide")
    except ValueError as e:
        print(f"❌ Config invalide: {e}")
    
    # Config invalide (platform incorrect)
    invalid_config = {
        "platform": "facebook",  # Invalide
        "device_id": "emulator-5566",
        "account": {
            "username": "test",
            "password": "test"
        },
        "workflow": {
            "type": "automation",
            "target_type": "hashtag",
            "hashtag": "test"
        }
    }
    
    try:
        config = ConfigLoader.from_dict(invalid_config)
        print(f"✅ Config valide")
    except ValueError as e:
        print(f"❌ Config invalide (attendu): {e}")


def example_6_generate_config():
    """Exemple 6: Générer une config d'exemple"""
    print("\n" + "="*60)
    print("EXEMPLE 6: Générer une config")
    print("="*60)
    
    # Créer une config d'exemple
    config = ConfigLoader.create_example_config("instagram")
    
    print(f"✅ Config générée")
    print(f"   Platform: {config.platform}")
    print(f"   Workflow: {config.workflow.type}")
    print(f"   Target: {config.workflow.target_type}")
    
    # Sauvegarder
    ConfigLoader.to_json(config, "configs/generated_example.json")
    print(f"   Sauvegardée: configs/generated_example.json")


def main():
    """Fonction principale"""
    print("\n" + "="*60)
    print("🤖 TAKTIK AUTOMATION - EXEMPLES D'UTILISATION")
    print("="*60)
    
    # Exécuter tous les exemples
    example_1_from_json()
    example_2_from_dict()
    example_3_device_registry()
    example_4_multi_accounts()
    example_5_config_validation()
    example_6_generate_config()
    
    print("\n" + "="*60)
    print("✅ Tous les exemples exécutés avec succès")
    print("="*60)
    print("\n💡 Pour exécuter réellement une session:")
    print("   python -m taktik.core.automation --config configs/my_config.json")
    print()


if __name__ == "__main__":
    main()
