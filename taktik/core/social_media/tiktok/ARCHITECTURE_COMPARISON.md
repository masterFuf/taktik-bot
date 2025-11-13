# 📊 Comparaison Architecture Instagram vs TikTok

Ce document compare les architectures Instagram et TikTok pour montrer la cohérence et les adaptations spécifiques.

---

## 🏗️ **Structure Commune**

Les deux modules partagent la même structure de base :

```
platform/
├── actions/
│   ├── atomic/           # Actions bas niveau
│   ├── core/             # Classes de base
│   └── business/         # Logique métier
├── workflows/
│   ├── core/             # Orchestration
│   ├── management/       # Session & config
│   └── helpers/          # Utilitaires
├── ui/
│   ├── selectors.py      # Sélecteurs XPath
│   └── detectors/        # Détecteurs d'états
├── auth/                 # Authentification
├── models/               # Data models
├── utils/                # Utilities
└── manager.py            # Manager principal
```

---

## 🎯 **Workflows Comparés**

### **Instagram Workflows**
1. **Target Followers/Following** - Cible les followers d'un compte
2. **Hashtag** - Cible les posts d'un hashtag
3. **Post URL** - Cible les likers d'un post
4. **Place** - Cible les posts d'un lieu

### **TikTok Workflows**
1. **Target Users** - Cible les followers/following d'un compte
2. **Hashtag** - Cible les vidéos d'un hashtag
3. **For You Feed** - Interagit avec le feed personnalisé
4. **Sound/Music** - Cible les vidéos d'un son

### **Similarités**
- ✅ Target users (followers/following)
- ✅ Hashtag targeting
- ✅ Filtrage par critères
- ✅ Gestion de session

### **Différences**
- 📱 TikTok : Feed vertical (scroll up/down)
- 📷 Instagram : Feed horizontal (scroll down)
- 🎵 TikTok : Ciblage par son/musique
- 📍 Instagram : Ciblage par lieu

---

## 🔧 **Actions Atomiques Comparées**

### **Actions Communes**

| Action | Instagram | TikTok |
|--------|-----------|--------|
| Follow | ✅ `click_follow_button()` | ✅ `click_follow_button()` |
| Like | ✅ `click_like_button()` | ✅ `click_like_button()` + `double_tap_like()` |
| Comment | ✅ `click_comment_button()` | ✅ `click_comment_button()` |
| Navigate Profile | ✅ `navigate_to_user_profile()` | ✅ `navigate_to_user_profile()` |
| Search | ✅ `search_hashtag()` | ✅ `search_hashtag()` |
| Scroll | ✅ `scroll_down()` | ✅ `scroll_to_next_video()` |

### **Actions Spécifiques Instagram**
- `click_story()` - Voir une story
- `send_dm()` - Envoyer un message direct
- `navigate_to_place()` - Naviguer vers un lieu
- `like_post_from_feed()` - Liker depuis le feed

### **Actions Spécifiques TikTok**
- `double_tap_like()` - Like par double tap (signature TikTok)
- `watch_video(duration)` - Regarder une vidéo
- `scroll_to_next_video()` - Navigation verticale
- `search_sound()` - Rechercher un son
- `click_favorite_button()` - Ajouter aux favoris

---

## 📱 **Sélecteurs UI Comparés**

### **Structure Similaire**

Les deux modules utilisent des dataclasses pour organiser les sélecteurs :

```python
# Instagram
@dataclass
class ProfileSelectors:
    follow_button: List[str]
    following_button: List[str]
    username: List[str]
    bio: List[str]

# TikTok
@dataclass
class ProfileSelectors:
    follow_button: List[str]
    following_button: List[str]
    username: List[str]
    bio: List[str]
```

### **Catégories de Sélecteurs**

| Catégorie | Instagram | TikTok |
|-----------|-----------|--------|
| Auth | ✅ | ✅ |
| Navigation | ✅ | ✅ |
| Profile | ✅ | ✅ |
| Content | Posts/Reels | Videos |
| Comments | ✅ | ✅ |
| Search | ✅ | ✅ |
| Popups | ✅ | ✅ |
| Detection | ✅ | ✅ |

---

## 🎨 **Différences UI**

### **Instagram**
- **Feed horizontal** : Scroll vertical pour voir les posts
- **Stories** : Contenu éphémère en haut
- **Reels** : Onglet séparé
- **DM** : Messagerie intégrée
- **Navigation** : 5 onglets (Home, Search, Reels, Shop, Profile)

### **TikTok**
- **Feed vertical** : Scroll vertical pour changer de vidéo
- **For You** : Feed personnalisé par défaut
- **Following** : Feed des comptes suivis
- **Sounds** : Élément central de la plateforme
- **Navigation** : 5 onglets (Home, Discover, Create, Inbox, Profile)

---

## 🔄 **Navigation Comparée**

### **Instagram Navigation**
```python
# Bottom tabs
navigate_to_home()        # Feed principal
navigate_to_search()      # Recherche
navigate_to_reels()       # Reels
navigate_to_shop()        # Shopping
navigate_to_profile()     # Profil
```

### **TikTok Navigation**
```python
# Bottom tabs
navigate_to_home()        # For You feed
navigate_to_discover()    # Découvrir
navigate_to_inbox()       # Messages
navigate_to_profile()     # Profil
```

---

## 📊 **Interactions Comparées**

### **Instagram**
```python
# Like un post
click_like_button()

# Commenter
click_comment_button()
input_comment("Great post!")

# Suivre
click_follow_button()

# Scroller le feed
scroll_down()
```

### **TikTok**
```python
# Like une vidéo (2 méthodes)
click_like_button()      # Via bouton
double_tap_like()        # Via double tap

# Commenter
click_comment_button()
input_comment("Amazing!")

# Suivre
click_follow_button()

# Scroller les vidéos
scroll_to_next_video()
watch_video(duration=3.0)
```

---

## 🎯 **Filtrage Comparé**

### **Critères Communs**
- ✅ Nombre de followers
- ✅ Nombre de following
- ✅ Ratio followers/following
- ✅ Mots-clés dans la bio
- ✅ Compte vérifié
- ✅ Compte privé/public

### **Critères Spécifiques Instagram**
- Nombre de posts
- Présence de story
- Type de compte (business, creator)

### **Critères Spécifiques TikTok**
- Nombre de likes totaux
- Nombre de vidéos
- Utilisation de sons populaires

---

## 🚀 **Performance**

### **Délais Humains**

Les deux modules utilisent des délais similaires :

```python
delays = {
    'click': (0.2, 0.5),
    'navigation': (0.7, 1.5),
    'scroll': (0.3, 0.7),
    'typing': (0.08, 0.15),
    'default': (0.3, 0.8)
}
```

**TikTok ajoute** :
```python
'video_watch': (2.0, 5.0)  # Regarder une vidéo
```

---

## 📦 **Package Names**

| Platform | Package Name |
|----------|--------------|
| Instagram | `com.instagram.android` |
| TikTok | `com.zhiliaoapp.musically` |

---

## ✅ **Avantages de la Cohérence**

1. **Apprentissage rapide** : Même structure pour les deux plateformes
2. **Code réutilisable** : Classes de base communes
3. **Maintenance facilitée** : Modifications parallèles possibles
4. **Tests similaires** : Même approche de test
5. **Documentation cohérente** : Même format de documentation

---

## 🔮 **Évolutions Futures**

### **Fonctionnalités à Ajouter**

**Instagram**
- [ ] IGTV automation
- [ ] Shopping automation
- [ ] Guides automation

**TikTok**
- [ ] Duets automation
- [ ] Stitches automation
- [ ] Live automation
- [ ] TikTok Shop automation

### **Améliorations Communes**
- [ ] AI-powered content analysis
- [ ] Advanced filtering algorithms
- [ ] Multi-account management
- [ ] Proxy rotation
- [ ] Captcha handling

---

## 📝 **Conclusion**

L'architecture TikTok reprend les meilleures pratiques d'Instagram tout en s'adaptant aux spécificités de la plateforme :

✅ **Structure identique** pour faciliter la maintenance  
✅ **Actions adaptées** aux particularités de TikTok  
✅ **Sélecteurs spécifiques** pour l'UI TikTok  
✅ **Workflows personnalisés** pour les cas d'usage TikTok  

Cette cohérence permet de développer et maintenir les deux modules efficacement.
