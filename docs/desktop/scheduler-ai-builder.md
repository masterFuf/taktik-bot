# AI Scheduler Builder

Document de suivi pour transformer Taktik Agent en generateur de schedulers.

## Objectif produit

Le builder aide l'utilisateur a creer un scheduler par telephone a partir :

1. du compte actif deja connu localement
2. d'un objectif simple
3. d'une fenetre horaire / niveau de risque
4. d'un contexte local de targets

Le flux vise :

1. lire le contexte du compte actif
2. poser quelques questions structurees
3. construire un prompt complet avec le catalogue des nodes disponibles
4. appeler le provider texte
5. normaliser la reponse JSON en graphe React Flow
6. afficher puis sauvegarder le scheduler et sa metadata de generation

Le scheduler reste scope a **un seul telephone**.

## Liens utiles

- [Scheduler - Architecture](scheduler-architecture.md)
- [Scheduler Smart Target Intelligence](../workflows/scheduler-smart-target-intelligence.md)
- [Taxonomy V2](scheduler-taxonomy-v2.md)

## Fichiers de reference

| Fichier | Role |
|---|---|
| `front/src/features/workspace/scheduler/ai/SchedulerBuilderPanel.tsx` | UI du builder, generation, preview, apply, remix |
| `front/src/features/workspace/scheduler/ai/schedulerAiCatalog.ts` | Catalogue LLM, prompts system/user, normalisation, fallback |
| `front/src/features/workspace/scheduler/pages/SchedulerPage.tsx` | Point d'integration avec le canvas et `aiGeneration` |
| `front/electron/database/models/scheduler/schedule.ts` | Shape persisted du scheduler |
| `front/electron/database/repositories/scheduler/SchedulerRepository.ts` | Persistance SQLite |
| `front/electron/handlers/scheduler/scheduler.ts` | IPC save/load/start/stop |

## Etat actuel du builder

Le builder est bien branche au front actuel.

Il supporte :

- choix d'objectif
- choix de plateformes (`instagram`, `tiktok`)
- fenetre horaire
- jours
- niveau de risque
- duree
- localisation cible
- comptes cibles
- hashtags
- notes / contraintes
- remix d'un prompt sauvegarde
- preview avant application
- fallback deterministe si l'IA echoue

## Contexte injecte

Le builder peut enrichir son prompt avec :

- le resume du compte actif
- le Smart Target context via
  `window.electronAPI.aiScheduler.getSmartTargetContext()`
- le taxonomy audit snapshot via
  `window.electronAPI.aiScheduler.getTaxonomyAudit()`

Le composant maintient aussi :

- les target packs selectionnes
- les target packs rejetes
- les suggestions de localisation / comptes / hashtags

## Prompt et generation

Le builder :

1. construit un `systemPrompt`
2. construit un `userPrompt`
3. appelle `window.electronAPI.aiProvider.textCompletion(...)`
4. parse la reponse via `parseSchedulerAiResponse(...)`
5. normalise nodes / edges / metadata

Si l'appel IA echoue ou renvoie un JSON invalide, il bascule sur
`createSchedulerAiFallbackSchedule(...)`.

## Catalogue expose au LLM

La source de verite reste `schedulerAiCatalog.ts`.

Le catalogue couvre notamment :

### Common

- `trigger`
- `delay`
- `condition`
- `time-window`
- `quota-guard`

### Instagram

- `automation`
- `scraping`
- `dm`
- `dm-responses`
- `smart-comment`
- `unfollow`
- `publish`

### TikTok

- `tiktok-automation`
- `tiktok-scraping`
- `tiktok-dm`
- `tiktok-cold-dm`
- `tiktok-unfollow`
- `tiktok-publish`
- `tiktok-account`

### Autres plateformes

- `threads-automation`
- `gmail-account`
- `youtube-account`
- `youtube-upload`

## Wording produit a conserver

Le builder ne doit plus parler d'anciens quotas distants / credits d'action.

Le bon vocabulaire est :

- **limites locales**
- `quota-guard`
- limites journalieres locales

Exemple DM outreach :

- scraping qualifie
- pauses prudentes
- limites locales faibles

## Persistance

Le scheduler sauve maintenant la generation IA dans `ai_generation`.

La metadata sauvegardee contient au minimum :

- `source`
- `generatedAt`
- `scheduleName`
- `summary`
- `answers`
- `accountContext`
- `targetIntelligence`
- `selectedTargetPacks`
- `rejectedTargetPacks`
- `systemPrompt`
- `userPrompt`
- `rawResponse`
- `provider`
- `model`
- `costUsd`
- `warnings`

Cette persistence permet le bouton **Remix saved prompt**.

## Validation / normalisation

Le normaliseur :

- ignore les node types non supportes
- ajoute un trigger si l'IA l'oublie
- cree les positions React Flow
- cree les edges sequentiels
- clamp les bornes connues
- conserve les warnings

## Limites connues

- `tiktok-account` est expose au catalogue et route dans le scheduler, mais le
  login TikTok reste `not_implemented` cote Bot.
- Le builder ne remplace pas les verifications runtime du moteur scheduler.
- Le Smart Target context reste une aide locale ; il ne scrape pas depuis ce
  composant.

## Roadmap encore vraie

- enrichir le mode conversation
- comparer une generation precedente et une nouvelle generation
- affiner les recommandations automatiques de targets
- continuer a nourrir le builder avec Smart Target Intelligence et la taxonomie
  locale
