"""Clear the AI qualifications that were written about profiles nobody ever read.

A scraping run kept qualifying profiles whose page had given NOTHING: the device returned a black
frame, `get_complete_profile_info` handed back a dict of defaults, and the run carried on because
that dict is truthy. The vision model then answered from the username alone — and answered
confidently: average confidence 0.95 on those rows, HIGHER than the 0.92 of the profiles it could
actually see. `bestwesternplusthionville` became Travel; `alexis_bdtt` became Lifestyle, female.

310 rows are in that state: a niche (and a gender, an age group, a confidence) sitting on a
`social_profiles` row with 0 followers, 0 following, 0 posts, no display name and no bio. 220 of
them come from a single day, 2026-08-19.

They are worse than unqualified, because they READ as qualified: Target Search's "no AI
qualification" filter tests what the qualification CONTAINS, so a profile carrying an invented
niche is invisible to the very pass meant to repair it.

The bot no longer produces these (`_read_nothing` in `workflows/scraping/list_scraping.py`, and
`capture_non_blank` in `shared/vision/capture.py`). This script deals with the ones already stored.

WHAT IS CLEARED, AND WHAT IS NOT
--------------------------------
Cleared: everything the model invented — niche, sub-niche, score, gender, age group, profession,
classification, confidence, and the raw analysis payload.

KEPT: `has_ai`, and the location (`location_city`, `location_region`, `ai_account_based_in`).
That looks inconsistent, and it is deliberate. The city is the only handle these profiles have:
Target Search reads it through the `has_ai = 1` join, so clearing it would make them unreachable
by the geographic filter that is how an operator finds work to redo. The city may be wrong too —
the next real qualification overwrites it.

`updated_at` is bumped on every touched row on purpose: without it the correction never leaves
this machine, and the other synced installs (four PCs on this account, plus the web dashboard
reading the remote base) keep serving the invented niche forever.

Usage:
    python scripts/reset_hallucinated_qualifications.py            # dry run, prints the plan
    python scripts/reset_hallucinated_qualifications.py --apply    # writes
    python scripts/reset_hallucinated_qualifications.py --apply --backup out.json

Close the desktop app first: it holds the same SQLite file.
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A profile row that carries no fact at all — the shape a page that never loaded leaves behind.
# Unanimous on purpose: a real account can have no posts, or no followers, or no bio, but not all
# of that AND no display name at once.
EMPTY_PROFILE = """
    sp.followers_count = 0
    AND sp.following_count = 0
    AND sp.posts_count = 0
    AND (sp.biography IS NULL OR TRIM(sp.biography) = '')
    AND (sp.display_name IS NULL OR TRIM(sp.display_name) = '')
"""

# What the model produced and nothing else. `has_ai` and the location columns stay (see docstring).
INVENTED_COLUMNS = (
    'ai_niche',
    'ai_specific_niche',
    'ai_score',
    'ai_classification',
    'ai_profession',
    'ai_profession_tags',
    'ai_gender',
    'ai_age_group',
    'confidence',
    'analysis_json',
)


def default_db_path():
    """The same file the desktop app opens (TAKTIK_DB_PATH wins, as it does for the bot)."""
    env = os.environ.get('TAKTIK_DB_PATH')
    if env:
        return env
    return os.path.join(os.environ.get('APPDATA', ''), 'taktik-desktop', 'taktik-data.db')


def find_targets(conn):
    """Rows to clear: an AI qualification standing on an empty profile row."""
    return conn.execute(f"""
        SELECT pq.id, pq.username, pq.ai_niche, pq.ai_gender, pq.confidence,
               pq.location_city, substr(pq.enrichment_updated_at, 1, 10) AS qualified_on
        FROM profile_qualification pq
        JOIN social_profiles sp
          ON sp.platform = 'instagram' AND sp.legacy_profile_id = pq.profile_id
        WHERE pq.platform = 'instagram'
          AND pq.has_ai = 1
          AND pq.ai_niche IS NOT NULL
          AND {EMPTY_PROFILE}
        ORDER BY pq.enrichment_updated_at
    """).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    parser.add_argument('--db', default=None, help='path to taktik-data.db')
    parser.add_argument('--backup', default=None, help='write the rows being cleared to this JSON file first')
    args = parser.parse_args()

    db_path = args.db or default_db_path()
    if not os.path.exists(db_path):
        print(f'Base introuvable : {db_path}')
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        targets = find_targets(conn)
        if not targets:
            print('Rien à corriger : aucune qualification posée sur un profil vide.')
            return 0

        by_day = Counter(row['qualified_on'] or '(sans date)' for row in targets)
        by_niche = Counter(row['ai_niche'] for row in targets)

        print(f'{len(targets)} qualification(s) posée(s) sur un profil entièrement vide.\n')
        print('Par jour de qualification :')
        for day, count in sorted(by_day.items(), reverse=True)[:12]:
            print(f'  {day}  {count:>4}')
        print('\nNiches inventées les plus fréquentes :')
        for niche, count in by_niche.most_common(8):
            print(f'  {niche:<28} {count:>4}')
        print('\nExemples :')
        for row in targets[:8]:
            print(f"  @{row['username']:<32} {row['ai_niche']:<22} conf={row['confidence']} ville={row['location_city']}")

        if not args.apply:
            print('\nDry run — rien n\'a été écrit. Relancer avec --apply pour appliquer.')
            return 0

        if args.backup:
            with open(args.backup, 'w', encoding='utf-8') as handle:
                json.dump([dict(row) for row in targets], handle, ensure_ascii=False, indent=2)
            print(f'\nSauvegarde des lignes concernées : {args.backup}')

        assignments = ', '.join(f'{column} = NULL' for column in INVENTED_COLUMNS)
        ids = [row['id'] for row in targets]
        placeholders = ','.join('?' for _ in ids)
        # updated_at bumped in the SAME statement: a correction that does not move the watermark
        # never leaves this PC.
        conn.execute(
            f"UPDATE profile_qualification SET {assignments}, updated_at = datetime('now') "
            f"WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        print(f'\n{len(ids)} ligne(s) vidée(s). Elles repassent « sans qualification IA » dans '
              'Target Search, sur cette machine et — via la synchronisation — sur les autres.')
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
