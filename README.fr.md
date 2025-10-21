<div align="center">
  <img src="logo/logo.png" alt="Logo Taktik" width="600"/>
</div>

<div align="center">
  <h3><a href="https://taktik-bot.com/">🌐 taktik-bot.com</a></h3>
</div>

<div align="right">
  <a href="./README.md">🇬🇧 English</a> | <strong>🇫🇷 Français</strong>
</div>

# 🎯 Taktik - Framework d'Automatisation Instagram

**Version 1.0.0** | Automatisation avancée avec comportement humain et mécanismes anti-détection.

> Framework professionnel d'automatisation Instagram avec 3 workflows puissants, filtrage intelligent et analytics complètes.

---

## ✨ Fonctionnalités Clés

### 🚀 3 Workflows d'Automatisation

#### 1. **Workflow Followers** - Ciblez Votre Audience
Interagissez avec les abonnés de comptes spécifiques pour développer votre communauté.

```bash
taktik
# Sélectionnez : Interagir avec les abonnés
# Entrez le nom d'utilisateur cible : @concurrent
# Configurez : likes, commentaires, follows
```

**Fonctionnalités :**
- ✅ Extraction des abonnés de n'importe quel compte public
- ✅ Filtrage intelligent (nombre d'abonnés, comptes business, vérifiés)
- ✅ Like de posts (1-3 par profil)
- ✅ Publication de commentaires avec templates ou messages personnalisés
- ✅ Follow d'utilisateurs avec probabilité configurable
- ✅ Visionnage et like de stories

#### 2. **Workflow Hashtag** - Découvrez du Nouveau Contenu
Engagez avec des posts de hashtags spécifiques pour augmenter votre visibilité.

```bash
taktik
# Sélectionnez : Interagir avec les posts d'un hashtag
# Entrez le hashtag : fitness
# Configurez : max interactions, filtres
```

**Fonctionnalités :**
- ✅ Exploration de posts par hashtag
- ✅ Like de posts avec probabilité intelligente
- ✅ Commentaires sur contenu engageant (10% par défaut)
- ✅ Filtrage de profils (min/max abonnés)
- ✅ Ignore les comptes déjà traités

#### 3. **Workflow Post URL** - Engagez avec du Contenu Spécifique
Interagissez avec les utilisateurs qui ont liké un post ou reel spécifique.

```bash
taktik
# Sélectionnez : Interagir avec les likers d'un post
# Entrez l'URL du post : https://instagram.com/p/ABC123
# Configurez : interactions, commentaires
```

**Fonctionnalités :**
- ✅ Extraction des likers de n'importe quel post/reel public
- ✅ Navigation vers le profil de chaque liker
- ✅ Like de leur contenu
- ✅ Commentaires avec messages personnalisés (5% par défaut)
- ✅ Follow optionnel

---

## 🎨 Capacités d'Interaction

### Actions sur le Contenu
- ✅ **Like de Posts** - Posts standards, carrousels et reels
- ✅ **Commentaires** - Messages basés sur templates ou personnalisés avec emojis
- ✅ **Follow/Unfollow** - Suivi intelligent avec limites configurables
- ✅ **Visionnage de Stories** - Voir et liker les stories

### Fonctionnalités Intelligentes
- 🧠 **Comportement Humain** - Délais aléatoires, scrolling naturel
- 🎯 **Filtrage Avancé** - Nombre d'abonnés, type de compte, langue
- 📊 **Analytics de Session** - Stats temps réel et rapports détaillés
- 🔒 **Anti-Détection** - Patterns aléatoires, gestion des quotas
- 💾 **Suivi en Base de Données** - Jamais deux interactions avec le même compte

---

## 💬 Système de Commentaires

### Catégories de Templates
```python
# Génériques
"Incroyable ! 🔥", "J'adore ! ❤️", "Trop cool ! 😎"

# Engagement
"Super contenu ! 👏", "Continue comme ça ! 💪"

# Courts
"🔥🔥🔥", "❤️", "😍"
```

### Commentaires Personnalisés
```bash
# Via CLI
taktik
# Entrez vos commentaires personnalisés quand demandé
# Ou utilisez les templates par défaut
```

### Configuration
- **Max commentaires par profil :** 1 (par défaut)
- **Probabilité de commentaire :** Configurable par workflow
- **Fermeture auto popup :** Détection intelligente du swipe
- **Suivi des quotas :** Intégré au système de licence

---

## 🚀 Démarrage Rapide

### Prérequis
- **Python 3.10+**
- **Appareil/émulateur Android** avec débogage USB activé
- **ADB** installé et configuré
- **Application Instagram** installée sur l'appareil

### Installation

```bash
# Cloner le dépôt
git clone https://github.com/votre-utilisateur/taktik-bot.git
cd taktik-bot

# Créer l'environnement virtuel
python -m venv venv

# Activer (Windows)
.\venv\Scripts\activate

# Activer (Linux/macOS)
source venv/bin/activate

# Installer les dépendances
pip install -e .
```

### Premier Lancement

```bash
# Lancer la CLI
python -m taktik

# Suivez les instructions interactives :
# 1. Sélectionnez le workflow (Followers/Hashtag/Post URL)
# 2. Entrez la cible (nom d'utilisateur/hashtag/URL)
# 3. Configurez les interactions
# 4. Démarrez l'automatisation
```

---

## ⚙️ Configuration

### Paramètres des Workflows

**Workflow Followers :**
```json
{
  "max_interactions_per_session": 5,
  "like_probability": 1.0,
  "comment_probability": 1.0,
  "follow_probability": 0.05,
  "max_likes_per_profile": 3,
  "max_comments_per_profile": 1
}
```

**Workflow Hashtag :**
```json
{
  "max_interactions": 10,
  "like_probability": 0.8,
  "comment_probability": 0.1,
  "min_followers": 100,
  "max_followers": 50000
}
```

**Workflow Post URL :**
```json
{
  "max_likers_to_extract": 30,
  "like_probability": 0.7,
  "comment_probability": 0.05,
  "follow_probability": 0.1
}
```

### Filtres

```json
{
  "filters": {
    "min_followers": 100,
    "max_followers": 10000,
    "skip_business_accounts": false,
    "skip_verified_accounts": false,
    "skip_private_accounts": true
  }
}
```

---

## 📊 Analytics de Session

### Stats Temps Réel
```
📈 Progression de la Session :
├─ Profils visités : 15/20
├─ Likes effectués : 32
├─ Commentaires postés : 8
├─ Follows effectués : 2
└─ Taux de succès : 94.2%
```

### Suivi en Base de Données
- ✅ Toutes les interactions sauvegardées en base SQLite
- ✅ Prévention des doublons (jamais deux interactions)
- ✅ Historique de sessions et analytics
- ✅ Capacités d'export

---

## 🛠️ Architecture Technique

### Design Modulaire
```
taktik/
├── actions/
│   ├── atomic/          # Actions UI bas niveau
│   ├── business/        # Workflows haut niveau
│   └── core/            # Classes de base
├── workflows/           # 3 workflows principaux
├── ui/                  # Sélecteurs & extracteurs
└── database/            # Intégration SQLite
```

### Technologies Clés
- **uiautomator2** - Automatisation UI Android
- **ADB** - Communication avec l'appareil
- **SQLite** - Base de données locale
- **Loguru** - Logging avancé

---

## 📚 Documentation

Pour la documentation complète, visitez **[taktik-bot.com/en/docs](https://taktik-bot.com/en/docs)**

---

## 🔒 Avis Légal

**Fins éducatives uniquement.** Ce projet est destiné à l'apprentissage des concepts d'automatisation. Les utilisateurs doivent se conformer aux Conditions d'Utilisation d'Instagram. Les développeurs ne sont pas responsables d'une mauvaise utilisation.

---

## 📄 Licence

Licence MIT - Voir [LICENSE](LICENSE) pour les détails.

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Veuillez d'abord lire [CONTRIBUTING.md](CONTRIBUTING.md).

---

<div align="center">
  <strong>Fait avec ❤️ pour les passionnés d'automatisation</strong>
</div>
