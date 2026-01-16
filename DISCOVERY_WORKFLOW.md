# Discovery Workflow - Conception

## Objectif
Découvrir et qualifier des prospects de haute qualité basés sur leurs centres d'intérêt, engagement et profil, puis générer des personas IA pour personnaliser les Cold DMs.

## Architecture

### 1. Sources de Découverte

#### A. Hashtags
- Scraper les posts d'un hashtag (ex: #instagramautomation)
- Pour chaque post : récupérer likers + commentateurs
- Stocker le contexte (quel hashtag, quel post)

#### B. Comptes Cibles (Competitors/Influencers)
- Scraper les followers d'un compte concurrent
- Scraper les likers/commentateurs de leurs posts
- Identifier les "super engagés" (likent/commentent plusieurs posts)

#### C. Posts Viraux
- Scraper les likers d'un post spécifique (URL)
- Récupérer les commentaires avec leur contenu

### 2. Enrichissement des Profils

Pour chaque profil découvert, récupérer :
- **Bio** : texte complet
- **Website** : lien externe (indicateur de business)
- **Followers/Following** : ratio
- **Posts count** : activité
- **Is Business** : compte pro ou créateur
- **Category** : catégorie du compte (si business)
- **Recent posts** : 3-5 derniers posts (captions)

### 3. Scoring IA des Profils

#### Critères de scoring (0-100)

| Critère | Poids | Description |
|---------|-------|-------------|
| **Business Signal** | 25% | A un site web, email dans bio, "DM for collab" |
| **Engagement Quality** | 20% | Commente (pas juste like), commentaires pertinents |
| **Profile Completeness** | 15% | Bio remplie, photo pro, posts réguliers |
| **Niche Relevance** | 25% | Bio/posts contiennent des mots-clés de la niche |
| **Follower Ratio** | 15% | Ratio followers/following sain (pas un bot) |

#### Données pour le scoring
```python
{
    "username": "example_user",
    "bio": "🚀 Helping brands grow on Instagram | DM for collabs",
    "website": "https://example.com",
    "followers": 5420,
    "following": 890,
    "posts_count": 234,
    "is_business": True,
    "category": "Marketing Agency",
    
    # Engagement data
    "interactions": [
        {"type": "like", "post_id": "xxx", "source": "#instagramgrowth"},
        {"type": "comment", "post_id": "yyy", "content": "Great tips!", "source": "@competitor"},
        {"type": "like", "post_id": "zzz", "source": "@competitor"}
    ],
    
    # Computed
    "engagement_count": 3,
    "unique_sources": 2,
    "has_commented": True
}
```

### 4. Génération de Persona IA

Pour chaque profil qualifié (score > seuil), générer :

```python
{
    "username": "example_user",
    "persona": {
        "interests": ["Instagram growth", "Marketing", "Brand building"],
        "pain_points": ["Needs more engagement", "Looking for automation tools"],
        "communication_style": "Professional but friendly",
        "best_approach": "Highlight ROI and time savings",
        "ice_breaker": "I noticed you're helping brands grow - have you tried automation?",
        "personalized_pitch": "Based on your focus on brand growth, TacticBot could help you..."
    },
    "dm_templates": [
        {
            "style": "direct",
            "message": "Hey! I saw your work with brands. Quick question - how do you handle engagement at scale?"
        },
        {
            "style": "value_first",
            "message": "Love your content on brand growth! I built something that might interest you..."
        }
    ]
}
```

### 5. Schéma Base de Données

#### Table: `discovery_campaigns`
```sql
CREATE TABLE discovery_campaigns (
    campaign_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    account_id INTEGER,
    niche_keywords TEXT,  -- JSON array
    target_sources TEXT,  -- JSON: hashtags, accounts, post_urls
    scoring_config TEXT,  -- JSON: weights and thresholds
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT,
    updated_at TEXT
);
```

#### Table: `discovered_profiles`
```sql
CREATE TABLE discovered_profiles (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    profile_id INTEGER,  -- FK to instagram_profiles
    
    -- Discovery context
    discovery_source TEXT,  -- 'hashtag', 'account', 'post_url'
    source_name TEXT,       -- '#growth', '@competitor', 'post_xxx'
    discovered_at TEXT,
    
    -- Engagement tracking
    interactions TEXT,  -- JSON array of interactions
    total_interactions INTEGER DEFAULT 0,
    has_commented INTEGER DEFAULT 0,
    comment_content TEXT,  -- Aggregated comments
    
    -- Scoring
    ai_score INTEGER,
    score_breakdown TEXT,  -- JSON
    
    -- Persona
    ai_persona TEXT,  -- JSON
    dm_templates TEXT,  -- JSON
    
    -- Status
    status TEXT DEFAULT 'NEW',  -- NEW, QUALIFIED, CONTACTED, CONVERTED, REJECTED
    contacted_at TEXT,
    
    FOREIGN KEY (campaign_id) REFERENCES discovery_campaigns(campaign_id),
    FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id)
);
```

#### Table: `discovery_interactions`
```sql
CREATE TABLE discovery_interactions (
    id INTEGER PRIMARY KEY,
    discovered_profile_id INTEGER,
    interaction_type TEXT,  -- 'like', 'comment'
    source_type TEXT,       -- 'hashtag', 'account_post'
    source_name TEXT,
    post_id TEXT,
    content TEXT,           -- Comment content if applicable
    detected_at TEXT,
    
    FOREIGN KEY (discovered_profile_id) REFERENCES discovered_profiles(id)
);
```

### 6. Workflow d'Exécution

```
┌─────────────────────────────────────────────────────────────┐
│                    DISCOVERY CAMPAIGN                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. COLLECT PHASE                                           │
│     ├── Hashtag #1 → Posts → Likers/Commenters             │
│     ├── Hashtag #2 → Posts → Likers/Commenters             │
│     ├── Account @competitor → Posts → Likers/Commenters    │
│     └── Post URL → Likers/Commenters                       │
│                                                              │
│  2. DEDUPLICATE                                             │
│     └── Merge profiles seen in multiple sources            │
│         (higher engagement = higher priority)               │
│                                                              │
│  3. ENRICH PHASE                                            │
│     └── For each unique profile:                           │
│         ├── Visit profile                                   │
│         ├── Extract bio, website, stats                    │
│         └── Save to database                               │
│                                                              │
│  4. SCORE PHASE (AI)                                        │
│     └── For each enriched profile:                         │
│         ├── Analyze with GPT/Claude                        │
│         ├── Calculate score                                │
│         └── Generate persona + DM templates                │
│                                                              │
│  5. EXPORT                                                  │
│     └── Qualified profiles ready for Cold DM               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 7. Intégration Cold DM

Quand on lance un Cold DM sur un profil découvert :
1. Récupérer le persona généré
2. Utiliser le template personnalisé OU
3. Générer un nouveau message basé sur le persona
4. Tracker la conversion (réponse, follow, etc.)

### 8. UI/UX

#### Page Discovery Campaign
- Créer une campagne avec :
  - Nom
  - Mots-clés de niche
  - Sources (hashtags, comptes, URLs)
  - Seuil de score minimum
  
#### Dashboard
- Nombre de profils découverts
- Répartition par score
- Top profils qualifiés
- Taux de conversion après DM

#### Profile Card
- Score visuel (gauge)
- Persona résumé
- Historique d'interactions
- Bouton "Send DM" avec template pré-rempli

---

## Prochaines Étapes

1. [ ] Créer les tables SQLite
2. [ ] Implémenter le Discovery Workflow Python
3. [ ] Ajouter le scoring IA (via API OpenAI/Claude)
4. [ ] Créer l'UI Electron pour les campagnes
5. [ ] Intégrer avec le Cold DM existant
