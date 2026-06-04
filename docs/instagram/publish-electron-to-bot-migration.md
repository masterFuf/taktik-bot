# Instagram Publish — migration Electron → Bot Python

> Décision (2026-06-03, Kevin) : **migrer Instagram publish vers un bridge Python**
> pour supprimer la disparité d'architecture. Aujourd'hui c'est le **seul** workflow
> qui pilote l'ADB depuis Electron ; tous les autres (IG automation/scraping/DM,
> TikTok dont **upload**, YouTube **upload**) passent par un bridge Python.
> Objectif : 0 régression visée, mais régression tolérée si tout est documenté et
> testée le soir sur device. On migre **flux par flux**, sans big-bang.

## Avancement (2026-06-04)

**Flux POST porté et câblé (avec fallback Electron pour les autres flux).**

- **Bridge bot** `publish_bridge` opérationnel : `bridges/instagram/publish/publish.py`
  (entrypoint, lit `argv[0]` = config JSON) → `runtime/commands.py` → `runtime/bridge.py`
  (`InstagramPublishBridge`, dispatch par `postType`). `_run_post` implémenté ; `_run_reel`,
  `_run_carousel`, `_run_story` retournent encore un `flow_not_ported`.
- **Workflow métier en core** : `taktik/core/social_media/instagram/workflows/publish/post_workflow.py`
  (`InstagramPostWorkflow`). Reproduit la séquence validée au Cartography Lab :
  push média (helper partagé `shared/device/media_store.py`) → lancement IG (clone-aware) →
  retour feed → ouvrir création → fermer modale brouillon → 1er média galerie → Next-loop
  jusqu'au composer → caption + hashtags → Share → attente fermeture composer (commit).
  Le bridge est un **adaptateur fin** (connexion device → workflow → events JSON).
- **Sélecteurs** : tous dans `ui/selectors/surfaces/content_creation.py` via des **providers
  XPath** (`create_button_flow_xpaths()`, `composer_xpaths()`, `first_gallery_item_xpath()`,
  `next_button_xpaths()`, `share_button_xpaths()`, etc.). Le workflow ne construit **aucun**
  XPath inline (refusé par `audit_selector_hardcodes.py`). Selector-only, zéro coordonnée.
- **Bascule front (POST)** : nouveau service adaptateur
  `front/electron/services/platforms/instagram/publish/bridge/InstagramPublishBotBridgeService.ts`
  (spawn `publish_bridge` via `runBridge`, mapping des events bot → canal existant
  `instagram:upload-progress`, stop par kill du process, `ProcessManager` propre). Le handler
  `instagram-upload.ts` route vers le bot **uniquement** les flux listés dans
  `BOT_BRIDGE_PUBLISH_KINDS` (= `['post']`) ; reel/carousel/story gardent le chemin Electron.
  **Contrat IPC inchangé** → scheduler et UI manuelle marchent sans modification.
- **Cartography Lab** : le flux POST réel est testable depuis le Lab. Mode **Workflows** :
  entrée « Publish POST » (picker média + caption, nouveau dialog `dialog:select-media`).
  Mode **Scenarios** : `publish-post-full` (joue jusqu'à Share, publie réellement) et
  `publish-post-flow` (validation des sélecteurs sans publier, s'arrête avant Share).

**Reste à faire** : porter `_run_reel` / `_run_carousel` / `_run_story` (même patron),
les valider device, les ajouter à `BOT_BRIDGE_PUBLISH_KINDS`, puis supprimer les services
Electron `publish/**` (phase 6).

> Note contrat : l'implémentation réutilise le contrat upload existant
> (`upload.types.ts`, canal `instagram:upload-progress`) plutôt qu'un nouveau
> `publish.types.ts` — les statuts bot sont mappés sur l'enum front existant côté adaptateur.

## État constaté (preuves)

- `front/electron/handlers/instagram/publish/instagram-upload.ts` (façade) délègue à
  `front/electron/services/platforms/instagram/publish/**` qui pilote l'ADB **en TS**
  (`InstagramUploadDeviceService` → `exec(adb … shell uiautomator dump / input tap)`).
- TikTok upload : `TikTokUploadWorkflowService` → `runBridge('tiktok_publish_bridge')`
  → `bridges/tiktok/publish/publish.py`. YouTube : `youtube_upload_bridge`.
- Bridges IG du bot existants : `account, agent, analysis, automation, engagement,
  scraping` — **pas `publish`**.

## Cible

- Nouveau bridge `publish_bridge` → `bridges/instagram/publish/` (calqué sur
  `bridges/tiktok/publish/` : `publish.py` entrypoint, `runtime/bridge.py`, `runtime/commands.py`).
- Logique publish portée dans `taktik/core/social_media/instagram/**` (actions/workflow)
  + selectors dans `taktik/core/social_media/instagram/ui/selectors/**` (owner bot).
- `instagram-upload.ts` réduit à une **façade IPC** qui `runBridge`, comme `tiktok/upload.ts`.

## Mapping services Electron → modules bot cibles

| Service Electron (`services/platforms/instagram/publish/…`) | Module bot cible |
|---|---|
| `selectors/InstagramPublishSelectors.ts` | `ui/selectors/**` (catalogue publish) — **owner unique bot** |
| `device/InstagramUploadDeviceService.ts` | `shared/device/**` + facade IG (déjà existant côté bot) |
| `media/InstagramUploadMediaService.ts`, `media/InstagramMediaCaptureService.ts` | `media/**` (push device, MediaStore scan, content URI) |
| `text/InstagramUploadCaptionService.ts` + `…CaptionEntryService.ts` | action saisie caption/hashtags (TaktikKeyboard) |
| `creation/InstagramUploadCreationNavigationService.ts` | action navigation création (bouton `+`, permissions, fallback) |
| `launch/InstagramUploadLaunchService.ts` | action launch/restart app + dismiss brouillon |
| `navigation/InstagramUploadPublishNavigationService.ts` | action Next/OK/share adaptatif |
| `story/InstagramUploadStoryFlowService.ts` | workflow flux story |
| `reel/InstagramUploadReelSelectionService.ts` | workflow flux reel |
| `carousel/InstagramUploadCarouselSelectionService.ts` | workflow flux carousel |
| `completion/InstagramPublishCompletionService.ts` | polling confirmation/erreur/timeout |
| `ui/InstagramUploadUiElementService.ts` | helpers UI (dump/find) → facade device bot |

## Contrat bridge (calqué tiktok upload)

- Entrée (config) : `deviceId`, `localPath`/`mediaPaths`, `caption`, `hashtags`,
  `postType` (`post|reel|carousel|story`), `packageName`, options spécifiques flux.
- Events stdout JSON : `status` (`connecting/uploading/publishing/completed/failed/stopped`),
  `log`, `result` terminal (`success|cancelled|error`), conformes aux contrats Live.
- Types front : `src/app/types/features/instagram/publish.types.ts` (réutiliser/aligner sur
  le contrat upload existant).

## Phases (incrémental, fallback Electron conservé)

1. **Scaffold** : `bridges/instagram/publish/` (entrypoint + runtime stub) + enregistrement
   `bridges.manifest.json` + `launcher.py`. Additif, ne touche pas Electron.
2. **Selectors** : **réconcilier** (ne pas dupliquer) avec l'existant bot
   `ui/selectors/surfaces/content_creation.py` (déjà des selectors de création
   posts/stories). Ajouter seulement les selectors publish manquants depuis
   `InstagramPublishSelectors.ts` (resource ids, textes FR/EN).
   **Décision (Kevin, 2026-06-03) : on NE porte PAS les coordonnées en dur.** Côté
   Electron, le chemin primaire est déjà selector-based (`findInstagram…(uiDump)`,
   resource-id/content-desc/text) ; les `INSTAGRAM_PUBLISH_FALLBACK_POINTS` ne sont
   qu'un `scaledFallback` quand le selector échoue — un hack qui casse selon
   DPI/résolution. Le bot reste **100% détection selector dynamique** (xpath +
   wait/retry) : si un selector n'est pas trouvé, on retry/échoue proprement, **jamais**
   un tap sur coordonnée en dur. Audit `audit_selector_hardcodes.py` vert. Source unique = bot.
3. **Flux POST** d'abord (le plus simple) : porter actions launch→création→média→caption→publish,
   bridge fonctionnel pour `postType=post`. **QA device.** — **Fait (2026-06-04)**, QA device en attente.
4. **Flux REEL**, puis **CAROUSEL**, puis **STORY** : un par un, QA device à chaque fois. — À faire.
5. **Bascule front** : `instagram-upload.ts` → façade `runBridge`, par flux, en gardant le
   chemin Electron en fallback tant que le flux bot n'est pas validé. — **Fait pour POST**
   (routage par `BOT_BRIDGE_PUBLISH_KINDS`), fallback Electron conservé pour les autres flux.
6. **Nettoyage** : suppression des services Electron `publish/**` une fois tous les flux
   validés + suppression des selectors publish Electron. — En attente (après flux 4).

## Règles (AGENTS bot/front)

- stdout bridge = JSON machine-readable uniquement (logs → stderr/logger).
- Pas de selectors hardcodés dans actions/workflow : tout dans `ui/selectors/**`.
- Pas de coordonnées/résolutions en dur sauf exception documentée.
- Contrat events publish manuel == scheduler (même sémantique `success/cancelled/error`).
- Garder le chemin Electron tant qu'un flux bot n'est pas validé device (anti-régression).

## QA (device, le soir)

Par flux : publier réellement un post/reel/carousel/story, vérifier confirmation
terminale claire, stop/cancel propre, device libéré. Comparer au comportement Electron
actuel avant de retirer le fallback.
