"""Merge the region spellings that split one region across two filter entries.

The region dropdown in Target Search is built FROM THE DATA (`getRegionsByCountry` groups
whatever is stored). So a region written two ways appears twice in the list, and picking
one silently drops the other half of the profiles:

    New Aquitaine  216  +  Nouvelle-Aquitaine  155   -> one region, 371 profiles
    Rhône-Alpes    210  +  Auvergne-Rhône-Alpes 194  -> one region, 404 profiles
    Geneva         123  +  Genève               65   -> one canton, 188 profiles

Three families, all present in the base:

  * the English name of a French/Swiss region ("Brittany", "Geneva"),
  * the pre-2016 French region name ("Rhône-Alpes", "Bourgogne"), which the 2016 reform
    merged into a larger one — the model still answers with the old name,
  * accents and casing ("Zurich" vs "Zürich").

The target spelling is the French official current name for France and Switzerland, which
is what the rest of the base already uses (Grand Est, Île-de-France, Occitanie…). Other
countries keep the form they already have; nothing is translated for its own sake.

Both columns are rewritten — `social_profiles.location_region` and
`profile_qualification.location_region` — because the read does
COALESCE(qualification, legacy) and fixing one leaves the other to win somewhere else.

`updated_at` is bumped: without it the correction never leaves this machine.

Usage:
    python scripts/merge_duplicate_regions.py            # dry run
    python scripts/merge_duplicate_regions.py --apply

Close the desktop app first: it holds the same SQLite file.
"""

import argparse
import os
import sqlite3
import unicodedata
from collections import Counter

# Explicit, auditable list. Written against what the base actually holds — a mapping to a
# name that appears nowhere would silently create a THIRD spelling.
REGION_MERGES = {
    # France — English name -> French official name
    'new aquitaine': 'Nouvelle-Aquitaine',
    'brittany': 'Bretagne',
    'normandy': 'Normandie',
    'corsica': 'Corse',
    'grand est region': 'Grand Est',
    'ile-de-france': 'Île-de-France',
    'ile de france': 'Île-de-France',
    'provence-alpes-cote d azur': 'Provence-Alpes-Côte d\'Azur',
    "provence-alpes-cote d'azur": 'Provence-Alpes-Côte d\'Azur',
    # France — pre-2016 names folded into the region that absorbed them
    'rhone-alpes': 'Auvergne-Rhône-Alpes',
    'rhône-alpes': 'Auvergne-Rhône-Alpes',
    'auvergne': 'Auvergne-Rhône-Alpes',
    'bourgogne': 'Bourgogne-Franche-Comté',
    'franche-comte': 'Bourgogne-Franche-Comté',
    'franche-comté': 'Bourgogne-Franche-Comté',
    'languedoc-roussillon': 'Occitanie',
    'midi-pyrenees': 'Occitanie',
    'midi-pyrénées': 'Occitanie',
    'aquitaine': 'Nouvelle-Aquitaine',
    'limousin': 'Nouvelle-Aquitaine',
    'poitou-charentes': 'Nouvelle-Aquitaine',
    'alsace': 'Grand Est',
    'lorraine': 'Grand Est',
    'champagne-ardenne': 'Grand Est',
    'nord-pas-de-calais': 'Hauts-de-France',
    'picardie': 'Hauts-de-France',
    'basse-normandie': 'Normandie',
    'haute-normandie': 'Normandie',
    # Switzerland — English/German name -> French name, matching the rest of the base
    'geneva': 'Genève',
    'zurich': 'Zürich',
    'berne': 'Bern',
    'ticino': 'Tessin',
    'valais': 'Valais',
    'vaud': 'Vaud',
    'neuchatel': 'Neuchâtel',
    'fribourg': 'Fribourg',
    'basel-city': 'Bâle-Ville',
    'basel city': 'Bâle-Ville',
}


def fold(value):
    """Accent- and case-insensitive key, so 'Zürich' and 'Zurich' meet."""
    return ''.join(ch for ch in unicodedata.normalize('NFD', (value or '').lower())
                   if unicodedata.category(ch) != 'Mn').strip()


def diacritics(value):
    """How many accents the spelling carries."""
    return sum(1 for ch in unicodedata.normalize('NFD', value or '')
               if unicodedata.category(ch) == 'Mn')


def target_for(region, spellings_by_key):
    """The spelling this value should become, or None to leave it alone.

    Two passes: the explicit merge list first, then — for anything it does not name — the
    other spellings of the same accent-folded key.

    Within a fold group the winner is the spelling carrying the MOST accents, not the most
    frequent one. Frequency says nothing about correctness here: the base holds
    "Baden-Wurttemberg" (28) against "Baden-Württemberg" (10), "Cordoba" (11) against
    "Córdoba" (5) — in all five accent groups the majority is the degraded form, because a
    stripped accent is what a lossy pipeline produces, not a spelling anyone chose. The
    accented form is strictly the more informative one, so it wins; count only breaks ties
    between spellings equally accented (plain casing).
    """
    raw = (region or '').strip()
    if not raw:
        return None

    explicit = REGION_MERGES.get(raw.lower()) or REGION_MERGES.get(fold(raw))
    if explicit and explicit != raw:
        return explicit

    if explicit == raw:
        return None

    variants = spellings_by_key.get(fold(raw))
    if variants and len(variants) > 1:
        winner = max(variants.items(), key=lambda kv: (diacritics(kv[0]), kv[1]))[0]
        if winner != raw:
            return winner
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    parser.add_argument('--db', default=os.path.join(os.environ.get('APPDATA', ''), 'taktik-desktop', 'taktik-data.db'))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print('database not found: %s' % args.db)
        return 1

    con = sqlite3.connect('file:{}{}'.format(args.db.replace('\\', '/'), '' if args.apply else '?mode=ro'), uri=True)

    # Every spelling in use, per accent-folded key, to settle accent duplicates by weight.
    spellings_by_key = {}
    for table, column in (('social_profiles', 'location_region'), ('profile_qualification', 'location_region')):
        for region, count in con.execute(
                "SELECT {c}, COUNT(*) FROM {t} WHERE platform='instagram' AND {c} IS NOT NULL AND {c} != '' GROUP BY {c}"
                .format(t=table, c=column)):
            spellings_by_key.setdefault(fold(region), Counter())[region] += count

    # Merge, never rename. A target that appears nowhere in the column is not the other
    # half of a split region — rewriting to it would invent one more spelling and bump
    # `updated_at` on every row for no repair. The region column, for instance, holds
    # "Zurich" unanimously (177 rows); "Zürich" only exists as a CITY. Nothing is split
    # there, so nothing is merged there.
    existing = {spelling for variants in spellings_by_key.values() for spelling in variants}

    moves = Counter()
    skipped = set()
    plans = {}
    for table in ('social_profiles', 'profile_qualification'):
        rows = con.execute(
            "SELECT DISTINCT location_region FROM {t} WHERE platform='instagram' "
            "AND location_region IS NOT NULL AND location_region != ''".format(t=table)).fetchall()
        plan = []
        for (region,) in rows:
            target = target_for(region, spellings_by_key)
            if not target:
                continue
            if target not in existing:
                skipped.add('%s -> %s' % (region, target))
                continue
            plan.append((target, region))
            moves['%s -> %s' % (region, target)] += 1
        plans[table] = plan

    print('distinct region spellings : %d' % len(spellings_by_key))
    print('spellings to rewrite      : %d' % len(moves))
    print()
    for move, _ in sorted(moves.items()):
        print('    %s' % move)
    if skipped:
        print('\nskipped, target absent from the column (a rename, not a merge):')
        for move in sorted(skipped):
            print('    %s' % move)

    if not args.apply:
        print('\nDRY RUN — nothing written. Re-run with --apply.')
        return 0

    total = 0
    for table, plan in plans.items():
        for target, source in plan:
            cur = con.execute(
                "UPDATE {t} SET location_region = ?, updated_at = datetime('now') "
                "WHERE platform='instagram' AND location_region = ?".format(t=table),
                (target, source))
            total += cur.rowcount
    con.commit()
    print('\nwritten: %d rows across both columns' % total)
    con.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
