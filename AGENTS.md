# AGENTS.md - Bot Python TAKTIK

## Vue d'ensemble

Le dossier `bot/` contient le moteur open-source d'automatisation Android. Il pilote Instagram, TikTok, YouTube et les modules partages via `uiautomator2`, ADB, des workflows Python et des bridges JSON utilises par l'application Electron.

Le Bot doit rester utilisable seul, sans l'application desktop premium. Quand Electron le lance, la communication se fait par bridges Python et messages JSON stdout.

## Zones principales

| Zone | Role |
|---|---|
| `bridges/` | Adaptateurs app desktop -> Bot. Un bridge lit un payload, execute un workflow et emet des events JSON. |
| `taktik/core/social_media/instagram/` | Workflows et actions Instagram. |
| `taktik/core/social_media/tiktok/` | Workflows et actions TikTok. |
| `taktik/core/social_media/youtube/` | Workflows YouTube. |
| `taktik/core/shared/` | Briques Android/ADB/actions communes. |
| `taktik/core/database/` | SQLite local, schemas, migrations, repositories et services legacy. |
| `tests/unit/` | Tests unitaires et anti-regression Python. |
| `scripts/` | Audits, build exe, checks manifest et outils de debug. |

## Taxonomie cible `taktik/core`

Le Bot ne doit pas recopier a l'identique la taxonomie du Front, mais il doit appliquer la meme logique de fond : une separation nette entre code specifique a une plateforme, briques partagees, persistence, runtime applicatif et compat legacy.

Traduction cote Bot :

| Famille | Emplacement cible | Ce qui y vit | Ce qui ne doit pas y vivre |
|---|---|---|---|
| Plateforme | `taktik/core/social_media/<platform>/` | Workflows, actions, selectors, services metier propres a Instagram/TikTok/YouTube/Threads. | Helpers transverses Android, repositories DB, compat generique, utilitaires "globaux". |
| Shared technique | `taktik/core/shared/` | Primitives Android/ADB/input/actions/platform reutilisables. | Logique metier d'une seule plateforme, selectors Instagram/TikTok, ecritures SQLite directes. |
| Persistence | `taktik/core/database/` | Schema, migrations, modeles, repositories, facade legacy transitoire. | Workflows Android, selectors UI, branches clone/compat, logique de bridge. |
| Runtime/app services | `taktik/core/app/*`, `agent` | Services applicatifs ou integrations transverses avec owner explicite. | Code place "la par confort" sans owner nomme ni frontiere documentee. |
| Compat/legacy | `taktik/core/compat`, `clone` | Adaptation legacy, variantes d'app/package, transitions temporaires. | Nouvelle logique metier par defaut si une place plus claire existe. |

Regles macro :

- Ne pas creer un nouveau dossier racine sous `taktik/core` sans documenter son owner, son role et pourquoi il ne rentre ni dans `social_media`, ni dans `shared`, ni dans `database`.
- Un module `shared` ne doit pas importer `social_media/<platform>` sauf exception de compat documentee.
- Un module specifique a une plateforme ne doit pas finir dans `shared` juste parce qu'il est reutilise par deux workflows de cette meme plateforme.
- Ne pas creer de dossier `shared/utils/**` generique. Les helpers partages doivent vivre sous un owner de capacite explicite, par exemple `shared/actions/**`, `shared/device/**` ou `shared/input/**`.
- Si un module ecrit en SQLite, il doit passer par `taktik/core/database/**` ou un repository/service de cette couche. Pas de persistence metier dispersee dans `shared`, `bridges` ou `social_media/**/services`.
- `taktik/core/shared/device/**` est l'owner canonique des primitives device/ADB/ATX partagees. Ne pas recreer `taktik/core/device/**` : les anciens imports internes ont ete migres vers `shared/device/manager.py`.
- Une facade plateforme sous `taktik/core/social_media/<platform>/**/device/` est acceptable seulement si elle ajoute un comportement plateforme explicite. Un `DeviceManager` place a cet endroit doit etre un shim ou une specialisation documentee, pas une duplication generique de `shared/device/manager.py`.
- Si un module top-level `taktik/core/<family>` est en pratique specifique a une seule plateforme, l'implementation doit vivre sous `taktik/core/social_media/<platform>/...`. Ne pas garder une facade racine par confort si les imports internes peuvent viser l'owner direct.
- Pour les anciennes facades mono-plateforme, preferer l'import owner direct des que les consommateurs internes sont migrables. Ne pas recreer `taktik/core/recorder` ou `taktik/core/media` pour masquer du code Instagram-specific.
- Dans une plateforme, eviter les packages `utils/**` generiques quand un owner explicite existe. Exemple : la configuration de logs Instagram vit sous `social_media/instagram/observability/**`.
- Dans les workflows plateforme, preferer `support/**` ou un owner metier nomme a `helpers/**` quand le code sert un runtime precis. Exemple : le support d'`InstagramAutomation` vit sous `social_media/instagram/workflows/support/**`.
- Dans les services plateforme, regrouper les familles de flow ou de surface sous un sous-package nomme plutot qu'une liste plate prefixee. Exemples : les services TikTok publish vivent sous `social_media/tiktok/services/publish/**`, les services followers sous `social_media/tiktok/services/followers/**`, les services profil sous `social_media/tiktok/services/profile/**`, les resets navigation sous `social_media/tiktok/services/navigation/**`, et le lifecycle/package runtime sous `social_media/tiktok/services/runtime/**`.
- Un module sous `taktik/core/**` ne doit pas importer directement `bridges.common.*` pour obtenir son IPC, son AI service ou un autre adaptateur desktop. Le bridge ou le workflow appelant doit injecter un notifier/service optionnel depuis l'exterieur. `core/app/email/gmail/workflows/account.py` suit maintenant cette regle via un notifier injecte.
- `taktik/core/agent/**` reste l'owner du noyau d'orchestration transverse. Les bridges lui injectent notifier, provider AI et contexte premium ; ils ne doivent pas devenir l'owner durable de la logique d'orchestration.
- Dans `taktik/core/agent/**`, utiliser les owners internes directs : `kernel/` pour contrats/contexte/registry/executor/runtime, `io/` pour manifest/plan/events, `decision/` pour la decision IA, `scenarios/` pour les autopilots legacy. La racine du package doit rester une facade publique via `__init__.py`, pas une liste de modules plats.
- Quand un workflow `core/social_media/**` a besoin d'emettre des events live, il doit recevoir un notifier injecte ou optionnel. Ne pas instancier `bridges.common.ipc.IPC()` directement dans le workflow.
- Les emitters `core/social_media/**` ne doivent pas importer un bridge pour envoyer stdout. Le bridge doit enregistrer un adapter/callback, et le core doit rester no-op en standalone si aucun adapter n'est injecte.
- `taktik/core/app/ai/**` est l'owner des integrations IA reutilisables par le Bot. Utiliser `app/ai/providers/**` pour les providers runtime comme OpenRouter et `app/ai/comments/**` pour l'IA commentaire/persona. `bridges/common/ai_service.py` ne doit rester qu'un shim de compatibilite vers `taktik.core.app.ai.providers.openrouter`.
- Les petites surfaces runtime applicatives migrees vivent sous `taktik/core/app/**`. `app/config/**` porte la configuration runtime et `app/security/**` porte la protection runtime. Ne pas recreer `taktik/core/config/**` ou `taktik/core/security/**`.
- Dans `taktik/core/app/email/**`, classer les integrations par provider puis par responsabilite. Pour Gmail, `gmail/workflows/**` porte les workflows runtime et `gmail/ui/**` porte les selectors/textes UI. Ne pas recreer `taktik/core/email/**`.
- Les dossiers `agent`, `compat`, `clone` doivent rester auditables. `ai`, `email`, `config` et `security` vivent sous `taktik/core/app/**`; `device` vit sous `shared/device/**`; `media` et `recorder` vivent chez leur owner Instagram. Avant tout deplacement, verifier si on clarifie vraiment l'ownership ou si on deplace seulement le foutoir.
- Sous `taktik/core/compat`, le framework de compatibilite selectors/versioning doit vivre sous `compat/selectors/**`. Ne pas recreer de modules top-level `compat/selector_registry.py`, `compat/selector_tracer.py` ou `compat/setup.py` ; la racine du package est seulement une facade publique via `__init__.py`.
- `taktik/core/clone/**` est l'owner transversal des variantes Android par package : detection de clones, package actif, proxy device clone-aware et patch de selectors par package. Ne pas y ajouter de logique metier Instagram/TikTok qui appartient a `social_media/<platform>`.
- Dans `taktik/core/clone/**`, utiliser les owners internes directs : `detection/` pour le scan ADB des packages, `packages/` pour les metadonnees package/prefix, `device/` pour le proxy clone-aware, `selectors/` pour le patch des catalogues selectors. La racine du package expose seulement la facade publique.
- `taktik/core/compat/selectors/**` est l'owner de la compatibilite selectors par version et du tracing. Le nouveau code interne doit importer cet owner direct plutot que les shims top-level `compat/*.py`.
- Pas de nouveau dossier fourre-tout `utils`, `helpers`, `misc`, `common` au niveau `taktik/core`. Preferer un owner clair.

## Refactor structurel Bot

Quand le chantier porte sur l'arborescence ou la responsabilite des dossiers, la methode obligatoire est :

1. Cartographier avant de deplacer : dossier -> owner -> imports entrants -> imports sortants -> proposition.
2. Refactorer par petits lots coherents : database, shared Android, compat/clone, media/integrations, puis plateformes.
3. Eviter le big-bang : garder des re-exports ou wrappers temporaires seulement si la compat est documentee et limitee dans le temps.
4. Verifier les bridges, les imports et les tests du lot avant commit.
5. Mettre a jour `AGENTS.md` et la documentation dans le meme changement si la structure ou les regles evoluent.

Definition simple :

- `social_media/<platform>` = code metier plateforme.
- `shared/` = primitives techniques partagees.
- `database/` = persistence.
- le reste = runtime/app/compat avec owner explicite, jamais zone tampon.

## Regles anti-regression Bot

### Avant de modifier un workflow

- Lire le workflow, le bridge qui l'appelle et le handler Electron associe si le workflow est lance depuis `front/`.
- Verifier le contrat d'entree et de sortie : payload JSON, champs attendus, events stdout, erreurs possibles.
- Identifier les tables SQLite ecrites ou lues par le workflow.
- Verifier si le meme comportement existe cote Instagram/TikTok pour eviter une divergence non voulue.

### Bridges JSON

- stdout doit rester reserve aux messages JSON consommables par Electron quand le bridge est lance par le desktop.
- Les logs humains doivent aller vers stderr ou logger configure, pas casser le flux JSON.
- Chaque event ajoute doit etre documente cote Electron et teste avec le handler qui le consomme.
- Ne pas renommer un champ d'event sans compatibilite ou migration du handler.
- Un bridge doit rester un adaptateur : lecture payload, appel workflow, emission events. La logique metier durable doit rester dans le workflow/service/repository.
- Toute modification de bridge doit verifier `bridges/bridges.manifest.json`, `bridges/launcher.py` et `front/electron/utils/paths.ts` via le script d'audit si le nom ou le chemin change.

### SQLite Bot

- Le Bot peut ecrire ses faits d'automatisation quand il tourne en standalone : profils vus, interactions, sessions, stats, follow/follower sync.
- Les ecritures DB doivent passer par un repository ou par un service legacy clairement identifie. Ne pas ajouter de nouveau SQL direct dans un workflow si un repository existe.
- Les repositories SQLite vivent dans `taktik/core/database/repositories/<domaine>/`. Ne pas creer de repository DB dans `taktik/core/social_media/**/services`, `workflows` ou un package parallele.
- Le nom du package repository doit refleter le vrai domaine de donnee : `instagram`, `tiktok`, `gmail`, etc. Exemple : la table `gmail_accounts` appartient a `repositories/gmail/`, meme si YouTube la consomme aussi.
- Les faits de messagerie multi-plateformes comme `sent_dms` appartiennent a `repositories/messaging/`. Les bridges peuvent garder une facade de compatibilite, mais pas de SQL direct.
- Une table analytique partagee comme `daily_stats` doit avoir son repository explicite. Ne pas la laisser comme SQL cache dans `LocalDatabaseService`.
- Si un workflow legacy a encore besoin d'une decision DB composee (`already_processed`, `already_filtered`, bookkeeping d'interactions, etc.), creer ou etendre une facade nommee sous `taktik/core/database/*.py`. Ne pas recreer `social_media/**/common/database_helpers.py`.
- Le shim Instagram `DatabaseHelpers` a ete supprime apres migration interne. Ne pas le rebrancher dans un nouveau workflow ou module UI ; importer les services `taktik.core.database` directs.
- Dans `repositories/tiktok/**`, garder `TikTokRepository` comme facade publique stable tant que `LocalDatabaseService` l'expose, mais deplacer le SQL par domaine vers des owners internes explicites. Les comptes vivent sous `repositories/tiktok/account/account_repository.py`, les profils sous `repositories/tiktok/profile/profile_repository.py`, le lifecycle `tiktok_sessions` sous `repositories/tiktok/session/session_repository.py`, les interactions sous `repositories/tiktok/interaction/interaction_repository.py`, les profils filtres sous `repositories/tiktok/filtering/filtered_profile_repository.py` et les stats journalieres sous `repositories/tiktok/stats/stats_repository.py`.
- Si un workflow Instagram legacy manipule `following_sync`, `followers_sync` ou des lookups d'historique de follow pour la decision d'unfollow, etendre `taktik/core/database/instagram_follow_graph.py` au lieu de reintroduire du SQL direct dans la plateforme.
- Quand une facade Instagram legacy devient stable sur une vraie table, promouvoir son SQL dans `taktik/core/database/repositories/instagram/<domaine>/` et ne laisser dans `taktik/core/database/*.py` qu'une orchestration de compatibilite. `following_sync` / `followers_sync` appartiennent maintenant a `repositories/instagram/social_graph/`.
- `taktik/core/database/local/schema.py` doit rester un orchestrateur. Les DDL doivent etre classees par domaine dans `taktik/core/database/local/schemas/<domaine>.py`.
- `taktik/core/database/local/migrations.py` doit rester un orchestrateur. Les steps de migration doivent etre classees par domaine dans `taktik/core/database/local/migration_steps/<domaine>.py`, sans changer l'ordre historique par accident.
- `taktik/core/database/local/service.py` peut garder des wrappers publics legacy, mais le SQL metier par domaine doit vivre dans le repository du domaine.
- Dans la couche repository/database shared, utiliser `logger` et jamais `print(...)`, pour ne pas polluer stdout ni casser les bridges JSON.
- Toute modification de schema doit mettre a jour ensemble : `taktik/core/database/local/schema.py`, `migrations.py`, repositories/modeles concernes, tests, et docs.
- Si une table est partagee avec Electron, comparer aussi `front/electron/database/schema.sql`, `schema.ts` et `migrations.ts`.
- Une migration doit etre idempotente et compatible avec une base deja peuplee.
- Ne pas creer de table miroir ou de colonne AI/cache sans definir qui est source de verite : Bot, Electron ou sync.

### Contrat avec Electron et standalone

- Le Bot open-source ne doit pas dependre d'une feature premium Electron pour fonctionner en standalone.
- Quand une option est ajoutee dans le desktop, verifier le comportement par defaut si le Bot est lance sans cette option.
- Les workflows appeles par le scheduler et par l'UI doivent partager le meme sens metier que le workflow Bot. Si le scheduler ajoute du contexte, ce contexte doit rester optionnel ou documente.
- Les erreurs doivent etre machine-readable pour Electron et comprehensibles en standalone : type/code, message, contexte minimal.
- Les statuts terminaux doivent rester compatibles avec Electron : success/completed, failed, stopped/cancelled selon le contrat du workflow.

### Matrice workflow

Pour tout nouveau workflow ou changement de workflow existant, verifier :

- bridge et payload d'entree ;
- workflow Bot et actions Android ;
- events stdout consommes par Electron ;
- ecritures SQLite et repository/service proprietaire ;
- handler Electron et Live Panel associes ;
- scheduler si le workflow peut etre planifie ;
- docs `bot/docs/**`, `front/docs/**` ou `taktik-bot/docs/admin/instagram/**` selon le perimetre ;
- tests unitaires, script d'audit ou verification manuelle reproductible.

### SOLID cote Bot

- Single Responsibility : un bridge adapte un payload et emet des events. Il ne doit pas contenir la logique metier complete du workflow.
- Single Responsibility : un workflow orchestre des actions. Il ne doit pas devenir repository SQLite, selecteur UI, moteur d'IA et logger custom en meme temps.
- Single Responsibility : une action Android fait une action Android testable. Elle ne decide pas de l'ownership DB.
- Open/Closed : ajouter un workflow ou une plateforme doit passer par registres/manifests/classes dediees, pas par modification fragile d'un gros bloc procedural.
- Liskov : les workflows specialises doivent respecter le contrat du workflow de base : entree, resultat, erreurs, events et cleanup.
- Interface Segregation : preferer de petits helpers cibles (`profile extraction`, `following sync`, `media push`) a un helper global qui sait tout faire.
- Dependency Inversion : les workflows dependent de services/repositories abstraits ou clairement injectes, pas de connexions SQLite ou commandes ADB cachees partout.
- Un workflow garde le sequencage metier, mais les decisions reutilisables doivent vivre dans un service teste. Exemple : fin de target basee sur usernames distincts connus/nouveaux, pas sur un compteur de scroll local.
- Ne pas garder de wrappers purement delegants dans un workflow apres extraction. Si le wrapper n'ajoute pas de sens metier, appeler directement le service pour rendre le sequencage lisible.

### Android, selectors et waits

- Ne jamais hardcoder directement dans un workflow/action un `resource-id`, XPath, `text`, `content-desc`, `hint` ou libelle visible Instagram/TikTok.
- Toute signature UI doit etre centralisee dans les modules `taktik/core/social_media/**/ui/selectors/**` ou `ui/language.py`, avec un commentaire d'historique si elle vient d'un dump reel.
- Sous `social_media/<platform>/ui/selectors`, classer d'abord par perimetre UI reel (`shell`, `surfaces`, `flows`, `support`) plutot que par fourre-tout technique. Un dev doit pouvoir deviner l'emplacement d'un selector a partir de l'ecran ou du flow Instagram/TikTok concerne.
- Un fichier historique top-level sous `ui/selectors/` n'est acceptable que comme shim de transition court. Des que les imports internes du monorepo sont migres et que la rupture de compatibilite est acceptee, supprimer le shim au lieu de le laisser vivre indefiniment.
- Quand une surface devient trop large pour un seul catalogue public, exposer plusieurs catalogues specialises (`*_DETAIL_SELECTORS`, `*_COMMENTS_SELECTORS`, etc.) avant d'ajouter de nouvelles clefs au catalogue legacy global. Le gros catalogue historique peut rester comme facade de compat, pas comme point d'extension par defaut.
- Ne pas ajouter de nouveau test, workflow ou service interne qui importe un module top-level legacy `ui/selectors/<name>.py` une fois qu'un owner scope existe sous `shell/`, `surfaces/`, `flows/` ou `support/`.
- Si un workflow a besoin d'un fast-path sur un dump XML, exposer une fonction/propriete depuis le catalogue selectors au lieu de mettre les strings dans le workflow.
- Eviter les sleeps fixes quand un wait conditionnel ou une detection UI est possible.
- Les selectors reutilisables doivent vivre dans des modules dedies ou partages, pas etre recopies dans plusieurs workflows.
- Tout changement de navigation Android doit etre valide sur le workflow manuel et sur le lancement bridge si les deux existent.
- Le comportement clone/package name doit etre explicite et teste quand on touche aux apps Instagram/TikTok clonees.

### Securite et donnees sensibles

- Ne jamais logger mot de passe, token, cookie, proxy credential, payload complet de compte ou contenu DM sensible.
- Les fichiers de config temporaires doivent etre limites au strict necessaire, stockes dans un emplacement controle et nettoyes quand le flux le permet.
- Les dumps UI, screenshots et traces de debug peuvent contenir des donnees personnelles : ne pas les ajouter aux tests/docs sans anonymisation.

### Tests et checks

- Lancer les tests unitaires cibles avec `pytest` quand une logique Python change.
- Pour DB/schema : lancer au minimum `pytest tests/unit/test_db_schema.py` et les tests du repository/service touche.
- Pour bridge : tester le bridge ou le script d'audit associe quand disponible (`scripts/check_bridge_manifest.py`, `scripts/audit_bridge_handler_usage.py`, etc.).
- Pour workflow/registry : lancer `python scripts/audit_workflow_registry.py` si la declaration, le manifest ou la famille de workflow change.
- Pour documentation schema partagee : lancer `python scripts/audit_sqlite_schema_docs.py` quand une table/colonne SQLite est ajoutee ou renommee.
- Si un test ne peut pas etre lance, l'expliquer dans le recap.

## Definition de done Bot

Un changement Bot est termine seulement si :

- le contrat payload/event est compris et preserve ;
- les ecritures SQLite ont un proprietaire clair ;
- les tests cibles ou une verification manuelle pertinente ont ete faits ;
- les docs associees sont mises a jour ;
- les risques residuels sont annonces explicitement.

## Anti-patterns deja observes a ne pas reproduire

Ces exemples existent pour servir de radar avant de coder vite.

- Hardcoder dans un workflow TikTok/Instagram des `resource-id`, XPath, `text`, `content-desc` ou libelles visibles comme `Ajouter une description`, `Add a description`, `:id/g19`. La bonne place est `ui/selectors/**` ou `ui/language.py`.
- Mettre dans un workflow des helpers reutilisables comme `sanitize_caption`, `build_caption`, `get_tiktok_package`, `find_element`, `tap_element`, `is_keyboard_visible`. La bonne place est un service ou helper specialise, teste unitairement.
- Ajouter une logique d'arret basee sur un detail technique interne comme `20 scrolls` alors que le produit parle de usernames/profils rencontres. Le parametre expose a l'utilisateur doit correspondre au concept metier.
- Faire diverger les workflows target, hashtag et post likers alors qu'ils partagent la meme notion de "consecutive known usernames". La logique commune doit etre factorisee ou au minimum propager le meme contrat.
- Introduire une variante locale de policy d'arret dans un workflow TikTok. Utiliser le service commun de stop policy et etendre son contrat si le besoin metier evolue.
- Melanger extraction brute et inference IA dans les memes champs DB. Exemple : un `country` observe dans Instagram About ne doit pas etre ecrase par un pays deduit par l'IA ; il faut separer source factuelle et inference.
- Laisser un bridge contenir trop de metier durable. Un bridge adapte le payload et les events ; le workflow/service porte la logique.
- Modifier un workflow sans verifier le handler Electron, le scheduler, le live panel et les tests associes.

## Checklist audit workflow avant modification

- Ou sont les selectors et textes UI mobile ? Si c'est dans le workflow, extraire.
- Ou sont les helpers reutilisables ? Si c'est dans le workflow, extraire.
- Quel est le contrat bridge payload/events ? Verifier Electron avant de renommer/ajouter.
- Quelle donnee est ecrite ? Identifier le proprietaire DB et le repository/service.
- Le workflow manuel et le scheduler ont-ils le meme sens metier ?
- Existe-t-il un test unitaire ou un audit script pour verrouiller la regression ?
