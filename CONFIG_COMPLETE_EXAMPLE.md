# 📋 Configuration Complète - Exemple Instagram Automation

## 🎯 Configuration Actuelle

Voici la configuration complète qui reproduit exactement le workflow CLI :

```json
{
  "client_id": "example_client_123",
  "platform": "instagram",
  "device_id": "emulator-5566",
  "api_key": "TAKTIK-9406-44BD-FB99-F518",
  
  "account": {
    "username": "_blueyadventures_",
    "password": "Jennykevin19941993",
    "save_session": true,
    "save_login_info": false
  },
  
  "workflow": {
    "type": "automation",
    "target_type": "followers",
    "target_username": "blueyfan89",
    "hashtag": null,
    "post_url": null,
    
    "actions": {
      "like": true,
      "follow": true,
      "comment": false,
      "watch": true,
      "unfollow": false
    },
    
    "limits": {
      "max_interactions": 100,
      "max_follows": 5,
      "max_likes": 400,
      "max_likes_per_profile": 4,
      "max_comments": 0,
      "max_unfollows": 0
    },
    
    "probabilities": {
      "like": 100,
      "follow": 5,
      "comment": 0,
      "watch_stories": 15,
      "like_stories": 10
    },
    
    "filters": {
      "min_followers": 50,
      "max_followers": 50000,
      "min_posts": 4,
      "max_followings": 7500
    },
    
    "session": {
      "duration_minutes": 120,
      "min_delay": 5,
      "max_delay": 15
    }
  }
}
```

---

## 📊 Correspondance avec le CLI

### ✅ Paramètres de Base
| CLI | JSON | Valeur |
|-----|------|--------|
| Target username | `target_username` | `blueyfan89` |
| Interaction type | `target_type` | `followers` |
| Max interactions | `limits.max_interactions` | `100` |
| Maximum likes per profile | `limits.max_likes_per_profile` | `4` |

### ✅ Probabilités
| CLI | JSON | Valeur |
|-----|------|--------|
| Probability to like posts | `probabilities.like` | `100%` |
| Probability to follow | `probabilities.follow` | `5%` |
| Probability to comment | `probabilities.comment` | `0%` |
| Probability to watch stories | `probabilities.watch_stories` | `15%` |
| Probability to like stories | `probabilities.like_stories` | `10%` |

### ✅ Filtres
| CLI | JSON | Valeur |
|-----|------|--------|
| Minimum followers required | `filters.min_followers` | `50` |
| Maximum followers accepted | `filters.max_followers` | `50000` |
| Minimum posts required | `filters.min_posts` | `4` |
| Maximum followings accepted | `filters.max_followings` | `7500` |

### ✅ Session
| CLI | JSON | Valeur |
|-----|------|--------|
| Maximum session duration | `session.duration_minutes` | `120 min` |
| Min delay between actions | `session.min_delay` | `5s` |
| Max delay between actions | `session.max_delay` | `15s` |

### ✅ Limites Calculées
| Paramètre | Calcul | Valeur |
|-----------|--------|--------|
| Estimated likes | `max_interactions × max_likes_per_profile` | `100 × 4 = 400` |
| Estimated follows | `max_interactions × (follow_probability / 100)` | `100 × 0.05 = 5` |
| Estimated comments | `max_interactions × (comment_probability / 100)` | `100 × 0 = 0` |

---

## 🚀 Utilisation

### Lancer la session

```bash
python -m taktik.core.automation --config configs/example_instagram.json
```

### Valider la config

```bash
python -m taktik.core.automation --config configs/example_instagram.json --dry-run
```

---

## 📝 Tous les Paramètres Disponibles

### **account** (Obligatoire)
```json
{
  "username": "string",           // Username Instagram
  "password": "string",           // Mot de passe
  "save_session": true|false,     // Sauvegarder la session (défaut: true)
  "save_login_info": true|false   // Sauvegarder infos login (défaut: false)
}
```

### **workflow.type** (Obligatoire)
- `"automation"` - Workflows d'automatisation
- `"management"` - Gestion de compte (🔜 à implémenter)
- `"advanced_actions"` - Actions avancées (🔜 à implémenter)

### **workflow.target_type** (Obligatoire pour automation)
- `"hashtag"` - Cibler un hashtag
- `"followers"` - Cibler les followers d'un compte
- `"following"` - Cibler les followings d'un compte
- `"post_url"` - Cibler les likers d'un post

### **workflow.actions** (Optionnel)
```json
{
  "like": true|false,      // Liker les posts (défaut: true)
  "follow": true|false,    // Suivre les comptes (défaut: true)
  "comment": true|false,   // Commenter (défaut: false)
  "watch": true|false,     // Regarder les stories (défaut: false)
  "unfollow": true|false   // Unfollow (défaut: false)
}
```

### **workflow.limits** (Optionnel)
```json
{
  "max_interactions": 50,        // Max profiles à traiter (1-1000, défaut: 50)
  "max_follows": 20,             // Max follows total (0-500, défaut: 20)
  "max_likes": 50,               // Max likes total (0-1000, défaut: 50)
  "max_likes_per_profile": 2,    // Max likes par profil (1-20, défaut: 2)
  "max_comments": 10,            // Max commentaires (0-100, défaut: 10)
  "max_unfollows": 50            // Max unfollows (0-500, défaut: 50)
}
```

### **workflow.probabilities** (Optionnel)
```json
{
  "like": 80,              // Probabilité de liker (0-100%, défaut: 80)
  "follow": 20,            // Probabilité de suivre (0-100%, défaut: 20)
  "comment": 5,            // Probabilité de commenter (0-100%, défaut: 5)
  "watch_stories": 15,     // Probabilité de regarder stories (0-100%, défaut: 15)
  "like_stories": 10       // Probabilité de liker stories (0-100%, défaut: 10)
}
```

### **workflow.filters** (Optionnel)
```json
{
  "min_followers": 50,      // Minimum de followers (défaut: 50)
  "max_followers": 50000,   // Maximum de followers (défaut: 50000)
  "min_posts": 5,           // Minimum de posts (défaut: 5)
  "max_followings": 7500    // Maximum de followings (défaut: 7500)
}
```

### **workflow.session** (Optionnel)
```json
{
  "duration_minutes": 60,   // Durée de session (1-480 min, défaut: 60)
  "min_delay": 5,           // Délai min entre actions (1-60s, défaut: 5)
  "max_delay": 15           // Délai max entre actions (1-120s, défaut: 15)
}
```

---

## 🎯 Exemples de Configurations

### Exemple 1: Hashtag Travel
```json
{
  "workflow": {
    "type": "automation",
    "target_type": "hashtag",
    "hashtag": "travel",
    "limits": {
      "max_interactions": 50,
      "max_likes_per_profile": 3
    }
  }
}
```

### Exemple 2: Followers d'un Compte
```json
{
  "workflow": {
    "type": "automation",
    "target_type": "followers",
    "target_username": "blueyfan89",
    "limits": {
      "max_interactions": 100,
      "max_likes_per_profile": 4
    },
    "probabilities": {
      "like": 100,
      "follow": 5
    }
  }
}
```

### Exemple 3: Following d'un Compte
```json
{
  "workflow": {
    "type": "automation",
    "target_type": "following",
    "target_username": "competitor_account",
    "limits": {
      "max_interactions": 30,
      "max_likes_per_profile": 2
    }
  }
}
```

### Exemple 4: Post URL
```json
{
  "workflow": {
    "type": "automation",
    "target_type": "post_url",
    "post_url": "https://instagram.com/p/ABC123/",
    "limits": {
      "max_interactions": 20,
      "max_likes_per_profile": 3
    }
  }
}
```

---

## 🔒 Sécurité

**⚠️ IMPORTANT:** Ne jamais commiter ce fichier avec de vrais credentials !

```bash
# .gitignore
configs/*.json
!configs/example_*.json
```

Utiliser des variables d'environnement :

```python
import os
import json

# Charger la config
with open("configs/template.json") as f:
    config = json.load(f)

# Remplacer les credentials
config["account"]["username"] = os.getenv("IG_USERNAME")
config["account"]["password"] = os.getenv("IG_PASSWORD")
config["api_key"] = os.getenv("TAKTIK_API_KEY")
```

---

## 📞 Support

- **Documentation:** `taktik/core/automation/README.md`
- **Architecture:** `AUTOMATION_ARCHITECTURE.md`
- **Quick Start:** `QUICK_START_AUTOMATION.md`
