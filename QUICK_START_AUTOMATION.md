# 🚀 Quick Start - Taktik Automation

Guide de démarrage rapide pour utiliser le module d'automatisation Taktik.

---

## ⚡ Installation

```bash
cd taktik-bot2
pip install -e .
```

**Dépendances requises:**
```bash
pip install pydantic loguru
```

---

## 🎯 Usage en 3 Étapes

### 1️⃣ Générer une configuration

```bash
python -m taktik.core.automation --generate-example
```

Cela crée `taktik_config_example.json`

### 2️⃣ Éditer la configuration

Ouvrir `taktik_config_example.json` et remplacer :

```json
{
  "platform": "instagram",
  "device_id": "emulator-5566",        // ← Votre device ID (adb devices)
  "api_key": "tk_live_...",            // ← Votre clé API Taktik
  
  "account": {
    "username": "your_username",       // ← Votre username Instagram
    "password": "your_password",       // ← Votre mot de passe
    "save_session": true
  },
  
  "workflow": {
    "type": "automation",
    "target_type": "hashtag",
    "hashtag": "travel",               // ← Hashtag à cibler
    
    "actions": {
      "like": true,
      "follow": true,
      "comment": false
    },
    
    "limits": {
      "max_interactions": 50,
      "max_follows": 20
    }
  }
}
```

### 3️⃣ Lancer la session

```bash
python -m taktik.core.automation --config taktik_config_example.json
```

---

## 📝 Exemples de Configuration

### Exemple 1: Automation Hashtag

```json
{
  "platform": "instagram",
  "device_id": "emulator-5566",
  "api_key": "tk_live_...",
  "account": {
    "username": "travel_blogger",
    "password": "***"
  },
  "workflow": {
    "type": "automation",
    "target_type": "hashtag",
    "hashtag": "travel",
    "actions": {
      "like": true,
      "follow": true
    },
    "limits": {
      "max_interactions": 100,
      "max_follows": 30
    }
  }
}
```

### Exemple 2: Automation Followers

```json
{
  "platform": "instagram",
  "device_id": "emulator-5566",
  "account": {
    "username": "my_account",
    "password": "***"
  },
  "workflow": {
    "type": "automation",
    "target_type": "followers",
    "actions": {
      "like": true,
      "follow": false
    },
    "limits": {
      "max_interactions": 50
    }
  }
}
```

### Exemple 3: Automation Post URL

```json
{
  "platform": "instagram",
  "device_id": "emulator-5566",
  "account": {
    "username": "my_account",
    "password": "***"
  },
  "workflow": {
    "type": "automation",
    "target_type": "post_url",
    "post_url": "https://instagram.com/p/ABC123/",
    "actions": {
      "like": true,
      "follow": true
    }
  }
}
```

---

## 🐍 Usage Python

### Basique

```python
from taktik.core.automation import SessionRunner

# Charger depuis JSON
runner = SessionRunner.from_config("my_config.json")

# Exécuter
result = runner.execute()

# Afficher résultats
print(result.summary())
print(f"Likes: {result.stats.likes}")
print(f"Follows: {result.stats.follows}")
```

### Avancé

```python
from taktik.core.automation import SessionRunner

# Créer depuis dict
config = {
    "platform": "instagram",
    "device_id": "emulator-5566",
    "account": {
        "username": "my_account",
        "password": "my_password"
    },
    "workflow": {
        "type": "automation",
        "target_type": "hashtag",
        "hashtag": "travel",
        "actions": {"like": True, "follow": True},
        "limits": {"max_interactions": 50}
    }
}

runner = SessionRunner.from_dict(config)
result = runner.execute()

# Exporter résultat
import json
with open("result.json", "w") as f:
    json.dump(result.to_dict(), f, indent=2)
```

---

## 📱 Device Registry

### Assigner des Devices

```python
from taktik.core.automation import DeviceRegistry

registry = DeviceRegistry()

# Assigner device → client → compte
registry.assign_device(
    device_id="emulator-5566",
    client_id="client_123",
    username="my_account",
    platform="instagram",
    notes="Client VIP"
)
```

### Récupérer des Devices

```python
# Par client
device = registry.get_device_for_client("client_123")

# Par compte
device = registry.get_device_for_account("my_account", "instagram")

# Devices disponibles
available = registry.get_available_devices()
```

---

## 🔧 Commandes CLI

```bash
# Générer exemple
python -m taktik.core.automation --generate-example

# Générer pour TikTok
python -m taktik.core.automation --generate-example --platform tiktok

# Valider config (dry-run)
python -m taktik.core.automation --config my_config.json --dry-run

# Lancer session
python -m taktik.core.automation --config my_config.json

# Mode verbose
python -m taktik.core.automation --config my_config.json --verbose
```

---

## 📊 Résultats

### Format de Résultat

```json
{
  "session_id": "abc-123",
  "status": "success",
  "platform": "instagram",
  "username": "my_account",
  "device_id": "emulator-5566",
  "started_at": "2025-11-18T22:00:00",
  "completed_at": "2025-11-18T22:20:00",
  "duration_seconds": 1200,
  "stats": {
    "likes": 45,
    "follows": 18,
    "comments": 0,
    "watches": 0,
    "dms_sent": 0,
    "errors": 0,
    "skipped": 2
  },
  "workflow_type": "automation",
  "target_type": "hashtag",
  "target_value": "travel"
}
```

### Affichage Console

```
╭─────────── Session Summary ────────────╮
│ Status: SUCCESS
│ Platform: instagram
│ Username: my_account
│ Device: emulator-5566
│ Duration: 1200.0s
│
│ 📊 Stats:
│   • Likes: 45
│   • Follows: 18
│   • Unfollows: 0
│   • Comments: 0
│   • DMs: 0
│   • Errors: 0
│   • Total: 63
╰────────────────────────────────────────╯
```

---

## 🔒 Sécurité

### ⚠️ Important

**Ne jamais commiter les configs avec credentials !**

```bash
# .gitignore
configs/*.json
!configs/example_*.json
```

### Variables d'Environnement

```python
import os

config = {
    "account": {
        "username": os.getenv("IG_USERNAME"),
        "password": os.getenv("IG_PASSWORD")
    },
    "api_key": os.getenv("TAKTIK_API_KEY")
}
```

```bash
# .env
IG_USERNAME=my_account
IG_PASSWORD=my_password
TAKTIK_API_KEY=tk_live_...
```

---

## 🐛 Troubleshooting

### Erreur: "Config file not found"

```bash
# Vérifier le chemin
ls -la my_config.json

# Utiliser chemin absolu
python -m taktik.core.automation --config /full/path/to/config.json
```

### Erreur: "Invalid configuration"

```bash
# Valider la config
python -m taktik.core.automation --config my_config.json --dry-run

# Vérifier le JSON
python -c "import json; json.load(open('my_config.json'))"
```

### Erreur: "Failed to connect to device"

```bash
# Lister les devices
adb devices

# Vérifier le device ID dans la config
# device_id doit correspondre exactement
```

### Erreur: "Login failed"

- Vérifier username/password
- Vérifier que le compte n'est pas bloqué
- Essayer de se connecter manuellement d'abord

---

## 📚 Documentation Complète

- **Module README:** `taktik/core/automation/README.md`
- **Architecture:** `AUTOMATION_ARCHITECTURE.md`
- **Résumé:** `AUTOMATION_SUMMARY.md`
- **Exemples Python:** `automation_example.py`

---

## 🎯 Cas d'Usage

### 1. Automatisation Simple

```bash
# 1. Créer config
python -m taktik.core.automation --generate-example

# 2. Éditer config
nano taktik_config_example.json

# 3. Lancer
python -m taktik.core.automation --config taktik_config_example.json
```

### 2. Multi-Comptes

```python
# script.py
from taktik.core.automation import SessionRunner

accounts = [
    {"username": "account1", "hashtag": "travel"},
    {"username": "account2", "hashtag": "food"},
    {"username": "account3", "hashtag": "fitness"}
]

for account in accounts:
    config = {
        "platform": "instagram",
        "device_id": f"emulator-{5566 + i}",
        "account": {
            "username": account['username'],
            "password": "***"  # Charger depuis .env
        },
        "workflow": {
            "type": "automation",
            "target_type": "hashtag",
            "hashtag": account['hashtag']
        }
    }
    
    runner = SessionRunner.from_dict(config)
    result = runner.execute()
    print(f"{account['username']}: {result.status.value}")
```

### 3. Intégration avec Taktik Social

```python
# worker.py
import asyncio
import httpx
from taktik.core.automation import SessionRunner

async def worker():
    while True:
        # Récupérer tâches depuis Taktik Social
        response = await httpx.get("https://taktik-social.com/api/tasks/pending")
        tasks = response.json()
        
        for task in tasks:
            # Exécuter
            runner = SessionRunner.from_dict(task['config'])
            result = runner.execute()
            
            # Envoyer résultats
            await httpx.post(
                "https://taktik-social.com/api/results",
                json=result.to_dict()
            )
        
        await asyncio.sleep(30)

asyncio.run(worker())
```

---

## 🤝 Support

- **Discord:** [discord.gg/bb7MuMmpKS](https://discord.gg/bb7MuMmpKS)
- **GitHub:** [github.com/masterFuf/taktik-bot](https://github.com/masterFuf/taktik-bot)
- **Docs:** [taktik-bot.com/docs](https://taktik-bot.com/docs)

---

## ✅ Checklist

Avant de lancer une session :

- [ ] Device connecté (`adb devices`)
- [ ] Config créée et éditée
- [ ] Credentials corrects
- [ ] API key valide (optionnel)
- [ ] Validation OK (`--dry-run`)

---

**Prêt à automatiser ? 🚀**

```bash
python -m taktik.core.automation --config my_config.json
```
