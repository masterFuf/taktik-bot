# 🔌 Guide d'Intégration TikTok dans le Menu Principal

Ce guide explique comment intégrer le module TikTok dans le menu principal de TAKTIK Bot.

---

## 📋 **Prérequis**

- ✅ Architecture TikTok créée
- ✅ Actions atomiques implémentées
- ✅ Sélecteurs UI définis
- ⏳ Workflows à implémenter
- ⏳ Menu TikTok à créer

---

## 🎯 **Objectif**

Créer un menu TikTok similaire au menu Instagram :

```
Main Menu
1. Instagram
2. TikTok    ← À implémenter
3. Quit

Your choice: 2

TikTok Mode Selection
1. 🔧 Management (Features: Auth, Profile, Videos)
2. 🤖 Automation (Workflows: Target users, Hashtags, For You, Sounds)
3. ← Back

Your choice:
```

---

## 📁 **Fichiers à Créer**

### **1. Menu TikTok** 
`taktik/cli/menus/tiktok_menu.py`

```python
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

class TikTokMenu:
    """Menu principal pour TikTok."""
    
    def __init__(self, api_client, config):
        self.api_client = api_client
        self.config = config
    
    def show(self):
        """Afficher le menu TikTok."""
        while True:
            console.clear()
            console.print(Panel.fit(
                "[bold cyan]TikTok Mode Selection[/bold cyan]\n\n"
                "1. 🔧 Management (Features: Auth, Profile, Videos)\n"
                "2. 🤖 Automation (Workflows: Target users, Hashtags, For You, Sounds)\n"
                "3. ← Back",
                border_style="cyan"
            ))
            
            choice = Prompt.ask("[bold]Your choice[/bold]", choices=["1", "2", "3"])
            
            if choice == "1":
                self.show_management_menu()
            elif choice == "2":
                self.show_automation_menu()
            elif choice == "3":
                break
    
    def show_management_menu(self):
        """Menu de gestion TikTok."""
        # À implémenter
        pass
    
    def show_automation_menu(self):
        """Menu d'automatisation TikTok."""
        # À implémenter
        pass
```

### **2. Menu Management**
`taktik/cli/menus/tiktok/management_menu.py`

```python
class TikTokManagementMenu:
    """Menu de gestion TikTok."""
    
    def show(self):
        """Afficher le menu de gestion."""
        while True:
            console.clear()
            console.print(Panel.fit(
                "[bold cyan]TikTok Management[/bold cyan]\n\n"
                "1. 🔐 Authentication\n"
                "2. 👤 Profile Management\n"
                "3. 🎬 Video Management\n"
                "4. 📊 Statistics\n"
                "5. ← Back",
                border_style="cyan"
            ))
            
            choice = Prompt.ask("[bold]Your choice[/bold]", choices=["1", "2", "3", "4", "5"])
            
            if choice == "1":
                self.handle_authentication()
            elif choice == "2":
                self.handle_profile_management()
            elif choice == "3":
                self.handle_video_management()
            elif choice == "4":
                self.handle_statistics()
            elif choice == "5":
                break
```

### **3. Menu Automation**
`taktik/cli/menus/tiktok/automation_menu.py`

```python
class TikTokAutomationMenu:
    """Menu d'automatisation TikTok."""
    
    def show(self):
        """Afficher le menu d'automatisation."""
        while True:
            console.clear()
            console.print(Panel.fit(
                "[bold cyan]TikTok Automation Workflows[/bold cyan]\n\n"
                "1. 👥 Target Users (Followers/Following)\n"
                "2. #️⃣ Hashtag Targeting\n"
                "3. 🎯 For You Feed\n"
                "4. 🎵 Sound/Music Targeting\n"
                "5. 📊 View Statistics\n"
                "6. ← Back",
                border_style="cyan"
            ))
            
            choice = Prompt.ask("[bold]Your choice[/bold]", choices=["1", "2", "3", "4", "5", "6"])
            
            if choice == "1":
                self.run_target_users_workflow()
            elif choice == "2":
                self.run_hashtag_workflow()
            elif choice == "3":
                self.run_for_you_workflow()
            elif choice == "4":
                self.run_sound_workflow()
            elif choice == "5":
                self.show_statistics()
            elif choice == "6":
                break
```

---

## 🔧 **Modifications à Apporter**

### **1. Menu Principal**
`taktik/cli/main_menu.py`

```python
# Ajouter l'import
from .menus.tiktok_menu import TikTokMenu

# Dans la méthode show()
elif choice == "2":  # TikTok
    tiktok_menu = TikTokMenu(self.api_client, self.config)
    tiktok_menu.show()
```

### **2. Configuration**
`taktik/config/config.py`

Ajouter les paramètres TikTok :

```python
TIKTOK_CONFIG = {
    'package_name': 'com.zhiliaoapp.musically',
    'main_activity': 'com.ss.android.ugc.aweme.splash.SplashActivity',
    'default_delays': {
        'click': (0.2, 0.5),
        'navigation': (0.7, 1.5),
        'scroll': (0.3, 0.7),
        'video_watch': (2.0, 5.0)
    }
}
```

### **3. Device Manager**
Vérifier que le DeviceManager supporte TikTok :

```python
# Dans device_manager.py
SUPPORTED_APPS = {
    'instagram': 'com.instagram.android',
    'tiktok': 'com.zhiliaoapp.musically'
}
```

---

## 🎬 **Workflows à Implémenter**

### **1. Target Users Workflow**

```python
# taktik/core/social_media/tiktok/workflows/core/target_users.py

class TargetUsersWorkflow:
    """Workflow pour cibler les followers/following d'un utilisateur."""
    
    def __init__(self, device, config):
        self.device = device
        self.config = config
        self.nav = NavigationActions(device)
        self.click = ClickActions(device)
        self.scroll = ScrollActions(device)
    
    def run(self, target_username: str, target_type: str = 'followers'):
        """
        Exécuter le workflow.
        
        Args:
            target_username: Nom d'utilisateur cible
            target_type: 'followers' ou 'following'
        """
        # 1. Naviguer vers le profil
        if not self.nav.navigate_to_user_profile(target_username):
            return False
        
        # 2. Ouvrir la liste followers/following
        # À implémenter
        
        # 3. Scroller et interagir
        # À implémenter
        
        return True
```

### **2. Hashtag Workflow**

```python
# taktok/core/social_media/tiktok/workflows/core/hashtag.py

class HashtagWorkflow:
    """Workflow pour cibler les vidéos d'un hashtag."""
    
    def run(self, hashtag: str, video_count: int = 10):
        """
        Exécuter le workflow.
        
        Args:
            hashtag: Hashtag à cibler (sans #)
            video_count: Nombre de vidéos à traiter
        """
        # 1. Rechercher le hashtag
        if not self.nav.search_hashtag(hashtag):
            return False
        
        # 2. Scroller les vidéos
        for i in range(video_count):
            # Watch video
            self.scroll.watch_video(duration=3.0)
            
            # Like (probabilité)
            if should_like():
                self.click.like_video()
            
            # Follow author (probabilité)
            if should_follow():
                self.nav.open_video_author_profile()
                self.click.follow_user(username)
                self.nav.go_back()
            
            # Next video
            self.scroll.scroll_to_next_video()
        
        return True
```

### **3. For You Feed Workflow**

```python
# taktik/core/social_media/tiktok/workflows/core/for_you.py

class ForYouFeedWorkflow:
    """Workflow pour interagir avec le feed For You."""
    
    def run(self, duration_minutes: int = 30):
        """
        Exécuter le workflow.
        
        Args:
            duration_minutes: Durée du workflow en minutes
        """
        # 1. Aller au feed principal
        self.nav.navigate_to_home()
        
        # 2. Scroller et interagir pendant X minutes
        start_time = time.time()
        
        while (time.time() - start_time) < (duration_minutes * 60):
            # Watch video
            watch_duration = random.uniform(2.0, 8.0)
            self.scroll.watch_video(duration=watch_duration)
            
            # Decide action based on filters
            if should_interact():
                self.click.like_video()
            
            if should_follow():
                self.nav.open_video_author_profile()
                self.click.follow_user(username)
                self.nav.go_back()
            
            # Next video
            self.scroll.scroll_to_next_video()
        
        return True
```

---

## 📊 **Base de Données**

### **Tables à Créer**

```sql
-- Table des comptes TikTok
CREATE TABLE tiktok_accounts (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    device_id TEXT,
    proxy_config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des sessions TikTok
CREATE TABLE tiktok_sessions (
    id INTEGER PRIMARY KEY,
    account_id INTEGER,
    workflow_type TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    actions_performed INTEGER DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES tiktok_accounts(id)
);

-- Table des actions TikTok
CREATE TABLE tiktok_actions (
    id INTEGER PRIMARY KEY,
    session_id INTEGER,
    action_type TEXT,
    target_username TEXT,
    success BOOLEAN,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES tiktok_sessions(id)
);

-- Table des utilisateurs ciblés
CREATE TABLE tiktok_targeted_users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    followers_count INTEGER,
    following_count INTEGER,
    likes_count INTEGER,
    videos_count INTEGER,
    bio TEXT,
    is_verified BOOLEAN,
    last_interaction TIMESTAMP,
    interaction_count INTEGER DEFAULT 0
);
```

---

## 🚀 **Étapes d'Intégration**

### **Phase 1: Menu de Base** ✅
1. ✅ Créer `TikTokMenu` principal
2. ✅ Intégrer dans le menu principal
3. ✅ Créer sous-menus Management et Automation

### **Phase 2: Workflows** ⏳
1. ⏳ Implémenter `TargetUsersWorkflow`
2. ⏳ Implémenter `HashtagWorkflow`
3. ⏳ Implémenter `ForYouFeedWorkflow`
4. ⏳ Implémenter `SoundWorkflow`

### **Phase 3: Management** ⏳
1. ⏳ Authentification TikTok
2. ⏳ Gestion de profil
3. ⏳ Statistiques

### **Phase 4: Tests & Debug** ⏳
1. ⏳ Tests des workflows
2. ⏳ Tests des actions
3. ⏳ Debug et optimisation

---

## 📝 **Exemple d'Utilisation**

```bash
# Lancer TAKTIK
python -m taktik

# Sélectionner TikTok
Main Menu
1. Instagram
2. TikTok
3. Quit

Your choice: 2

# Sélectionner Automation
TikTok Mode Selection
1. 🔧 Management
2. 🤖 Automation
3. ← Back

Your choice: 2

# Sélectionner Hashtag Workflow
TikTok Automation Workflows
1. 👥 Target Users
2. #️⃣ Hashtag Targeting
3. 🎯 For You Feed
4. 🎵 Sound/Music Targeting
5. ← Back

Your choice: 2

# Configurer le workflow
Enter hashtag (without #): dance
Number of videos to process [10]: 20
Like probability (0-100) [70]: 80
Follow probability (0-100) [30]: 40

# Exécution
🚀 Starting Hashtag Workflow...
🔍 Searching for #dance...
✅ Found hashtag
📱 Processing video 1/20...
👀 Watching video (3.2s)...
❤️ Liked video
👤 Following @username...
✅ Followed @username
📱 Processing video 2/20...
...
```

---

## ✅ **Checklist d'Intégration**

- [ ] Créer `TikTokMenu`
- [ ] Créer `TikTokManagementMenu`
- [ ] Créer `TikTokAutomationMenu`
- [ ] Modifier le menu principal
- [ ] Créer les workflows
- [ ] Créer les tables de base de données
- [ ] Implémenter l'authentification
- [ ] Tester les workflows
- [ ] Documenter l'utilisation
- [ ] Créer des exemples

---

**Status:** 📋 **GUIDE PRÊT POUR L'INTÉGRATION**
