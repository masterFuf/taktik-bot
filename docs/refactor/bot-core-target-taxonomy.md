# Proposition - Taxonomie cible `taktik/core`

## Pourquoi la racine `core/` parait melangee

Aujourd'hui, `taktik/core` melange plusieurs natures de code au meme niveau :

- metier plateforme : `social_media/`
- technique partagee : `shared/`
- persistence : `database/`
- runtime/app services : `agent`, `ai`, `config`, `device`, `email`, `media`, `recorder`, `security`
- compat / legacy : `clone`, `compat`

Le probleme n'est pas seulement le nombre de dossiers. Le probleme est qu'on ne lit
pas assez vite *quelle famille* on est en train de traverser : metier, infra locale,
integration technique, ou compat.

## Recommandation

Je recommande une cible en **6 familles lisibles**, avec migration par lots et
sans recreer de shims racine quand les consommateurs internes peuvent etre
migres directement.

```text
taktik/core/
  social_media/          # code metier par plateforme
    instagram/
    tiktok/
    threads/
    youtube/

  shared/                # primitives Android/ADB/input/actions partagees
    actions/
    device/
    input/
    platform/

  database/              # schema, migrations, modeles, repositories, facades DB
    local/
    repositories/
    ...

  agent/                 # orchestration IA transverse, pilote par le Front premium
    kernel/
    io/
    decision/
    scenarios/

  app/                   # services runtime/app transverses a owner explicite
    ai/
    config/
    email/
    security/

  device/                # compat device restante vers shared/device, a reduire

  clone/                 # variantes Android/package-aware transverses

  compat/                # compatibilite selectors/versioning documentee
    selectors/
```

## Pourquoi cette cible

### `social_media/`

Ici ne vit que le metier propre a une plateforme :

- workflows
- actions
- selectors UI
- services metier plateforme

Ne doivent pas y vivre :

- repositories DB
- primitives device generiques
- wrappers shared juste "par habitude"

### `shared/`

Owner unique de :

- ADB / uiautomator2
- facades device
- actions techniques partagees
- briques de plateforme generiques

Ne doit pas importer `social_media/<platform>` hors compat documentee.

### `database/`

Owner unique de :

- schema
- migrations
- modeles
- repositories
- facades DB transitoires

### `app/`

Cette famille rend visible tout ce qui est "service applicatif transverse" sans
le melanger a la technique Android pure :

- `ai/`
- `config/`
- `email/`
- `security/`

`agent/` reste separe : il est le noyau d'orchestration transverse appele par le
Front premium, pas un simple provider applicatif.

### `agent/`

Owner de l'orchestration IA transverse :

- contrats et runtime d'execution de plans
- registry workflows injectee
- parsing/serialization manifest et plan
- scenarios historiques, dont l'autopilot Instagram-first

Ne doit pas importer `bridges.common.*` directement. Les bridges injectent les
notifiers, providers IA et handlers reels.

### `device/`

Il reste aujourd'hui comme boundary de compat vers `shared/device`. Tant que ses
consommateurs historiques ne sont pas tous migres, il ne doit plus recevoir de
nouvelle implementation autonome.

### `compat/`

Regle :

- tout ce qui vit ici doit documenter son consommateur et sa strategie de sortie
- ne pas recreer de modules top-level pour cacher des selectors ou bridges legacy

### `clone/`

Owner transverse des variantes Android par package. Il reste lisible a la racine
parce qu'il est utilise par plusieurs plateformes et n'est pas une compat passive.

## Variante conservative si on ne veut pas renommer la racine tout de suite

Si on veut **maximiser la securite** et **minimiser les moves**, la meilleure
etape intermediaire est :

```text
taktik/core/
  social_media/
  shared/
  database/
  agent/
  app/
  device/
  clone/
  compat/
```

...mais avec des **regles de lecture et d'ordre** explicites :

1. `social_media`, `shared`, `database` = familles coeur
2. `agent` = orchestration IA transverse
3. `app` = services runtime transverses (`ai`, `config`, `email`, `security`)
4. `device` = compat device restante vers `shared/device`
5. `clone`, `compat` = runtime clone/package-aware et compat selectors documentee

Cette variante bouge moins de chemins, mais elle ne corrige pas completement
l'impression de "racine en vrac".

## Etat physique conserve au 2026-05-31

La migration racine a commence le 2026-05-31 : les petites surfaces runtime
sont deplacees par lots vers `app/` sans shims legacy caches.

```text
taktik/core/
  social_media/          # metier plateforme
  shared/                # primitives techniques partagees
  database/              # persistence
    local/
      paths.py           # resolution chemin DB pour bridges standalone
    repositories/
      messaging/         # sent_dms / faits messaging multi-plateformes
    models/
      instagram_profile.py

  agent/                 # runtime kernel d'orchestration
    kernel/
    io/
    decision/
    scenarios/

  app/                   # services applicatifs runtime
    ai/
      providers/
      comments/
    config/
      runtime/
    email/
      gmail/
        workflows/
        ui/
    security/
      protection/
  device/                # compat vers shared/device
    compat/
  clone/                 # runtime clone/package-aware
    detection/
    packages/
    device/
    selectors/
  compat/                # compat/versioning selectors
    selectors/
```

Regle pratique : `app/` existe maintenant pour les services runtime deja
audites (`ai`, `config`, `email`, `security`). Ne pas y deplacer `agent/` par
confort : il reste le noyau d'orchestration transverse. Ne pas introduire
`runtime/` tant que `device/` n'a pas ete audite jusqu'aux derniers
consommateurs bridges/scripts.

## Recommandation pratique

Je recommande une migration en **2 etapes** :

### Etape A - maintenant

- documenter la cible
- continuer a nettoyer les imports et l'ownership
- ne pas renommer toute la racine
- privilegier les sous-packages internes quand une famille runtime est trop plate. Exemple applique : `taktik/core/agent` est maintenant classe en `kernel/`, `io/`, `decision/`, `scenarios/` sans deplacer toute la racine `core`.
- deplacer les services app deja clarifies sous `taktik/core/app/**` sans facade racine legacy.

### Etape B - plus tard, si on confirme l'arbitrage

- reduire puis supprimer `device/` si tous les consommateurs peuvent viser `shared/device`
- re-auditer `clone/` et `compat/` sans les fusionner par reflexe
- ne garder un re-export temporaire que si un consommateur externe non migrable est identifie et documente

## Lots de migration proposes

### Lot A1 - `compat/clone`

- cartographier `clone/` et `compat/`
- distinguer vrai clone package, vrai legacy, et depot passif

### Lot A2 - `app services`

- auditer `agent`, `ai`, `email`, `media`, `recorder`, `security`, `config`
- ecrire owner + role + entrants/sortants

### Lot A3 - cible `device` / runtime

- uniquement apres cartographie
- decider si la compat `device/` peut etre supprimee ou si un owner runtime dedie est encore necessaire

## Regles de classement a retenir

- un dossier racine doit repondre a une seule question d'ownership
- si on ne peut pas dire "c'est du metier plateforme / shared technique / DB / app service / compat", le classement est mauvais
- pas de nouveau fourre-tout racine
- pas de moves massifs sans couche de transition documentee
