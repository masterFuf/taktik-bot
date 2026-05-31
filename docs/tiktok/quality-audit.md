# TikTok - Audit qualite et refactor

> Le suivi transverse de `bot/taktik/core` est maintenant maintenu dans [Suivi refactor Bot core](bot-core-refactor-tracker.md). Cette page garde le contexte TikTok et les risques plateforme-specifiques.

## Objectif

Cette page permet d'identifier rapidement les endroits ou TikTok risque de diverger ou de casser.

Elle sert aussi de support quand on veut ajouter une feature sans multiplier les patterns.

## Signaux d'alerte

| Signal | Ou regarder | Risque | Direction |
|---|---|---|---|
| Handler trop large | `handlers/tiktok/tiktok.ts` | responsabilites floues | decouper par famille |
| Publish base sur temps | `handlers/tiktok/upload.ts`, Bot publish | faux positif si connexion lente | lire signal UI/progress |
| SQL direct | handlers/services | sync/migrations fragiles | repository/service data |
| Scheduler different du manuel | scheduler engine + handlers | stop incomplet | chemin commun |
| Events incomplets | bridges TikTok | Live Center pauvre | schema events |
| Selectors coordonnees | Bot workflows | regressions UI | selectors/detectors |
| Popups non traitees | publish/account/feed | blocages aleatoires | handler opportuniste FR/EN |
| Stop sans cancellation | workflows longs | device continue | checks cancellation |

## Cas corrige le 2026-05-28 - Like TikTok FR

Symptome observe sur un Samsung SM-A105FN en TikTok FR :

- le like video ne cliquait plus ;
- le dump XML exposait `content-desc="Attribuer un « J'aime » à la vidéo..."` ;
- nos selectors video restaient centres sur `Like video` / `Unlike` / `Share video`.

Cause racine :

- le rail video TikTok utilisait des fallbacks texte EN-only pour like/share ;
- l'optimisation de langue gardait logiquement le FR et supprimait l'EN, ce qui
  pouvait vider des listes comme `like_button_unliked` sur un device FR ;
- la detection de l'etat liked et certains extracteurs (`author`, `sound`,
  compteurs via `content-desc`) n'etaient pas assez localises.

Remediation retenue :

- preferer les structures stables `f57` + `f4u` (like) et `f57` + `t_j` (share) ;
- garder les fallbacks FR/EN dans `video.py` ;
- etendre `language.py` pour classifier correctement les nouveaux selectors FR ;
- parser les compteurs et metadonnees FR dans `video_detector.py`.

## Cas corrige le 2026-05-28 - Publish dump helpers

Symptome technique :

- `upload_workflow.py` contenait encore la lecture de dumps XML, le tri des bounds et les taps pour le bouton Upload/Gallery et les suggestions hashtag ;
- ces heuristiques sont utiles, mais elles rendaient le workflow trop responsable et difficiles a tester hors device.

Remediation retenue :

- extraction de `publish_upload_picker.py` pour selectionner le bouton Upload/Gallery depuis les bounds XML ;
- extraction de `publish_hashtag_suggestions.py` pour selectionner une suggestion hashtag depuis les bounds XML ;
- conservation des selectors dans `ui/selectors/publish.py` ;
- ajout de tests unitaires sur faux dumps XML pour eviter les regressions.

## Cas corrige le 2026-05-28 - Publish screen/dialog helpers

Symptome technique :

- `upload_workflow.py` portait encore la detection Home/galerie/camera/post/video-editor ;
- il portait aussi les permissions Android, la popup RGPD/post-publish et la confirmation de publication ;
- ces responsabilites sont reutilisables ou testables hors orchestration.

Remediation retenue :

- extraction de `publish_screen_detector.py` pour toutes les detections d'ecran du publish ;
- extraction de `publish_dialogs.py` pour permissions, RGPD/post-publish et confirmation ;
- `upload_workflow.py` ne garde que les appels d'orchestration ;
- ajout de tests unitaires sur faux devices et monkeypatch du `PermissionHandler`.

## Cas corrige le 2026-05-28 - Publish app control

Symptome technique :

- `upload_workflow.py` connaissait directement les commandes ADB `monkey`,
  `am start` et `am force-stop` ;
- cette logique de lifecycle applicatif est reutilisable et doit rester
  testable sans lancer un vrai device.

Remediation retenue :

- extraction de `app_control.py` pour lancer et force-stop un package TikTok ;
- conservation du comportement non fatal en cleanup ;
- ajout de tests unitaires sur les commandes ADB construites et le fallback
  `monkey` -> `am start`.

## Cas corrige le 2026-05-28 - Publish coordinate fallbacks

Symptome technique :

- `upload_workflow.py` contenait encore des `device.click(x, y)` calcules depuis
  `displayWidth/displayHeight` pour Create, Upload, galerie et focus caption ;
- ces coordonnees restent des derniers recours utiles sur certains builds TikTok,
  mais elles ne doivent pas etre melees a l'orchestration du workflow.

Remediation retenue :

- extraction de `publish_touch_fallbacks.py` ;
- conservation de l'ordre selector -> dump XML -> coordonnees de secours ;
- ajout de tests unitaires sur les ratios et sur le cas "toujours sur camera"
  apres selection galerie.

## Cas corrige le 2026-05-28 - Publish text input

Symptome technique :

- `upload_workflow.py` importait directement le clavier TAKTIK et connaissait le
  fallback `adb shell input text` ;
- la logique d'echappement ADB et le refus du fallback non-ASCII etaient
  caches dans l'orchestrateur.

Remediation retenue :

- extraction de `publish_text_input.py` ;
- conservation du comportement : Taktik Keyboard d'abord, ADB ASCII ensuite ;
- ajout de tests unitaires sur clear, type, fallback ADB, echappement et
  blocage du fallback non-ASCII.

## Cas corrige le 2026-05-29 - Publish navigation

Symptome technique :

- `upload_workflow.py` gardait encore des adaptateurs de navigation publish :
  tap Create, tap Upload, ensure gallery picker, select first gallery item ;
- ces helpers rendaient le fichier moins lisible : l'orchestration et les
  details de navigation etaient melanges dans la meme classe.

Remediation retenue :

- extraction de `publish_navigation.py` ;
- conservation de l'ordre selector -> dump XML -> fallback coordonnees ;
- suppression des wrappers techniques inutiles dans `upload_workflow.py` ;
- ajout de tests unitaires sur l'ordre des tentatives et les retries galerie.

## Cas corrige le 2026-05-29 - TikTok Followers stop policy

Symptome produit :

- la fin d'une target etait encore deduite par des tentatives de scroll ;
- ce signal technique ne correspond pas a ce que l'utilisateur configure ;
- le vrai concept metier est le nombre d'usernames/profils deja connus rencontres
  de suite avant de conclure qu'une target ne livre plus de nouveaux profils.

Remediation retenue :

- extraction de `services/followers/stop_policy.py`, service commun base sur usernames
  normalises distincts, nouveaux usernames, usernames connus et consecutifs connus ;
- branchement initial dans `FollowersWorkflow` avec le champ bridge
  `maxConsecutiveKnownUsernames` et le fallback `150` ;
- ajout des stats `known_usernames_seen`, `new_usernames_seen` et
  `consecutive_known_usernames` dans les events followers ;
- les workflows hashtag/scraping/post likers doivent reprendre ce service dans
  une tranche separee pour eviter un refactor trop large.

## Cas corrige le 2026-05-29 - TikTok bridge home reset

Symptome technique :

- `search_bridge.py` et `followers_bridge.py` redefinissaient chacun une remise
  a Home TikTok entre deux queries/targets ;
- les bridges portaient des XPath Home en dur alors que les selectors de
  navigation existent deja dans `ui/selectors/navigation.py` ;
- chaque correction future du Home tab aurait pu diverger entre workflows.

Remediation retenue :

- extraction de `services/navigation_reset.py` ;
- utilisation de `NAVIGATION_SELECTORS.home_tab` comme source unique ;
- branchement dans les bridges search et followers ;
- ajout de tests unitaires sur l'ordre des back presses et les selectors testes.

## Cas corrige le 2026-05-29 - Followers profile username selector

Symptome technique :

- `followers/profile_data.py` contenait encore un XPath fallback direct pour
  extraire un username depuis `content-desc` ;
- ce fallback est une signature UI TikTok et devait vivre dans le catalogue
  selectors, pas dans un mixin de workflow ;
- l'extraction username etait peu testable sans instancier le workflow.

Remediation retenue :

- extraction de `services/profile/username.py` ;
- ajout de `PROFILE_SELECTORS.username_content_description` ;
- conservation du comportement `unknown` si aucun username n'est trouve ;
- ajout de tests unitaires sur le selector principal et le fallback content-desc.

## Cas corrige le 2026-05-29 - Followers list row helpers

Symptome technique :

- `FollowersWorkflow` contenait directement la recherche des boutons Follow /
  Friends / Following, le matching vertical avec le username et le tap coordonne
  dans la zone username ;
- ce code est de la detection/navigation de liste, pas du sequencage metier du
  workflow ;
- le fallback de coordonnee `x=280` etait impossible a tester sans device.

Remediation retenue :

- extraction de `services/followers/listing.py` ;
- conservation du fallback coordonne comme constante centralisee et testee ;
- `FollowersWorkflow` garde la verification story apres tap, car elle fait partie
  du scenario followers ;
- ajout de tests unitaires sur overlap de bounds, matching username et tap point.

## Cas corrige le 2026-05-29 - Followers legacy scroll policy

Symptome technique :

- `FollowersWorkflow` calculait directement le nombre de scroll attempts a faire
  quand aucune row nouvelle n'etait visible ;
- cette logique reste un fallback technique legacy, mais elle doit etre explicite,
  pure et testee pendant qu'on migre vers les stops par usernames connus ;
- le workflow portait aussi le calcul du ratio visite/total.

Remediation retenue :

- extraction de `services/followers/scroll_policy.py` ;
- conservation exacte des seuils legacy : ratio connu et fallback par total visite ;
- `FollowersWorkflow` ne fait plus que logger la decision et utiliser le nombre
  de tentatives ;
- ajout de tests unitaires sur ratio, total inconnu, no-data et ratio cappe.

## Cas corrige le 2026-05-29 - Followers repository adapter

Symptome technique :

- `FollowersWorkflow` et ses mixins appelaient directement `_db` pour creer et
  terminer les sessions, verifier les interactions recentes, sauvegarder un
  profil, compter les followers deja visites et enregistrer les actions ;
- ce melange faisait du workflow un orchestrateur Android et un mini repository
  SQLite en meme temps ;
- chaque futur changement de schema TikTok aurait pu toucher le workflow.

Remediation retenue :

- extraction de `taktik/core/database/repositories/tiktok/followers_repository.py` ;
- le workflow conserve seulement `account_id` et `session_id` comme contexte ;
- les mixins passent par le repository pour les lectures/ecritures ;
- ajout de tests unitaires avec fake DB pour verrouiller les no-op sans compte,
  la creation de session et les ecritures d'interaction/profil.

## Audit ouvert le 2026-05-29 - Workflows business TikTok

Constat general :

- les workflows `ForYou` et `Search` partagent `BaseVideoWorkflow`, mais `Search`
  redouble encore une partie du traitement video deja present dans `ForYou` ;
- `ScrapingWorkflow` et `UnfollowWorkflow` n'heritent pas de `BaseTikTokWorkflow`
  et redefinissent stop/callbacks/scroll/pagination de leur cote ;
- `FollowersWorkflow` est le point le plus risque : il orchestre, accede a la DB,
  decide des skips, calcule les scrolls, clique par coordonnees et gere la
  navigation de recovery ;
- plusieurs workflows raisonnent encore en `scroll_attempts` alors que le produit
  doit raisonner en usernames/profils rencontres ou nouveaux profils decouverts ;
- il reste des signatures UI ou XPath fallback hors catalogue selectors :
  `profile_data.py`, `_internal/popup_handler.py`, certains commentaires/heuristiques
  de page detection ;
- les sleeps fixes restent nombreux et devront etre remplaces progressivement par
  des waits/detections quand le signal UI existe.

Priorite de refactor proposee :

1. Propager le service commun `services/followers/stop_policy.py` aux workflows
   hashtag/scraping/search/post likers, sans recreer de variante locale.
2. Sortir les ecritures et lectures TikTok DB de `FollowersWorkflow` vers un service
   repository metier injecte.
3. Extraire les helpers de liste TikTok : trouver rows, extraire username, cliquer
   une row sans coordonnee brute, scroller jusqu'a nouveaux usernames.
4. Rapprocher `ScrapingWorkflow` et `UnfollowWorkflow` de `BaseTikTokWorkflow` ou
   d'un contrat commun de lifecycle/callbacks.
5. Centraliser les derniers XPath/textes UI dans `ui/selectors/**` et ajouter les
   tests unitaires avant chaque extraction.

## Pattern cible

```text
React TikTok
  -> typed payload
  -> IPC handler
  -> repository/service data
  -> bridge runner
  -> Python bridge
  -> Bot TikTok workflow
  -> events
  -> session repository
  -> Live Center
```

## ORM ou query builder

L'idee est bonne a terme, mais l'ordre compte.

Priorite avant ORM :

1. stabiliser les repositories ;
2. retirer le SQL metier des handlers ;
3. typer les DTOs ;
4. rendre les migrations idempotentes ;
5. rendre la sync diagnostiquable ;
6. isoler le publish TikTok dans un contrat clair.

Ensuite, un query builder/ORM cote Electron pourra reduire les requetes manuelles. Le Bot Python ne doit recevoir un ORM que si on decide clairement qu'il possede certaines donnees.

## Anti-regression obligatoire

| Check | Attendu |
|---|---|
| Publish manuel | media, caption, hashtags, upload, success. |
| Publish scheduler | meme comportement que manuel. |
| Automation | events/stats coherents. |
| Stop/cancel | bridge ferme, session terminale, device libere. |
| Popups | permissions/contacts/consent traites. |
| Upload lent | pas de timeout fixe trop court. |
| Live Center | payload et stage visibles. |
| Sync | comptes, profils, analytics, medias diagnostiques. |
| Network | dedicated/hybrid/single active respectes. |
| Mirror | embedded et debug non regressifs. |

## Definition of Done

Une PR TikTok n'est pas done si elle ajoute :

- un run scheduler sans stop/cancel robuste ;
- un publish qui ne remonte pas ses stages ;
- une table sans migration/sync ;
- une requete SQL brute non justifiee ;
- un selector cache dans un workflow ;
- une logique popup non documentee ;
- un helper qui duplique `_internal`.

## Refactor opportunites

| Opportunite | Valeur |
|---|---|
| Decouper `tiktok.ts` | Lisibilite et tests par famille. |
| Event schema publish | Live Center fiable et debug plus simple. |
| Upload progress UI dump | Moins de faux echecs sur reseau lent. |
| Repository TikTok enrichi | Moins de SQL direct. |
| Shared video workflow | Moins de duplication For You/search/followers. |
