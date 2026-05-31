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

Je recommande une cible en **5 familles lisibles**, avec migration par lots et
re-exports temporaires quand necessaire.

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

  app/                   # services runtime/app transverses a owner explicite
    agent/
    ai/
    config/
    email/
    media/
    recorder/
    security/

  runtime/               # runtime Android / device orchestration transverses
    device/

  compat/                # compatibilite et legacy documentes
    clone/
    legacy/
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

- `agent/`
- `ai/`
- `config/`
- `email/`
- `media/`
- `recorder/`
- `security/`

Aujourd'hui ces dossiers sont deja presents, mais leur mise a plat a la racine
les fait lire comme des pairs de `database/` ou `shared/`, alors qu'ils sont
d'une autre nature.

### `runtime/`

Je separe ici le runtime Android transverse qui n'est ni metier plateforme,
ni persistence, ni service applicatif.

Cas principal aujourd'hui :

- `device/`

Ce point est le seul qui demande un vrai arbitrage : si on veut respecter
strictement la taxonomie actuelle sans introduire `app/` et `runtime/`,
alors on peut garder `device/`, `agent/`, `ai/`, `config/`, etc. a la racine.
Mais la lisibilite restera moins bonne.

### `compat/`

Je recommande de ne plus avoir `clone/` et `compat/` comme voisins separables
au meme niveau que tout le reste.

Cible :

```text
compat/
  clone/
  legacy/
```

Regle :

- tout ce qui vit ici doit documenter son consommateur et sa strategie de sortie

## Variante conservative si on ne veut pas renommer la racine tout de suite

Si on veut **maximiser la securite** et **minimiser les moves**, la meilleure
etape intermediaire est :

```text
taktik/core/
  social_media/
  shared/
  database/
  compat/
  clone/
  agent/
  ai/
  config/
  device/
  email/
  media/
  recorder/
  security/
```

...mais avec des **regles de lecture et d'ordre** explicites :

1. `social_media`, `shared`, `database` = familles coeur
2. `agent`, `ai`, `config`, `device`, `email`, `media`, `recorder`, `security` = runtime/app owners
3. `compat`, `clone` = legacy/compat seulement

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

  ai/                    # integrations IA
    providers/
    comments/

  app/                   # services applicatifs runtime
    config/
      runtime/
    security/
      protection/
  email/                 # integration Gmail
    gmail/
      workflows/
      ui/
  media/                 # facade media legacy package-level
  recorder/              # facade recorder legacy
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

Regle pratique : avant d'introduire `app/` ou `runtime/` a la racine, on doit
avoir termine l'audit de chaque famille et verifier les imports bridges/scripts.
Sinon on ne ferait que deplacer le desordre dans un nouveau dossier.

## Recommandation pratique

Je recommande une migration en **2 etapes** :

### Etape A - maintenant

- documenter la cible
- continuer a nettoyer les imports et l'ownership
- ne pas renommer toute la racine
- privilegier les sous-packages internes quand une famille runtime est trop plate. Exemple applique : `taktik/core/agent` est maintenant classe en `kernel/`, `io/`, `decision/`, `scenarios/` sans deplacer toute la racine `core`.

### Etape B - plus tard, si on confirme l'arbitrage

- introduire `app/`
- introduire `runtime/`
- faire migrer `clone/` sous `compat/`
- garder des re-exports temporaires

## Lots de migration proposes

### Lot A1 - `compat/clone`

- cartographier `clone/` et `compat/`
- distinguer vrai clone package, vrai legacy, et depot passif

### Lot A2 - `app services`

- auditer `agent`, `ai`, `email`, `media`, `recorder`, `security`, `config`
- ecrire owner + role + entrants/sortants

### Lot A3 - cible `app/` / `runtime/`

- uniquement apres cartographie
- introduire dossiers aggregateurs et re-exports si on valide l'arbitrage

## Regles de classement a retenir

- un dossier racine doit repondre a une seule question d'ownership
- si on ne peut pas dire "c'est du metier plateforme / shared technique / DB / app service / compat", le classement est mauvais
- pas de nouveau fourre-tout racine
- pas de moves massifs sans couche de transition documentee
