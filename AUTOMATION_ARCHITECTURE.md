# 🏗️ Taktik Automation - Architecture Complète

## 📋 Vue d'Ensemble

Ce document décrit l'architecture complète du système d'automatisation Taktik, incluant :
- **Taktik Bot** (Open Source) - Usage communautaire
- **Taktik Social** (Privé) - Service client automatisé

---

## 🎯 Objectifs

### Taktik Bot (Open Source)
- Permettre aux utilisateurs de lancer des sessions sans CLI interactive
- Support de fichiers de configuration JSON
- Multi-comptes et multi-devices
- Intégration facile dans des scripts

### Taktik Social (Privé)
- Automatisation centralisée pour clients
- Gestion de devices physiques (téléphones USB)
- API pour contrôle à distance
- Dashboard de monitoring

---

## 📁 Structure du Projet

```
taktik-bot2/
├── taktik/
│   ├── core/
│   │   ├── automation/              # 🆕 Module d'automatisation
│   │   │   ├── __init__.py
│   │   │   ├── session_runner.py   # Core runner
│   │   │   ├── config_loader.py    # Chargement configs
│   │   │   ├── device_registry.py  # Registre devices
│   │   │   ├── result_handler.py   # Résultats
│   │   │   ├── __main__.py         # CLI
│   │   │   └── README.md           # Documentation
│   │   │
│   │   ├── api/                     # 🆕 API Server (privé)
│   │   │   ├── __init__.py
│   │   │   ├── server.py           # FastAPI server
│   │   │   ├── routes/
│   │   │   │   ├── sessions.py     # Endpoints sessions
│   │   │   │   ├── devices.py      # Endpoints devices
│   │   │   │   └── health.py       # Health check
│   │   │   ├── worker.py           # Worker Taktik Social
│   │   │   └── middleware.py       # Auth, logging
│   │   │
│   │   ├── config/
│   │   │   ├── api_endpoints.py    # ✅ Existant
│   │   │   └── automation_schema.py # 🆕 Schémas validation
│   │   │
│   │   ├── database/               # ✅ Existant
│   │   ├── license/                # ✅ Existant
│   │   ├── security/               # ✅ Existant
│   │   │
│   │   └── social_media/           # ✅ Existant
│   │       ├── instagram/
│   │       └── tiktok/
│   │
│   ├── cli/                        # ✅ Existant (CLI interactive)
│   └── utils/                      # ✅ Existant
│
└── configs/                        # 🆕 Configs utilisateur
    ├── example_instagram.json
    ├── example_tiktok.json
    └── .gitignore                  # Ignorer les configs avec credentials
```

---

## 🔄 Flux de Données

### 1. Usage Open Source (Taktik Bot)

```
Utilisateur
    ↓ Crée config.json
SessionRunner
    ↓ Charge config
DeviceManager
    ↓ Connecte device
Instagram/TikTok
    ↓ Exécute workflow
SessionResult
    ↓ Retourne stats
Utilisateur
```

### 2. Usage Privé (Taktik Social)

```
Client (Web)
    ↓ Fournit credentials
Taktik Social API (Cloud)
    ↓ Stocke en DB
    ↓ Crée tâche
Worker (Local chez toi)
    ↓ Poll API toutes les 30s
    ↓ Récupère tâche
SessionRunner (Local)
    ↓ Exécute sur device USB
    ↓ Retourne résultats
Worker
    ↓ Envoie résultats
Taktik Social API
    ↓ Stocke stats
Client Dashboard
```

---

## 🏗️ Architecture Détaillée

### Module Automation (Open Source)

#### **SessionRunner**
```python
class SessionRunner:
    """Exécute une session programmatiquement"""
    
    def __init__(self, config: SessionConfig)
    
    @classmethod
    def from_config(cls, config_path: str)
    
    @classmethod
    def from_dict(cls, config_dict: Dict)
    
    def execute(self) -> SessionResult
    
    def cancel(self)
```

**Responsabilités:**
- Charger et valider la configuration
- Connecter au device
- Lancer l'application (Instagram/TikTok)
- Se connecter au compte
- Exécuter le workflow
- Retourner les résultats

#### **ConfigLoader**
```python
class ConfigLoader:
    """Charge et valide les configurations"""
    
    @staticmethod
    def from_json(config_path: str) -> SessionConfig
    
    @staticmethod
    def from_dict(config_dict: Dict) -> SessionConfig
    
    @staticmethod
    def to_json(config: SessionConfig, output_path: str)
    
    @staticmethod
    def create_example_config(platform: str) -> SessionConfig
```

**Responsabilités:**
- Charger configs depuis JSON ou dict
- Valider avec Pydantic
- Générer des exemples
- Sauvegarder des configs

#### **DeviceRegistry**
```python
class DeviceRegistry:
    """Gère l'assignation device ↔ client ↔ compte"""
    
    def assign_device(device_id, client_id, username)
    
    def get_device_for_client(client_id) -> str
    
    def get_device_for_account(username) -> str
    
    def get_available_devices() -> List[str]
    
    def update_last_used(device_id)
```

**Responsabilités:**
- Assigner devices aux clients/comptes
- Récupérer les assignations
- Lister les devices disponibles
- Tracker l'utilisation

#### **SessionResult**
```python
@dataclass
class SessionResult:
    """Résultat d'une session"""
    
    session_id: str
    status: SessionStatus
    stats: SessionStats
    started_at: datetime
    completed_at: datetime
    
    def to_dict() -> Dict
    def summary() -> str
```

**Responsabilités:**
- Stocker les résultats de session
- Calculer les statistiques
- Exporter en JSON
- Générer des résumés

---

### API Server (Privé - Taktik Social)

#### **FastAPI Server**
```python
# taktik/core/api/server.py
from fastapi import FastAPI

app = FastAPI(title="Taktik Bot API")

@app.post("/api/sessions/run")
async def run_session(config: dict, api_key: str):
    """Lance une session"""
    runner = SessionRunner.from_dict(config)
    result = await runner.execute_async()
    return result.to_dict()

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Récupère le statut d'une session"""
    ...

@app.get("/api/devices")
async def list_devices():
    """Liste les devices disponibles"""
    registry = DeviceRegistry()
    return registry.list_assignments()
```

#### **Worker Service**
```python
# taktik/core/api/worker.py
class TaktikWorker:
    """Worker qui poll Taktik Social API"""
    
    def __init__(self, taktik_social_url: str, api_key: str):
        self.social_api = taktik_social_url
        self.api_key = api_key
    
    async def start(self):
        """Démarre le worker"""
        while True:
            tasks = await self.fetch_pending_tasks()
            
            for task in tasks:
                result = await self.execute_task(task)
                await self.send_results(result)
            
            await asyncio.sleep(30)
    
    async def fetch_pending_tasks(self):
        """Récupère les tâches depuis Taktik Social"""
        response = await httpx.get(
            f"{self.social_api}/api/tasks/pending",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()
    
    async def execute_task(self, task):
        """Exécute une tâche"""
        runner = SessionRunner.from_dict(task['config'])
        return runner.execute()
    
    async def send_results(self, result):
        """Envoie les résultats à Taktik Social"""
        await httpx.post(
            f"{self.social_api}/api/results",
            json=result.to_dict(),
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
```

---

## 🔌 Intégration Taktik Social

### Architecture Réseau

```
┌─────────────────────────────────────────────────────────┐
│                    CLOUD (Taktik Social)                │
│                                                         │
│  ┌─────────────┐         ┌──────────────┐             │
│  │   Web App   │────────▶│  Backend API │             │
│  │  (Clients)  │         │   (FastAPI)  │             │
│  └─────────────┘         └──────┬───────┘             │
│                                  │                      │
│                          ┌───────▼────────┐            │
│                          │   Database     │            │
│                          │  (PostgreSQL)  │            │
│                          └────────────────┘            │
│                                                         │
└─────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTPS
                              │ Polling/Webhook
                              ▼
┌─────────────────────────────────────────────────────────┐
│                  LOCAL (Chez toi)                       │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │         Taktik Bot Worker                │          │
│  │  ┌────────────┐      ┌────────────┐     │          │
│  │  │   Worker   │─────▶│ Session    │     │          │
│  │  │  Service   │      │  Runner    │     │          │
│  │  └────────────┘      └─────┬──────┘     │          │
│  │                             │            │          │
│  │                    ┌────────▼────────┐  │          │
│  │                    │ Device Registry │  │          │
│  │                    └────────┬────────┘  │          │
│  └─────────────────────────────┼───────────┘          │
│                                 │                      │
│         ┌───────────────────────┼──────────────┐      │
│         │                       │              │      │
│    ┌────▼─────┐          ┌─────▼────┐   ┌────▼─────┐│
│    │ Phone 1  │          │ Phone 2  │   │ Phone 3  ││
│    │ (USB)    │          │ (USB)    │   │ (USB)    ││
│    │ Client A │          │ Client B │   │ Client C ││
│    └──────────┘          └──────────┘   └──────────┘│
│                                                       │
└───────────────────────────────────────────────────────┘
```

### Flux de Communication

#### **1. Client crée une tâche**
```http
POST https://taktik-social.com/api/tasks
Authorization: Bearer client_token

{
  "account_username": "client_instagram",
  "workflow_type": "automation",
  "target": "hashtag:travel",
  "limits": {"max_interactions": 50}
}
```

#### **2. Worker poll les tâches**
```http
GET https://taktik-social.com/api/tasks/pending
Authorization: Bearer worker_api_key

Response:
[
  {
    "task_id": "task_123",
    "client_id": "client_456",
    "config": {
      "platform": "instagram",
      "device_id": "auto",  // Worker assigne automatiquement
      "account": {...},
      "workflow": {...}
    }
  }
]
```

#### **3. Worker exécute**
```python
# Le worker assigne automatiquement le device
registry = DeviceRegistry()
device_id = registry.get_device_for_client(task['client_id'])

# Ou assigne un device disponible
if not device_id:
    available = registry.get_available_devices()
    device_id = available[0]
    registry.assign_device(device_id, task['client_id'])

# Met à jour la config
task['config']['device_id'] = device_id

# Lance la session
runner = SessionRunner.from_dict(task['config'])
result = runner.execute()
```

#### **4. Worker envoie les résultats**
```http
POST https://taktik-social.com/api/results
Authorization: Bearer worker_api_key

{
  "task_id": "task_123",
  "session_id": "session_789",
  "status": "success",
  "stats": {
    "likes": 45,
    "follows": 18,
    "errors": 0
  },
  "duration_seconds": 1234.5
}
```

---

## 🔒 Sécurité

### Authentification

**Taktik Social → Worker:**
- API Key stockée en variable d'environnement
- HTTPS uniquement
- Rate limiting

**Worker → Devices:**
- ADB local (pas d'exposition réseau)
- Sessions chiffrées

### Données Sensibles

**Credentials:**
- Stockés chiffrés dans Taktik Social DB
- Transmis via HTTPS
- Jamais loggés en clair

**API Keys:**
```bash
# .env (local)
TAKTIK_SOCIAL_URL=https://taktik-social.com
TAKTIK_WORKER_API_KEY=tk_worker_...
```

---

## 📊 Monitoring & Logs

### Logs Worker

```python
# Configuration loguru
logger.add(
    "logs/worker_{time}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)
```

### Métriques

- Nombre de sessions exécutées
- Taux de succès/échec
- Temps d'exécution moyen
- Utilisation des devices
- Actions par plateforme

### Dashboard (Taktik Social)

- Sessions en cours
- Historique des sessions
- Stats par client
- Disponibilité des devices
- Alertes en cas d'erreur

---

## 🚀 Déploiement

### Taktik Bot (Open Source)

```bash
# Installation
pip install -e .

# Générer config
python -m taktik.core.automation --generate-example

# Lancer session
python -m taktik.core.automation --config my_config.json
```

### Worker (Privé)

```bash
# Installation
pip install -e .
pip install fastapi uvicorn httpx

# Configuration
cp .env.example .env
# Éditer .env avec TAKTIK_SOCIAL_URL et API_KEY

# Lancer worker
python -m taktik.core.api.worker
```

### Systemd Service (Linux)

```ini
[Unit]
Description=Taktik Bot Worker
After=network.target

[Service]
Type=simple
User=taktik
WorkingDirectory=/home/taktik/taktik-bot2
Environment="PATH=/home/taktik/taktik-bot2/venv/bin"
ExecStart=/home/taktik/taktik-bot2/venv/bin/python -m taktik.core.api.worker
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 📝 Roadmap

### Phase 1: Core Automation ✅
- [x] SessionRunner
- [x] ConfigLoader
- [x] DeviceRegistry
- [x] SessionResult
- [x] CLI
- [x] Documentation

### Phase 2: API Server (En cours)
- [ ] FastAPI server
- [ ] Endpoints sessions
- [ ] Endpoints devices
- [ ] Worker service
- [ ] Authentification

### Phase 3: Intégration Taktik Social
- [ ] API Taktik Social
- [ ] Polling worker
- [ ] Webhook support
- [ ] Dashboard monitoring

### Phase 4: Features Avancées
- [ ] Multi-sessions parallèles
- [ ] Queue de tâches
- [ ] Retry automatique
- [ ] Notifications (email, Discord)
- [ ] Backup/restore sessions

---

## 🤝 Contribution

**Open Source (Taktik Bot):**
- Module `automation/` est open source
- PRs bienvenues sur GitHub
- Documentation à maintenir

**Privé (Taktik Social):**
- Module `api/` non inclus dans repo public
- Usage interne uniquement

---

## 📄 License

- **Taktik Bot:** Open Source (MIT)
- **Taktik Social Integration:** Propriétaire

---

## 📞 Support

- **Documentation:** [taktik-bot.com/docs](https://taktik-bot.com/docs)
- **Discord:** [discord.gg/bb7MuMmpKS](https://discord.gg/bb7MuMmpKS)
- **GitHub:** [github.com/masterFuf/taktik-bot](https://github.com/masterFuf/taktik-bot)
