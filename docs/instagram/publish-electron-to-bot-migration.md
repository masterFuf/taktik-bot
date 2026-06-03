# Instagram Publish — migration Electron → Bot Python

> Décision (2026-06-03, Kevin) : **migrer Instagram publish vers un bridge Python**
> pour supprimer la disparité d'architecture. Aujourd'hui c'est le **seul** workflow
> qui pilote l'ADB depuis Electron ; tous les autres (IG automation/scraping/DM,
> TikTok dont **upload**, YouTube **upload**) passent par un bridge Python.
> Objectif : 0 régression visée, mais régression tolérée si tout est documenté et
> testée le soir sur device. On migre **flux par flux**, sans big-bang.

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
   `InstagramPublishSelectors.ts` (resource ids, textes FR/EN). **Attention** : les
   `INSTAGRAM_PUBLISH_FALLBACK_POINTS` Electron sont des **coordonnées en dur par
   viewport** — règle AGENTS « pas de coordonnées en dur sauf exception documentée » :
   soit on les remplace par une détection selector, soit on les garde comme fallback
   explicitement documenté et scopé par résolution. Audit `audit_selector_hardcodes.py`
   doit rester vert. Source unique = bot.
3. **Flux POST** d'abord (le plus simple) : porter actions launch→création→média→caption→publish,
   bridge fonctionnel pour `postType=post`. **QA device.**
4. **Flux REEL**, puis **CAROUSEL**, puis **STORY** : un par un, QA device à chaque fois.
5. **Bascule front** : `instagram-upload.ts` → façade `runBridge`, par flux, en gardant le
   chemin Electron en fallback tant que le flux bot n'est pas validé.
6. **Nettoyage** : suppression des services Electron `publish/**` une fois tous les flux
   validés + suppression des selectors publish Electron.

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
