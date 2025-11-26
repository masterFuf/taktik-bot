# 🤖 Taktik Automation Module

Module d'automatisation programmatique pour Instagram et TikTok.  
Permet de lancer des sessions sans passer par la CLI interactive.

## 📋 Table des Matières

- [Installation](#installation)
- [Usage Rapide](#usage-rapide)
- [Configuration](#configuration)
- [API Python](#api-python)
- [CLI](#cli)
- [Device Registry](#device-registry)
- [Intégration Taktik Social](#intégration-taktik-social)
- [Exemples](#exemples)

---

## 🚀 Installation

Le module est inclus dans Taktik Bot. Aucune installation supplémentaire requise.

**Dépendances:**
```bash
pip install pydantic loguru
```

---

## ⚡ Usage Rapide

### 1. Générer un fichier de config d'exemple

```bash
python -m taktik.core.automation --generate-example
```

Cela crée `taktik_config_example.json` que vous pouvez éditer.

### 2. Éditer la configuration

```json
{
  "platform": "instagram",
  "device_id": "emulator-5566",
  "api_key": "tk_live_your_api_key_here",
  "account": {
    "username": "your_username",
    "password": "your_password",
    "save_session": true
  },
  "workflow": {
    "type": "automation",
    "target_type": "hashtag",
    "hashtag": "travel",
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

### 3. Lancer la session

```bash
python -m taktik.core.automation --config my_config.json
```

---

## ⚙️ Configuration

### Structure Complète

```json
{
  "client_id": "client_123",           // Optionnel: ID client (Taktik Social)
  "platform": "instagram",             // instagram | tiktok
  "device_id": "emulator-5566",        // Device ID (adb devices)
  "api_key": "tk_live_...",            // Clé API Taktik
  
  "account": {
    "username": "your_username",       // Username du compte
    "password": "your_password",       // Mot de passe
    "save_session": true,              // Sauvegarder la session
    "save_login_info": false           // Sauvegarder les infos de login
  },
  
  "workflow": {
    "type": "automation",              // automation | management | advanced_actions
    "target_type": "hashtag",          // hashtag | followers | following | post_url
    "hashtag": "travel",               // Si target_type = hashtag
    "post_url": "https://...",         // Si target_type = post_url
    
    "actions": {
      "like": true,                    // Liker les posts
      "follow": true,                  // Suivre les comptes
      "comment": false,                // Commenter
      "watch": false,                  // Regarder les stories
      "unfollow": false                // Unfollow
    },
    
    "limits": {
      "max_interactions": 50,          // Max interactions totales
      "max_follows": 20,               // Max follows
      "max_likes": 50,                 // Max likes
      "max_comments": 10,              // Max commentaires
      "max_unfollows": 50              // Max unfollows
    }
  }
}
```

### Types de Workflow

#### 1. **Automation** (Workflow d'automatisation)
```json
{
  "workflow": {
    "type": "automation",
    "target_type": "hashtag",
    "hashtag": "travel"
  }
}
```

**Target Types:**
- `hashtag` - Cibler un hashtag
- `followers` - Cibler vos followers
- `following` - Cibler vos followings
- `post_url` - Cibler un post spécifique

#### 2. **Management** (Gestion de compte)
```json
{
  "workflow": {
    "type": "management"
    // TODO: À implémenter (post content, story, etc.)
  }
}
```

#### 3. **Advanced Actions** (Actions avancées)
```json
{
  "workflow": {
    "type": "advanced_actions"
    // TODO: À implémenter (mass DM, intelligent unfollow, etc.)
  }
}
```

---

## 🐍 API Python

### Usage Basique

```python
from taktik.core.automation import SessionRunner

# Depuis un fichier JSON
runner = SessionRunner.from_config("config.json")
result = runner.execute()

print(f"Status: {result.status.value}")
print(f"Likes: {result.stats.likes}")
print(f"Follows: {result.stats.follows}")
```

### Depuis un Dictionnaire

```python
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
```

### Résultat de Session

```python
result = runner.execute()

# Statut
print(result.status)  # SessionStatus.SUCCESS | FAILED | CANCELLED

# Stats
print(result.stats.likes)
print(result.stats.follows)
print(result.stats.total_actions())

# Durée
print(result.duration_seconds())

# Export
result_dict = result.to_dict()
print(result.summary())
```

---

## 💻 CLI

### Commandes Disponibles

```bash
# Générer un exemple de config
python -m taktik.core.automation --generate-example

# Générer pour TikTok
python -m taktik.core.automation --generate-example --platform tiktok --output tiktok_config.json

# Lancer une session
python -m taktik.core.automation --config my_config.json

# Valider sans exécuter (dry-run)
python -m taktik.core.automation --config my_config.json --dry-run

# Mode verbose
python -m taktik.core.automation --config my_config.json --verbose
```

### Codes de Sortie

- `0` - Succès
- `1` - Échec (erreur de config, connexion, workflow, etc.)

---

## 📱 Device Registry

Le module inclut un registre de devices pour gérer l'assignation device ↔ client ↔ compte.

### Usage

```python
from taktik.core.automation import DeviceRegistry

registry = DeviceRegistry()

# Assigner un device à un client/compte
registry.assign_device(
    device_id="emulator-5566",
    client_id="client_123",
    platform="instagram",
    username="my_account",
    notes="Client VIP - Compte principal"
)

# Récupérer le device d'un client
device_id = registry.get_device_for_client("client_123")

# Récupérer le device d'un compte
device_id = registry.get_device_for_account("my_account", "instagram")

# Lister les devices disponibles
available = registry.get_available_devices()

# Exporter le registre
registry.export_to_json("device_registry_backup.json")
```

### Fichier de Registre

Stocké dans `~/.taktik/device_registry.json`:

```json
{
  "emulator-5566": {
    "device_id": "emulator-5566",
    "client_id": "client_123",
    "platform": "instagram",
    "username": "my_account",
    "assigned_at": "2025-11-18T22:00:00",
    "last_used": "2025-11-18T23:00:00",
    "is_active": true,
    "notes": "Client VIP"
  }
}
```

---

## 🌐 Intégration Taktik Social

### Architecture

```
[Taktik Social Web] (Cloud)
         ↓
    API REST
         ↓
[Taktik Bot Worker] (Local)
         ↓
   SessionRunner
         ↓
[Devices/Téléphones] (USB)
```

### Worker Service (À implémenter)

```python
# taktik/server/worker.py
import asyncio
from taktik.core.automation import SessionRunner

class TaktikWorker:
    """Worker qui poll Taktik Social API"""
    
    async def start(self):
        while True:
            # Récupérer les tâches depuis Taktik Social
            tasks = await self.fetch_pending_tasks()
            
            for task in tasks:
                # Lancer la session
                runner = SessionRunner.from_dict(task['config'])
                result = runner.execute()
                
                # Envoyer les résultats
                await self.send_results(result.to_dict())
            
            await asyncio.sleep(30)  # Poll toutes les 30s
```

---

## 📚 Exemples

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
      "follow": true,
      "comment": false
    },
    "limits": {
      "max_interactions": 100,
      "max_follows": 30,
      "max_likes": 100
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

### Exemple 3: Multi-Comptes

```python
# Script pour gérer plusieurs comptes
from taktik.core.automation import SessionRunner, DeviceRegistry

accounts = [
    {"username": "account1", "device": "emulator-5566"},
    {"username": "account2", "device": "emulator-5568"},
    {"username": "account3", "device": "emulator-5570"},
]

registry = DeviceRegistry()

for account in accounts:
    # Assigner le device
    registry.assign_device(
        device_id=account['device'],
        username=account['username'],
        platform="instagram"
    )
    
    # Charger la config
    config = {
        "platform": "instagram",
        "device_id": account['device'],
        "account": {
            "username": account['username'],
            "password": "***"  # À charger depuis DB
        },
        "workflow": {
            "type": "automation",
            "target_type": "hashtag",
            "hashtag": "travel"
        }
    }
    
    # Lancer la session
    runner = SessionRunner.from_dict(config)
    result = runner.execute()
    
    print(f"{account['username']}: {result.status.value}")
```

---

## 🔒 Sécurité

**⚠️ Important:**
- Ne jamais commiter les fichiers de config avec des mots de passe
- Utiliser des variables d'environnement pour les credentials
- Stocker les configs dans `~/.taktik/configs/` (ignoré par git)

**Exemple avec variables d'environnement:**

```python
import os
from taktik.core.automation import SessionRunner

config = {
    "platform": "instagram",
    "device_id": os.getenv("DEVICE_ID"),
    "api_key": os.getenv("TAKTIK_API_KEY"),
    "account": {
        "username": os.getenv("IG_USERNAME"),
        "password": os.getenv("IG_PASSWORD")
    },
    "workflow": {...}
}

runner = SessionRunner.from_dict(config)
```

---

## 🐛 Debugging

### Mode Verbose

```bash
python -m taktik.core.automation --config config.json --verbose
```

### Logs

Les logs sont affichés dans la console. Pour les sauvegarder:

```bash
python -m taktik.core.automation --config config.json 2>&1 | tee session.log
```

### Dry Run

Valider la config sans exécuter:

```bash
python -m taktik.core.automation --config config.json --dry-run
```

---

## 📝 TODO

- [ ] Implémenter workflows TikTok
- [ ] Implémenter workflows Management (post content, story)
- [ ] Implémenter Advanced Actions (mass DM, intelligent unfollow)
- [ ] API Server FastAPI (pour Taktik Social)
- [ ] Worker service avec polling
- [ ] Webhooks pour notifications temps réel
- [ ] Dashboard web pour monitoring
- [ ] Support multi-sessions parallèles

---

## 📄 License

Ce module fait partie de Taktik Bot.  
Open source pour usage communautaire.  
Intégration Taktik Social réservée à usage privé.

---

## 🤝 Support

- **Documentation:** [taktik-bot.com/docs](https://taktik-bot.com/docs)
- **Discord:** [discord.gg/bb7MuMmpKS](https://discord.gg/bb7MuMmpKS)
- **GitHub:** [github.com/masterFuf/taktik-bot](https://github.com/masterFuf/taktik-bot)
