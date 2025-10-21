# Framework de Test Instagram Bot

Ce répertoire contient des scripts de test automatisés pour tester individuellement chaque fonctionnalité du bot Instagram.

## 🎯 Objectif

Permettre de tester rapidement et de manière isolée chaque composant du bot Instagram sans lancer une session complète d'automatisation.

## 📁 Structure

```
test/
├── README.md                    # Ce fichier
├── story/                       # Tests pour les stories
├── like/                        # Tests pour les likes
├── follow/                      # Tests pour les follows
├── navigation/                  # Tests pour la navigation
│   ├── followers/               # Tests pour la liste des followers
│   └── following/               # Tests pour la liste des following
└── profile/                     # Tests pour la récupération de profils
```

## 🧪 Exemples de commandes

### Stories
```bash
# Tester la visualisation des stories
python taktik\core\social_media\instagram\test\story\test_story_viewer.py lets.explore.ch
```

### Likes
```bash
# Tester le like des posts d'un profil
python taktik\core\social_media\instagram\test\like\test_profile_likes.py outside_the_box_films
```

### Follow
```bash
# Tester le follow d'un profil
python taktik\core\social_media\instagram\test\follow\test_profile_follow.py instagram_username
```

### Navigation - Followers
```bash
# Tester la navigation vers la liste des followers
python taktik\core\social_media\instagram\test\navigation\followers\test_navigate_to_followers.py outside_the_box_films 50
```

### Navigation - Following
```bash
# Tester la navigation vers la liste des following
python taktik\core\social_media\instagram\test\navigation\following\test_navigate_to_following.py outside_the_box_films 50
```

## 🔧 Prérequis

- Device Android connecté et configuré avec ADB
- Application Instagram installée et connectée
- Python 3.8+
- Dépendances du projet installées

## 📋 Logs de Test

Tous les tests utilisent le système de logging intégré. Les logs incluent :
- 🧪 Marqueurs spéciaux `[TEST]` pour identifier les logs de test
- ✅ Succès des étapes
- ❌ Erreurs et échecs
- ⚠️ Avertissements
- 📍 Informations de navigation