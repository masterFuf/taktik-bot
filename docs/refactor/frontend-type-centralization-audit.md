# Audit Frontend - Centralisation des types TypeScript

## Objectif

Cet audit recense les `interface` et `type` declares directement dans les composants React de l'application desktop (`front/src`). Le but n'est pas de tout extraire aveuglement, mais de separer clairement :

- les types UI locaux, acceptables dans un composant ;
- les types metier, IPC, DB ou workflow, qui doivent vivre dans des fichiers de types partages ;
- les mappers qui transforment des donnees Electron/SQLite/IPC en modeles UI.

Cette separation devient importante parce que le front couvre plusieurs domaines : Instagram, TikTok, Threads, YouTube, Gmail, scheduler, agent IA, debug tools, device management, et qu'une partie des types se repete aujourd'hui dans les pages.

> Etat courant verifie : les pages legacy `ActionTester.tsx` et
> `AutoTestRunner.tsx` n'existent plus dans `front/src`. Les lignes qui les
> citent ci-dessous sont des jalons historiques de refactor. Le laboratoire
> actif est `front/src/features/tools/cartography/CartographyLabPage.tsx`,
> avec contrats centraux dans `src/app/types/features/debug/actions.types.ts`.

## Methode d'audit

Commande de scan utilisee :

```powershell
rg -n "^(export\s+)?(interface|type)\s+[A-Z][A-Za-z0-9_]*" front/src --glob "*.tsx" --glob "!**/*.stories.tsx"
```

Validation typecheck :

```powershell
cd front
npm run typecheck -- --pretty false
npx eslint . --ext ts,tsx --report-unused-disable-directives --quiet
```

Statut actuel : OK. Les erreurs historiques restantes apres la centralisation ont ete corrigees sur les contrats preload/DB, les sessions locales, les devices, les retours IPC partiellement dynamiques et les erreurs ESLint bloquantes.

Resultat actuel :

| Indicateur | Valeur |
|---|---:|
| Declarations `interface` / `type` dans des `.tsx` au demarrage de l'audit | 470 |
| Declarations `interface` / `type` dans des `.tsx` apres correction du scan | 416 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction `ProfileDetailSheet` | 410 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction `debug/compat` | 382 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction `ActionTester` | 376 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction `AutoTestRunner` | 369 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction `SchedulerControl` | 362 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction `ClonerPage` | 355 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction Discovery/DM/Analyzer/Agent/Content Planner/Scraping/Threads/Device | 291 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction Editor/TikTok Unfollow/Scheduler AI/DB Explorer/Device Management/Historiques scraping | 262 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction Bot/Cold DM/Target Search/Uploads/Smart Target Finder | 245 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction TikTok Target Search/Discovery Qualification/Feed/For You | 235 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction TikTok Target/Post Likers Instagram | 231 |
| Declarations `interface` / `type` dans des `.tsx` apres suppression du workflow Discovery obsolète | 229 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction workflows Target/Hashtag Instagram + Followers/Hashtag TikTok | 221 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction composants shared Cold DM | 215 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction AgentPanel/AgentScout | 210 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction AiModeBar | 207 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction SchedulerTemplatesPage | 204 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction DeviceBubbleList/MirrorDebugPanel/CutEditor | 195 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction Theme/PlatformNav/Toast + settings/licence/accounts/session/scheduler | 158 |
| Declarations `interface` / `type` dans des `.tsx` apres extraction VideoRecorderPage | 156 |
| Fichiers `.tsx` concernes | 207 |
| Scope | `front/src`, hors stories |

Ce nombre inclut aussi des types parfaitement legitimes dans un composant, comme `ButtonProps`, `ModalProps`, `StepStatus` ou un type d'etat purement visuel. Il ne faut donc pas le lire comme "416 problemes", mais comme une cartographie de refacto. La premiere version du scan utilisait `^\s*` et comptait aussi des imports `type Foo` dans les blocs d'import ; le scan actuel ne compte que les declarations top-level.

## Regle de decision

### A garder dans le composant

Un type peut rester local si :

- il ne sert qu'aux props d'un sous-composant declare dans le meme fichier ;
- il decrit uniquement un etat visuel local (`ViewMode`, `StepStatus`, `ModalState`) ;
- il ne franchit aucune frontiere IPC, DB, preload, bridge ou workflow ;
- il n'est pas reutilise ailleurs et ne porte pas un concept metier.

Exemples acceptables :

```ts
interface AccountCardProps { ... }
type StepStatus = 'pending' | 'running' | 'done' | 'error'
```

### A extraire

Un type doit etre centralise si :

- il represente une table SQLite, une ligne repository ou un DTO preload ;
- il represente une configuration de workflow ;
- il represente une session, un profil, un appareil, une interaction, une campagne, un template ;
- il est duplique entre Instagram/TikTok/Threads ou entre page, handler et preload ;
- il est utilise pour mapper une reponse `window.electronAPI.*`.

Exemples a extraire :

```ts
interface AutoSession { ... }
interface SmartSession { ... }
interface TikTokScrapingConfig { ... }
interface WorkflowReport { ... }
interface ConnectedDevice { ... }
```

## Emplacements cibles recommandes

| Domaine | Emplacement cible |
|---|---|
| Types partages comptes/profils | `front/src/app/types/features/shared/account.types.ts` |
| Types Instagram UI/workflows | `front/src/app/types/features/instagram/*.types.ts` |
| Types TikTok UI/workflows | `front/src/app/types/features/tiktok/*.types.ts` |
| Types scheduler | `front/src/app/types/features/scheduler/*.types.ts` |
| Types device management | `front/src/app/types/features/device/*.types.ts` |
| Types debug/compat | `front/src/app/types/features/debug/*.types.ts` |
| Types Electron/preload | `front/electron/preload/*.ts` ou `front/electron/types/*.ts` |
| Types DB/repositories | `front/electron/database/models/**` et repositories concernes |
| Mappers DB/IPC -> UI | `front/src/features/<domain>/lib/*.mappers.ts` ou `utils/*.ts` |

## Zones les plus touchees

Top dossiers par nombre de declarations `interface/type` dans des `.tsx` :

| Zone | Declarations |
|---|---:|
| `features/platforms/instagram` | 64 |
| `features/tools/debug` | 61 |
| `features/platforms/tiktok` | 47 |
| `features/workspace/scheduler` | 45 |
| `features/workspace/device` | 33 |
| `features/app/settings` | 16 |
| `features/tools/editor` | 10 |
| `features/workspace/agent` | 9 |
| `features/platforms/threads` | 7 |
| `features/shared/account` | 4 |

## Fichiers prioritaires

Ces fichiers melangent beaucoup de types locaux et de concepts metier. Ils sont de bons candidats pour une extraction progressive.

| Fichier | Declarations | Risque principal | Recommandation |
|---|---:|---|---|
| `features/tools/debug/compat/WorkflowTestRunner.tsx` | 14 | Types de rapport, events, selectors et workflows dans une page | Fait : extrait vers `debug/compat.types.ts` |
| `features/tools/debug/actions/ActionTester.tsx` | 8 | Ancienne page supprimee ; definition actions + resultats de debug | Fait : extrait vers `debug/actions.types.ts`, consomme aujourd'hui par Cartography Lab |
| `features/workspace/scheduler/pages/SchedulerControl.tsx` | 7 | Schedule graph, nodes, triggers | Fait : extrait vers `scheduler.types.ts` |
| `features/tools/debug/compat/CompatPanel.tsx` | 7 | Resultats compat/selectors/domaines | Fait : extrait vers `debug/compat.types.ts` |
| `features/tools/debug/actions/AutoTestRunner.tsx` | 7 | Ancienne page supprimee ; suites de test, steps, resultats | Fait : extrait vers `debug/actions.types.ts`, consomme aujourd'hui par Cartography Lab |
| `features/tools/cloner/pages/ClonerPage.tsx` | 7 | APK, devices ADB, resultats clone/install | Fait : extrait vers `tools/cloner.types.ts` |
| `features/platforms/instagram/data/discovery/Discovery.tsx` | 6 | Campagnes, profils, stats discovery | Supprimé : remplacé par scraping ciblé + qualification IA + Taktik Agent |
| `features/platforms/instagram/data/target/ProfileDetailSheet.tsx` | 6 | Profil detail, posts, interactions, screenshots IA | Fait : types extraits vers `instagram/profile-detail.types.ts` |
| `features/workspace/content-planner/ContentPlannerPage.tsx` | 6 | Plans, contenu, calendrier | Fait : extrait vers `workspace/content-planner.types.ts` |
| `features/platforms/tiktok/workflows/dm/TikTokDM.tsx` | 6 | Conversations, messages et reponses IA | Fait : extrait vers `tiktok/dm.types.ts` |
| `features/tools/debug/analyzer/WorkflowAnalyzer.tsx` | 6 | Analyse de session, events, violations, resultats | Fait : extrait vers `debug/analyzer.types.ts` |
| `features/platforms/instagram/workflows/agent/TaktikAgent.tsx` | 5 | Config, decisions, stats agent | Fait : extrait vers `instagram/agent.types.ts` |
| `features/platforms/instagram/workflows/dm-responses/DMResponses.tsx` | 5 | Conversations DM et reponses IA | Fait : extrait vers `instagram/dm-responses.types.ts` |
| `features/platforms/threads/components/ThreadsSessionLivePanel.tsx` | 5 | Session live Threads, stats, events | Fait : extrait vers `threads/session.types.ts` |
| `features/workspace/device/management/NoDeviceConnected.tsx` | 5 | Device summary, setup status, ADB/Wi-Fi | Fait : extrait vers `device/device.types.ts` |
| `features/tools/debug/panel/DebugPanel.tsx` | 4 | Logs et metrics debug | Fait : extrait vers `debug/panel.types.ts` |
| `features/platforms/tiktok/data/discovery/TikTokDiscoveryScraping.tsx` | 4 | Campaigns et profils discovery TikTok | Supprimé : remplacé par scraping TikTok + Target Search |
| `features/tools/editor/pages/VideoEditorPage.tsx` | 5 | Workflows editor, categories, plateformes, devices | Fait : extrait vers `editor/page.types.ts` |
| `features/platforms/tiktok/workflows/unfollow/TikTokUnfollow.tsx` | 4 | Config unfollow, tri, filtres | Fait : extrait vers `tiktok/unfollow.types.ts` |
| `features/workspace/scheduler/ai/AISchedulerModal.tsx` | 4 | Props, risques, duree, plateformes, templates IA | Fait : extrait vers `scheduler/ai.types.ts` |
| `features/app/settings/page/sections/database-explorer/DatabaseExplorer.tsx` | 4 | Tables, colonnes, FK, SQL result | Fait : extrait vers `settings/database-explorer.types.ts` |
| `features/workspace/device/management/DevicesManagement.tsx` | 4 | Devices, versions apps, modals | Fait : rattache a `device/device.types.ts` |
| `features/workspace/device/management/DeviceManagement.tsx` | 4 | Devices API, view mode, filtres | Fait : rattache a `device/device.types.ts` |
| `features/platforms/instagram/data/scraping/ScrapingHistory.tsx` | 3 | Sessions et profils historises | Fait : types partages + `instagram/scraping.types.ts` |
| `features/platforms/tiktok/data/scraping/TikTokScrapingHistory.tsx` | 3 | Sessions et profils historises TikTok | Fait : types partages + `tiktok/scraping.types.ts` |
| `features/platforms/tiktok/data/discovery/TikTokDiscoveryQualification.tsx` | 3 | Profil qualification et config filtres | Supprimé avec le module Discovery |
| `features/platforms/instagram/workflows/bot/Bot.tsx` | 3 | Messages bot et catalogue workflows | Fait : extrait vers `instagram/bot.types.ts` |
| `features/platforms/instagram/workflows/cold-dm/ColdDM.tsx` | 3 | Sessions scraping et config Cold DM Instagram | Fait : rattache a `shared/cold-dm.types.ts` |
| `features/platforms/tiktok/workflows/cold-dm/TikTokColdDM.tsx` | 3 | Sessions scraping et config Cold DM TikTok | Fait : rattache a `shared/cold-dm.types.ts` |
| `features/platforms/instagram/data/target/TargetSearch.tsx` | 2 | Profils cibles et filtres recherche | Fait : extrait vers `instagram/target-search.types.ts` |
| `features/platforms/instagram/upload/post/UploadPost.tsx` | 3 | Fichiers selectionnes et type upload | Fait : consomme les types upload Instagram centralises |
| `features/platforms/tiktok/upload/post/TikTokUploadPost.tsx` | 3 | Fichiers selectionnes, tonalite caption et props upload | Fait : extrait vers `tiktok/upload.types.ts` |
| `features/workspace/scheduler/ai/SmartTargetFinder.tsx` | 3 | Profils cibles IA, filtre plateforme et stats | Fait : extrait vers `scheduler/ai.types.ts` |
| `features/platforms/tiktok/data/target/TikTokTargetSearch.tsx` | 3 | Profils cibles TikTok et filtres recherche | Fait : extrait vers `tiktok/target-search.types.ts` |
| `features/platforms/instagram/data/discovery/DiscoveryQualification.tsx` | 3 | Sessions discovery, profils qualifies et resultats IA | Supprimé avec le workflow Discovery ; la qualification IA doit migrer vers les sessions de scraping |
| `features/platforms/instagram/workflows/feed/InstagramFeed.tsx` | 2 | Config workflow Feed Instagram | Fait : extrait vers `instagram/feed.types.ts` |
| `features/platforms/tiktok/workflows/for-you/TikTokForYou.tsx` | 2 | Config workflow For You TikTok | Fait : extrait vers `tiktok/for-you.types.ts` |
| `features/platforms/tiktok/workflows/target/TikTokTarget.tsx` | 2 | Config workflow Target TikTok | Fait : extrait vers `tiktok/target.types.ts` |
| `features/platforms/instagram/workflows/post-likers/InstagramPostLikers.tsx` | 2 | Config workflow Post Likers Instagram | Fait : extrait vers `instagram/post-likers.types.ts` |
| `features/platforms/instagram/workflows/target/InstagramTarget.tsx` | 2 | Config workflow Target Instagram | Fait : extrait vers `instagram/target.types.ts` |
| `features/platforms/instagram/workflows/hashtag/InstagramHashtag.tsx` | 2 | Config workflow Hashtag Instagram | Fait : extrait vers `instagram/hashtag.types.ts` |
| `features/platforms/tiktok/workflows/followers/TikTokFollowers.tsx` | 2 | Config workflow Followers TikTok | Fait : extrait vers `tiktok/followers.types.ts` |
| `features/platforms/tiktok/workflows/hashtag/TikTokHashtag.tsx` | 2 | Config workflow Hashtag TikTok | Fait : extrait vers `tiktok/hashtag.types.ts` |
| `features/shared/cold-dm/components/ColdDMSourceSelector.tsx` | 2 | Source scraped/manual/file + sessions scraping | Fait : rattache a `shared/cold-dm.types.ts` |
| `features/shared/cold-dm/components/ColdDMSummary.tsx` | 2 | Resume source/messages/recipients | Fait : rattache a `shared/cold-dm.types.ts` |
| `features/shared/cold-dm/components/ColdDMMessageEditor.tsx` | 2 | Comptes IA + messages/prompt | Fait : rattache a `shared/cold-dm.types.ts` |
| `features/workspace/agent/components/AgentPanel.tsx` | 0 metier | Props panel, stats IA, contexte workflow | Fait : rattache a `features/workspace/agent/types.ts` |
| `features/workspace/agent/modes/AgentScout.tsx` | 0 metier | Etat Scout, prefiltrage SQL et reponse IPC | Fait : rattache a `features/workspace/agent/types.ts` |
| `features/shared/workflow/AiModeBar.tsx` | 0 metier | Fonctions IA et props de toggle partagees | Fait : rattache a `shared/workflow.types.ts` |
| `features/workspace/scheduler/pages/SchedulerTemplatesPage.tsx` | 0 metier | Templates scheduler et devices de deploiement | Fait : rattache a `scheduler/scheduler.types.ts` |
| `features/workspace/device/management/components/DeviceBubbleList.tsx` | 0 metier | Liste devices et groupes automatiques | Fait : rattache a `device/device.types.ts` |
| `features/tools/debug/mirror/MirrorDebugPanel.tsx` | 0 metier | Logs/stats/filtres du pipeline mirror | Fait : rattache a `debug/panel.types.ts` |
| `features/tools/editor/timeline/CutEditor.tsx`, `features/tools/video/pages/VideoRecorderPage.tsx` | 0 metier principal | Clips/tracks/recordings/props video tools | Fait : rattache a `editor/*.types.ts` |
| `features/app/settings/page/**` | 0 metier principal | Settings, themes et modeles OpenRouter | Fait : rattache a `settings/*.types.ts` |
| `features/app/license/**` | 0 metier principal | Licence, validation et selection devices | Fait : rattache a `license/license.types.ts` |
| `features/platforms/gmail|youtube/**` | 0 metier principal | Comptes Google/Gmail utilises par YouTube | Fait : rattache a `gmail/account.types.ts` et `youtube/account.types.ts` |
| `features/shared/session`, `workspace/scheduler` | 0 metier principal | Contexte session, execution scheduler, node scraping | Fait : rattache aux types shared/scheduler |
| `features/shared/account/components/FollowingListSection.tsx` | 0 metier | Types de graph/following Instagram dans un composant | Fait : types relationnels + mappers dans `shared/account` |
| `features/platforms/instagram/workflows/smart-comment/SmartComment.tsx` | 1 local | DTO Smart Comment + live session + reponses IA | Fait en grande partie : types centralises, reste `SmartCommentPageProps` local |
| `features/shared/account/components/AccountProfileForm.tsx` | 1 local | Types compte, sessions, historique, mappers DB | Fait : types + mappers + panel historique extraits |

## Cas concret : `AccountProfileForm.tsx`

Etat actuel :

- `AccountProfile` et `PlatformAccount` sont du metier partage Instagram/TikTok ;
- `AutoSession`, `SmartSession`, `HistoryTab` sont des types d'historique reutilisables ;
- les fonctions `toAutoSession`, `toSmartSession`, `statsFromTikTokSession`, `readNumber`, `readString` sont des mappers/normalizers de donnees IPC/DB ;
- `AccountCardProps` et `AccountHistoryPanelProps` peuvent rester locaux si les sous-composants restent dans le fichier.

Extraction recommandee :

| Element | Destination |
|---|---|
| `AccountProfile`, `PlatformAccount`, `AutoSession`, `SmartSession`, `HistoryTab` | `front/src/app/types/features/shared/account.types.ts` |
| `toAutoSession`, `toSmartSession`, `statsFromTikTokSession` | `front/src/features/shared/account/lib/account-history.mappers.ts` |
| `AccountHistoryPanel` | `front/src/features/shared/account/components/AccountHistoryPanel.tsx` |
| `AccountCard` | Optionnel, non extrait actuellement : garder local tant qu'aucun fichier `AccountCard.tsx` dedie n'existe. |

## Plan de refacto progressif

### Phase 1 - Shared account

Objectif : nettoyer le composant partage Instagram/TikTok sans modifier le comportement.

Statut : premiere extraction realisee.

Actions :

1. Fait : deplacer les types metier compte/historique vers `account.types.ts`.
2. Fait : creer `account-history.mappers.ts`.
3. Fait : extraire `AccountHistoryPanel`.
4. Fait : verifier `InstagramAccountProfile` et `TikTokAccountProfilePage`.
5. Fait : deplacer les types `following_sync` / `followers_sync` / stats relationnelles vers `account.types.ts`.
6. Fait : creer `account-relationship.mappers.ts` pour normaliser les lignes SQLite avant affichage.

Validation :

```powershell
npx eslint src/features/shared/account/components/AccountProfileForm.tsx src/features/shared/account/components/FollowingListSection.tsx
npm run typecheck
```

Note : le `typecheck` global peut encore echouer sur des erreurs preexistantes hors scope. La validation de cette extraction consiste a verifier qu'aucune erreur ne remonte sur les fichiers touches.

Fichiers crees ou modifies :

| Fichier | Role |
|---|---|
| `front/src/app/types/features/shared/account.types.ts` | Contrats comptes, profils, historique, relations following/followers |
| `front/src/features/shared/account/lib/account-history.mappers.ts` | Normalisation sessions automation / smart comment |
| `front/src/features/shared/account/lib/account-relationship.mappers.ts` | Normalisation `following_sync`, `followers_sync`, stats relationnelles |
| `front/src/features/shared/account/components/AccountHistoryPanel.tsx` | Panel UI dedie a l'historique |
| `front/src/features/shared/account/components/AccountProfileForm.tsx` | Composant principal allege |
| `front/src/features/shared/account/components/FollowingListSection.tsx` | Consomme les types et mappers centralises |
| `front/src/features/shared/account/index.ts` | Barrel export des composants et types partages du domaine |
| `front/src/app/types/features/instagram/smart-comment.types.ts` | Reutilise `AccountProfile` et `DEFAULT_ACCOUNT_PROFILE` depuis le domaine shared account |
| `front/src/app/types/features/instagram/profile-detail.types.ts` | Contrats de `ProfileDetailSheet` : profil, posts, interactions, screenshots IA, following graph |
| `front/src/app/types/features/debug/compat.types.ts` | Contrats debug compat : workflow catalog, live events, reports, version index, selector test results |
| `front/src/app/types/features/debug/actions.types.ts` | Contrats debug actions : action definitions, logs, selector traces, action results |
| `front/src/app/types/features/scheduler/scheduler.types.ts` | Contrats scheduler control : trigger config, nodes, edges, schedules, devices |
| `front/src/app/types/features/tools/cloner.types.ts` | Contrats cloner : APK source/output, devices ADB, identity preview, clone/install results |

### Phase 2 - Instagram workflows

Objectif : reduire les types dupliques entre pages workflow, live panels, handlers et preload.

Priorites :

- `SmartComment.tsx` : deja largement extrait ; reste uniquement un prop type local acceptable
- `Scraping.tsx`
- `ProfileDetailSheet.tsx` : fait pour les types, reste possible extraction UI plus tard si necessaire
- pages Target/Hashtag/PostUrl/Feed si elles portent leurs configs localement.

Types cibles :

- workflow config ;
- live stats ;
- scraped profile ;
- AI classification ;
- profile detail DTO.

### Phase 3 - Scheduler

Objectif : centraliser les types de graph scheduler.

Priorites :

- `SchedulerControl.tsx` : fait pour le control center
- `SchedulerPage.tsx`
- `SchedulerTemplatesPage.tsx`
- `AISchedulerModal.tsx`
- `SchedulerBuilderPanel.tsx`

Types cibles :

- `ScheduleNode`
- `ScheduleEdge`
- `TriggerConfig`
- `ScheduleTemplate`
- `WorkflowSchedule`

### Phase 4 - Debug / compat

Objectif : transformer les outils debug en clients de types partages, utiles aussi pour la documentation et les tests.

Priorites :

- `WorkflowTestRunner.tsx` : fait pour les types principaux
- `CompatPanel.tsx` : fait pour les resultats compat/selectors
- `ReportViewer.tsx` : fait pour le contrat `WorkflowReport`
- `WorkflowAnalyzer.tsx`
- `ActionTester.tsx` : fait pour les types principaux, puis page legacy supprimee au profit de Cartography Lab

Types cibles :

- `WorkflowReport`
- `StepEvent`
- `SelectorEvent`
- `XPathStat`
- `ActionResult`
- `CompatTestResult`

### Phase 5 - Device management

Objectif : unifier les types device entre preload, hooks, cards et pages.

Priorites :

- `DevicesManagement.tsx`
- `DeviceManagement.tsx`
- `NoDeviceConnected.tsx`
- `DeviceCard.tsx`
- `DeviceBubbleList.tsx`

Types cibles :

- `ConnectedDevice`
- `DeviceInfo`
- `WifiDevice`
- `AppVersions`
- `DeviceGroup`

## Anti-patterns detectes

### Type DB cast directement dans un composant

Probleme :

```ts
const rows = await window.electronAPI.db.getSessionsByAccount(...)
const sessions = rows as AutoSession[]
```

Risque : le composant croit manipuler un modele stable alors que la reponse IPC est `Record<string, unknown>`.

Pattern recommande :

```ts
const rows = await window.electronAPI.db.getSessionsByAccount(...)
const sessions = rows.map(toAutoSession)
```

### Meme concept, noms differents

Exemples frequents :

- `followers_count` / `followersCount`
- `profile_pic_path` / `profilePicPath`
- `workflow_type` / `target_type`
- `media_count` / `posts_count`

Risque : mappers implicites dans les composants, bugs silencieux dans les tableaux, exports ou filtres.

Pattern recommande :

- garder les noms DB en repository/preload ;
- exposer un DTO UI camelCase quand les composants en ont besoin ;
- documenter la conversion dans un mapper.

### Config workflow locale a une page

Probleme :

```ts
interface HashtagConfig { ... }
```

Si le meme workflow est aussi manipule par un panel agent, un scheduler, un handler Electron ou un bridge, le type doit etre partage.

## Definition of Done pour chaque extraction

Une extraction est terminee quand :

- le composant ne declare plus de type metier reutilisable ;
- les imports viennent d'un fichier `*.types.ts` ou `app/types/**` ;
- les reponses IPC/DB passent par un mapper explicite ;
- ESLint ne remonte pas de `no-explicit-any` sur les zones touchees ;
- `npm run typecheck` ne cree pas de nouvelle erreur liee au fichier ;
- la page de documentation consolidee du domaine est mise a jour si le type reflete un contrat important.

## Suivi recommande

Cette page doit rester un audit vivant. A chaque grosse extraction :

1. mettre a jour la table des fichiers prioritaires ;
2. documenter les nouveaux fichiers de types ;
3. ajouter les mappers importants dans la doc du module concerne ;
4. relancer le scan `rg` pour suivre la tendance.
