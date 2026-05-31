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
- le contexte runtime normalise de l'agent ;
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
  contracts.py
  agent_context.py
  agent_ai.py
  workflow_manifest.py
  plan_io.py
  registry.py
  executor.py
  scenarios/
    instagram_feed_autopilot.py
```

### Notes

- `taktik_agent_workflow.py` peut rester temporairement comme facade historique.
- Son role cible est de devenir un scenario/autopilot branche sur les contrats du noyau.
- Le scenario Instagram actuel ne doit pas dicter a lui seul l'architecture finale de `core/agent`.

## Lots recommandes

### Lot A - Contrat et boundaries

- introduire `contracts.py` ;
- documenter `core/agent` comme runtime kernel transverse ;
- retirer l'import direct `bridges.common.ai_service` de `taktik_agent_workflow.py` via injection.

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

### Lot D - Extension multi-plateforme

- brancher TikTok et les autres workflows sur le meme registre ;
- garder le Front comme planner premium.

## Point d'attention

Le Bot doit rester utilisable sans le Front.

Donc :

- un bridge peut injecter notifier, provider AI, plan et contexte premium ;
- mais le noyau `core/agent` doit rester appelable depuis Python seul avec les memes contrats.
