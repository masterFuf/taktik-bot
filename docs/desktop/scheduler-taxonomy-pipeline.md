# Scheduler â€” Taxonomy pipeline

## Ce qu'on fait maintenant

On repart sur un pipeline simple, global, et industrialisable :

1. **Exporter les distincts globaux** depuis SQLite
2. **Envoyer ce working set a une IA** pour produire une taxonomie propre
3. **Reinjecter la taxonomie / les aliases / les hashtags** en base
4. **Reclassifier les profils prioritaires**
5. **Faire consommer cette couche propre au Smart Target**

## Point important

La seed `scheduler-taxonomy-seed.ts` est seulement un **bootstrap de securite**.

Elle permet :

- d'avoir des tables fonctionnelles tout de suite
- de ne pas attendre la fin du pipeline complet

Mais **ce n'est pas la source de verite finale**.

La source de verite cible, c'est :

- le working set exporte
- les sorties IA nettoyees
- les tables V2 remplies

## Export du working set global

Commande :

```bash
npm run taxonomy:export
```

Par defaut, le script lit :

- `%APPDATA%/taktik-desktop/taktik-data.db`

Et ecrit :

- `docs/Scheduler/generated/TAXONOMY_WORKING_SET.json`

Options :

```bash
node scripts/taxonomy/export-working-set.cjs --db "C:\\path\\to\\taktik-data.db" --out "C:\\path\\to\\working-set.json"
```

## Generation du prompt de normalisation

Commande :

```bash
npm run taxonomy:prompt
```

Le script lit par defaut :

- `docs/Scheduler/generated/TAXONOMY_WORKING_SET.json`

Et genere :

- `docs/Scheduler/generated/TAXONOMY_NORMALIZATION_PROMPT.txt`

Ce fichier est celui que tu peux donner tel quel a Claude / une autre IA.

## Normalisation directe via OpenRouter

On peut maintenant sauter l'etape copier-coller du prompt et faire la normalisation directement depuis le desktop local :

```bash
npm run taxonomy:normalize
```

Le script :

- lit `docs/Scheduler/generated/TAXONOMY_NORMALIZATION_PROMPT.txt`
- recupere la cle OpenRouter depuis :
  1. `--api-key`
  2. `OPENROUTER_API_KEY`
  3. `taktik-config.json` dans `AppData/Roaming/taktik-desktop`
- appelle OpenRouter
- ecrit :
  - `docs/Scheduler/generated/TAXONOMY_NORMALIZED.json`

Options :

```bash
node scripts/taxonomy/run-openrouter-normalization.cjs --model "google/gemini-2.5-pro" --input "C:\\path\\to\\prompt.txt" --out "C:\\path\\to\\normalized.json"
```

## Import du resultat normalise

Quand l'IA a retourne un JSON propre, le poser par defaut ici :

- `docs/Scheduler/generated/TAXONOMY_NORMALIZED.json`

Puis lancer :

```bash
npm run taxonomy:import
```

Options :

```bash
node scripts/taxonomy/import-normalized-taxonomy.cjs --input "C:\\path\\to\\TAXONOMY_NORMALIZED.json" --db "C:\\path\\to\\taktik-data.db"
```

## Enrichissement par niche

La premiere normalisation globale peut etre encore trop compacte.  
Pour densifier rapidement les **sous-niches**, **segments**, et **hashtags** sans repartir de zero, on lance ensuite :

```bash
npm run taxonomy:enrich
```

Le script :

- lit `docs/Scheduler/generated/TAXONOMY_NORMALIZED.json`
- recroise avec `docs/Scheduler/generated/TAXONOMY_WORKING_SET.json`
- appelle OpenRouter niche par niche
- ecrit :
  - `docs/Scheduler/generated/TAXONOMY_ENRICHED.json`

Options :

```bash
node scripts/taxonomy/enrich-normalized-by-niche.cjs --niche "business_marketing" --model "google/gemini-2.5-flash"
```

Une fois le fichier enrichi genere, on peut l'importer directement :

```bash
node scripts/taxonomy/import-normalized-taxonomy.cjs --input "docs/Scheduler/generated/TAXONOMY_ENRICHED.json"
```

## Expansion par sous-niche

Pour pousser encore plus loin, on peut travailler **une sous-niche = une requete**.

Commande :

```bash
npm run taxonomy:subniches -- --niche business_marketing
```

Par defaut :

- on teste sur `business_marketing`
- chaque sous-niche genere son propre JSON
- les fichiers sont ranges en hierarchie :
  - `docs/Scheduler/generated/sub-niche-catalog/<niche_slug>/<sub_niche_slug>.json`

Le script demande :

- un pack global pour la sous-niche
- des packs locaux / linguistiques si pertinents
- des variantes France / Belgique / Suisse FR / Suisse DE / international EN quand le contexte le justifie
- des variantes orthographiques ou marketing utiles (sans spam)

Exemple de sortie :

- `docs/Scheduler/generated/sub-niche-catalog/business_marketing/social_media_agency.json`
- `docs/Scheduler/generated/sub-niche-catalog/business_marketing/digital_marketing_seo.json`
- `docs/Scheduler/generated/sub-niche-catalog/business_marketing/_index.json`

Ce mode est pratique pour :

- relire une grande niche avant de tout lancer
- pousser beaucoup plus de volume sur chaque sous-niche
- preparer ensuite un traitement / import plus fin

## Expansion de toutes les niches

Quand la qualite d'une niche test te convient, on peut derouler toute la taxonomie :

```bash
npm run taxonomy:subniches:all
```

Options utiles :

```bash
npm run taxonomy:subniches:all -- --limit-niches 3
npm run taxonomy:subniches:all -- --niche business_marketing --force
npm run taxonomy:subniches:all -- --model "google/gemini-2.5-flash" --temperature 0.45
```

Le runner :

- lit `TAXONOMY_ENRICHED.json`
- enchaine `expand-sub-niche-catalog.cjs` niche par niche
- saute automatiquement les niches deja generees sauf si `--force`
- garde les sorties hierarchiques dans :
  - `docs/Scheduler/generated/sub-niche-catalog/<niche_slug>/<sub_niche_slug>.json`

## Compilation du catalogue par sous-niche

Une fois les JSON hierarchiques generes, on peut les compiler en un payload unique directement importable :

```bash
npm run taxonomy:subniches:compile
```

Sortie par defaut :

- `docs/Scheduler/generated/TAXONOMY_SUBNICHE_COMPILED.json`

Le compileur :

- relit toute l'arborescence `sub-niche-catalog/`
- transforme les `global_hashtags` et `locale_profiles` en lignes `hashtag_catalog`
- fusionne ces hashtags avec ceux deja presents dans `TAXONOMY_ENRICHED.json`
- deduplique par `hashtag/platform/language/niche/sub-niche/segment/intent`

Puis on peut importer directement :

```bash
node scripts/taxonomy/import-normalized-taxonomy.cjs --input "docs/Scheduler/generated/TAXONOMY_SUBNICHE_COMPILED.json"
```

## Nettoyage des artefacts intermediaires

Une fois la passe complete terminee, on peut supprimer les vieux dumps de debug / legacy qui ne servent plus :

```bash
npm run taxonomy:cleanup
```

Le script supprime actuellement :

- `docs/Scheduler/generated/HASHTAG_EXPANSION_RAW_*.txt`
- `docs/Scheduler/generated/SUBNICHE_*.txt`
- `docs/Scheduler/generated/TAXONOMY_HASHTAG_EXPANDED.json`

Mode verification sans suppression :

```bash
node scripts/taxonomy/cleanup-generated-artifacts.cjs --dry-run
```

## Contenu du working set

Le JSON exporte contient :

- `niches`
- `subNiches`
- `businessCategories`
- `topTags`
- `aliasGroups`
- `summary`

L'objectif est d'avoir un **snapshot global et brut**, pas encore editorialise.

## Ce qu'on envoie ensuite a l'IA

Le working set sert de matiere premiere pour :

1. construire une taxonomie canonique
2. definir les aliases
3. definir les segments
4. generer les hashtags par niche / sous-niche / segment

Les prompts utilises sont documentes dans [Taxonomy prompts](scheduler-taxonomy-prompts.md).

## Etape suivante recommande

Des qu'on a le premier export :

1. on le donne a Claude
2. il nous renvoie :
   - `niches`
   - `sub_niches`
   - `segments`
   - `aliases`
   - `hashtags`
3. on importe tout ca dans SQLite
4. on refait le Smart Target sur cette base nettoyee

## But produit

On veut eviter de recalculer toute une pseudo-taxonomie en live, compte par compte.

On veut au contraire :

- une **taxonomie globale**
- des **profils rattaches a cette taxonomie**
- un **catalogue hashtags stable**

Puis seulement apres, du scoring et du matching par compte.
