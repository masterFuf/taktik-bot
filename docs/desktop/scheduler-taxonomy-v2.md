# Scheduler â€” Taxonomy V2

## Pourquoi cette V2

Le Smart Target actuel sait tirer des signaux utiles depuis :

- le compte actif
- l'historique d'interactions
- les profils classes en base

Mais tant que la base reste heterogene sur :

- `ai_niche`
- `ai_specific_niche`
- `business_category`
- `ai_classification.tags`

... le moteur reste trop heuristique et produit des recommandations fragiles.

La **Taxonomy V2** sert de couche canonique entre :

1. les qualifications IA brutes
2. les profils stockes en SQLite
3. le scheduler AI builder
4. le futur catalogue de hashtags / segments / sources

## Objectifs

- normaliser les niches et sous-niches existantes
- separer geographie, segment metier et niche de contenu
- fournir une source de verite stable au Smart Target
- preparer les prochaines qualifications IA pour sortir un format plus riche
- permettre un catalogue de hashtags par niche / sous-niche / segment

## Tables V2 ajoutees

### `taxonomy_niches`

Niveau principal de la taxonomie.

Colonnes clefs :

- `niche_slug`
- `label`
- `description`
- `account_type`
- `market_scope`

Exemples :

- `business_marketing`
- `creator_economy`
- `local_commerce`
- `tech_ai`

### `taxonomy_sub_niches`

Sous-niches rattachees a une niche principale.

Colonnes clefs :

- `sub_niche_slug`
- `niche_slug`
- `label`
- `target_segments` (JSON texte)

Exemples :

- `social_media_agency`
- `web_agency`
- `growth_marketing`
- `crm_automation`

### `taxonomy_segments`

Segments cibles metier.

Exemples :

- `agency_owner`
- `marketing_freelancer`
- `small_business_owner`
- `startup_founder`
- `community_manager`

### `taxonomy_aliases`

Table de normalisation entre les valeurs brutes de la base et la taxonomie canonique.

Elle permet de mapper :

- `Business & Marketing`
- `business_marketing`
- `Entrepreneur`
- `Digital creator`

... vers des slugs cibles propres.

Colonnes clefs :

- `alias_value`
- `alias_slug`
- `source_type`
- `canonical_type`
- `canonical_slug`
- `confidence`

### `hashtag_catalog`

Catalogue reutilisable pour le scheduler, lie a la taxonomie.

Colonnes clefs :

- `hashtag`
- `platform`
- `language`
- `niche_slug`
- `sub_niche_slug`
- `segment_slug`
- `market_scope`
- `intent`
- `priority`
- `quality_score`

Intentions possibles (taxonomie marketing/scheduler, pas workflow Discovery
dedie) :

- `discovery`
- `authority`
- `lead_generation`
- `local_visibility`
- `community`

### `profile_taxonomy_assignments`

Projection canonique d'un profil au-dessus des champs bruts.

Elle permet de stocker pour chaque profil :

- niche normalisee
- sous-niche normalisee
- type de compte
- portee marche
- segments cibles

Cette table ne remplace pas immediatement `instagram_profiles.ai_niche` et compagnie.
Elle sert de **couche de consolidation**.

Commande actuelle pour projeter les profils Instagram existants dans cette couche :

```bash
npm run taxonomy:assign:instagram
```

Cette projection :

- lit `instagram_profiles`
- mappe `ai_niche`, `ai_specific_niche`, `business_category`
- applique `taxonomy_aliases` puis fallback par slug
- renseigne `profile_taxonomy_assignments`

## Audit de la base existante

Un nouveau service Electron expose un audit live de la taxonomie actuelle :

- niches distinctes
- couples niche / sous-niche
- categories business distinctes
- top tags issus de `ai_classification.tags`
- groupes d'alias a normaliser

Point d'entree IPC :

- `ai-scheduler:get-taxonomy-audit`

Bridge preload :

- `window.electronAPI.aiScheduler.getTaxonomyAudit()`

Dans le builder, un panneau **Taxonomy audit snapshot** affiche maintenant :

- les volumes de niches / sous-niches / categories
- les top tags remontes depuis les classifications
- les principaux groupes d'alias a normaliser

Ce panneau n'est pas encore un outil d'edition. Il sert d'abord a diagnostiquer la qualite de la base avant de recalibrer le Smart Target.

## Strategie recommande

### Etape 1 - Audit

Mesurer ce qu'on a vraiment dans la base locale :

- quelles niches dominent
- quelles variantes se recoupent
- quelles sous-niches sont vides, generiques ou bruitées

### Etape 2 - Mapping canonique

Construire un mapping de normalisation via `taxonomy_aliases`.

### Etape 3 - Catalogue hashtags

Alimenter `hashtag_catalog` via :

- la taxonomie
- un prompt IA dedie
- une validation manuelle

### Etape 4 - Reclassification ciblee

Requalifier uniquement :

- les profils ambigus
- les profils a fort potentiel
- les profils utiles au scheduler

### Etape 5 - Smart Target V3

Faire consommer la taxonomie canonique au lieu de deduire la strategie uniquement depuis les signaux bruts.

## Impact attendu

Pour un compte type `taktik_r2d2`, on veut sortir d'une logique :

- `Geneva`
- `#localbusiness`

... pour aller vers une logique :

- `regional_b2b`
- `business_marketing`
- `growth_marketing`
- `social_media_agency`
- `marketing_freelancer`
- `saas / automation / leadgen`

Le scheduler pourra alors proposer :

- meilleurs comptes source
- meilleurs segments
- meilleurs hashtags
- meilleurs workflows selon le contexte metier reel

## Limites actuelles

- l'audit V1 cible d'abord Instagram
- les tags sont extraits depuis `ai_classification` avec un echantillon borne pour rester reactif
- les tables sont creees, mais pas encore peuplees automatiquement
- la qualification IA du bot n'ecrit pas encore directement dans `profile_taxonomy_assignments`

## Pipeline cible

Le flux prioritaire n'est plus :

- heuristiques live
- puis seed manuelle

Le flux cible devient :

1. export global des distincts SQLite
2. production d'un working set
3. prompt IA de normalisation
4. import des niches / sous-niches / aliases / hashtags
5. reclassification des profils cibles
6. Smart Target consomme enfin la couche taxonomique propre

La seed initiale sert seulement de bootstrap.

Les details sont documentes dans :

- [Taxonomy pipeline](scheduler-taxonomy-pipeline.md)
- [Taxonomy prompts](scheduler-taxonomy-prompts.md)
