# [Bot] Cible `core/agent` - runtime kernel

## Pourquoi ce document existe

`taktik/core/agent` n'est pas un workflow Instagram mal range.

La cible produit est differente :

- le Front premium prepare la strategie, les triggers, les conditions produit et les campagnes ;
- le Bot execute localement les workflows reels, protege le runtime Android et remonte des events ;
- `core/agent` doit donc devenir le noyau d'execution d'un plan, pas un gros scenario Instagram opaque.

## Role cible de `taktik/core/agent`

Owner : runtime/app transverse.

Ce package doit porter :

- les contrats d'orchestration (`AgentPlan`, `PlanStep`, `WorkflowInvocation`, `AgentEvent`) ;
- les ports d'injection runtime (`AgentAIService`, factories, notifiers futurs) ;
- le contexte runtime normalise de l'agent ;
- les erreurs runtime structurees ;
- le registre de workflows executables ;
- l'executor qui deroule un plan ;
- les adapters/notifiers injectes par les bridges ou par un appelant standalone ;
- des scenarios internes transitoires quand un autopilot historique n'a pas encore ete replie dans le noyau.

Ce package ne doit pas porter durablement :

- les details UI ou selectors d'une plateforme ;
- un import direct a `bridges.common.*` pour construire son provider AI ou son IPC ;
- un faux "workflow universel" qui contient en dur tout Instagram, TikTok et le scheduler premium.

## Separation Front / Bot

### Front premium

Le Front decide :

- quelle campagne ou routine lancer ;
- quelles conditions produit et quels triggers autorisent l'execution ;
- quels workflows combiner ;
- quelles variables de haut niveau envoyer au Bot.

### Bot

Le Bot execute :

- un plan deja resolu ;
- les checks runtime observables localement ;
- les workflows reels `social_media/**` ;
- la telemetrie et les erreurs machine-readable.

En resume :

- strategie cross-workflow = Front ;
- execution locale robuste = Bot.

## Contrats cibles minimaux

### `WorkflowInvocation`

Decrit une etape executable :

- `platform`
- `workflow_id`
- `params`

### `PlanStep`

Decrit une etape du plan :

- `step_id`
- `kind`
- `workflow`
- `conditions`
- `metadata`

### `AgentPlan`

Decrit un plan premium ou standalone :

- `plan_id`
- `source`
- `platform`
- `steps`
- `variables`
- `metadata`

### `AgentEvent`

Decrit ce que le Bot remonte a l'appelant :

- statut courant
- etape en cours
- resultat
- erreur
- stats

## Cible de structure

Sans big-bang, la cible de structure devient :

```text
taktik/core/agent/
  __init__.py
  kernel/
    contracts.py
    ports.py
    errors.py
    context.py
    registry.py
    executor.py
    runtime.py
  io/
    manifest.py
    plan.py
    events.py
  decision/
    agent_ai.py
  scenarios/
    instagram_feed_autopilot.py
```

### Notes

- `scenarios/instagram_feed_autopilot.py` porte le scenario Instagram-first historique.
- Son role cible reste de devenir un scenario/autopilot branche sur les contrats du noyau.
- Le scenario Instagram actuel ne doit pas dicter a lui seul l'architecture finale de `core/agent`.
- `kernel/contracts.py` ne porte que les dataclasses de plan/event. Les interfaces injectees vivent dans `kernel/ports.py` pour eviter de melanger contrat de donnees et ports runtime. Les erreurs machine-readable du noyau vivent dans `kernel/errors.py`.

## Lots recommandes

### Lot A - Contrat et boundaries

- introduire `contracts.py` ;
- documenter `core/agent` comme runtime kernel transverse ;
- retirer l'ancien import direct `bridges.common.ai_service` du scenario agent via injection.

### Lot B - Scenario legacy

- repositionner `TaktikAgentWorkflow` comme scenario/autopilot historique ;
- conserver son comportement Instagram-first ;
- limiter ses dependances directes a `social_media/instagram/**`, `database/**` et services injectes.

### Lot C - Noyau d'execution

- lire `workflows.manifest.json` comme source des IDs canoniques ;
- convertir les payloads JSON Front/CLI en `AgentPlan` valide ;
- introduire `registry.py` ;
- introduire `executor.py` ;
- faire consommer au Bot un `AgentPlan` explicite.

Etat courant :

- `io/manifest.py` lit le manifest transversal et valide les IDs de workflows ;
- `io/plan.py` convertit un payload JSON-safe en `AgentPlan` ;
- `io/events.py` convertit les `AgentEvent` en payloads JSON-safe pour les futurs bridges ;
- `kernel/ports.py` porte les ports d'injection IA utilises par `decision/` et les scenarios historiques ;
- `kernel/errors.py` expose `MissingWorkflowHandlersError` avec un payload JSON-safe pour les futurs bridges ;
- `kernel/runtime.py` fournit une facade parse/execute qui depend d'un `WorkflowRegistry` injecte ;
- `WorkflowRegistry` et `AgentRuntime` exposent une prevalidation des handlers manquants pour un `AgentPlan` valide, afin qu'un appelant Front/CLI puisse detecter les workflows non branches avant execution ;
- `AgentPlanExecutor` refuse maintenant un plan dont au moins un workflow n'a pas de handler enregistre avant d'emettre le premier event, pour eviter les demi-executions ;
- `TaktikAgentWorkflow` accepte deja `agent_plan` / `agentPlan`, le valide et l'expose dans `AgentContext` sans l'executer ni ajouter de nouvel event stdout.
- l'arborescence physique est maintenant scopee : `kernel/`, `io/`, `decision/`, `scenarios/`. La racine du package expose seulement la facade publique `__init__.py`.

### Lot D - Extension multi-plateforme

- brancher TikTok et les autres workflows sur le meme registre ;
- garder le Front comme planner premium.
- avant de brancher un workflow Android reel, ajouter son handler explicite dans le registre de l'appelant et verifier la couverture avec `missing_workflow_handlers()`.

Etat courant :

- `social_media/tiktok/workflows/publish/agent_handler.py` expose le premier handler reel branchable dans `WorkflowRegistry` : `tiktok.standalone.upload_post`.
- Le handler TikTok publish reste injectable : il recoit `device`, `device_id`, notifier et factory de workflow depuis l'appelant. Il ne cree pas de connexion device et ne change pas le bridge existant.
- `social_media/youtube/workflows/publish/agent_handler.py` applique le meme pattern pour `youtube.publish.upload_post`, avec normalisation des parametres bridge-compatible.
- `social_media/tiktok/actions/business/workflows/followers/agent_handler.py` applique le pattern aux followers TikTok via `tiktok.automation.followers`. Ce handler reste single-target : un plan multi-cibles doit composer plusieurs `PlanStep`, plutot que cacher une boucle bridge dans le handler.
- `social_media/tiktok/actions/business/workflows/for_you/agent_handler.py` applique le pattern au feed For You via `tiktok.automation.for_you`, en normalisant les parametres video et en forwardant les callbacks sans reprendre le startup bridge.
- `social_media/tiktok/actions/business/workflows/search/agent_handler.py` applique le pattern aux variantes Search/Hashtag/Target (`tiktok.automation.search`, `tiktok.automation.hashtag`, `tiktok.automation.target`). Chaque invocation reste single-query ; les lots multi-query historiques du bridge deviennent une composition explicite de steps.
- Les primitives communes de ces adapters TikTok vivent sous `social_media/tiktok/actions/business/workflows/_internal/agent_runtime.py`. Elles restent plateforme/workflow-locales : merge payload, coercition de parametres et forwarding notifier, sans import bridge ni logique de planning.
- `social_media/tiktok/actions/business/workflows/unfollow/agent_handler.py` applique le pattern a `tiktok.standalone.tiktok_unfollow`, avec mapping explicite `skipFriends` -> `include_friends` pour conserver le sens historique du bridge.
- `social_media/tiktok/actions/business/workflows/scraping/agent_handler.py` applique le pattern a `tiktok.automation.scraping` et `tiktok.standalone.tiktok_scraping`. La persistence DB du bridge n'est pas reprise dans le handler ; un appelant peut injecter un `profile_sink` s'il veut enregistrer les profils.
- `social_media/tiktok/actions/business/workflows/dm/agent_handler.py` applique le pattern a `tiktok.automation.dm_read` et `tiktok.automation.dm_send`.
- `social_media/tiktok/actions/business/workflows/dm/outreach.py` porte maintenant la logique metier cold outreach ; `dm_outreach_bridge.py` injecte seulement le notifier stdout JSON et la dedup SQLite. Le handler Agent outreach pourra etre ajoute dans un lot separe avec ces memes injections.
- `social_media/tiktok/actions/business/workflows/dm/agent_handler.py` expose aussi `tiktok.standalone.tiktok_dm_outreach`, en reutilisant les injections notifier/dedup du workflow extrait.

## Point d'attention

Le Bot doit rester utilisable sans le Front.

Donc :

- un bridge peut injecter notifier, provider AI, plan et contexte premium ;
- mais le noyau `core/agent` doit rester appelable depuis Python seul avec les memes contrats.
