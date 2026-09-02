"""Delete the profiles that no longer exist — once, and only once, they have proved it.

The bot marks a profile it could not OPEN (`unreachable_at`, `unreachable_count`) rather than
deleting it on the spot, because a search finding nobody is not proof of death: a rename keeps the
account alive under another handle, a run has already failed on a search field that was never
cleared, and Instagram is sometimes just slow. One failure is noise.

This script is the other end of that decision. It removes only the profiles that answered nobody
`--min-failures` runs in a row AND carry no history worth keeping — no interaction, no
qualification. A profile we have followed or liked is never deleted whatever its state: the
interaction rows would point at nothing, and the campaign figures would quietly start counting
wrong.

TWO THINGS TO KNOW BEFORE RUNNING IT
------------------------------------
1. It is IRREVERSIBLE. Use --backup; it writes every deleted row (and its dependants) to JSON
   first.
2. It is LOCAL. The Turso sync carries inserts and updates, not deletions, so the other installs
   keep their copy and may hand it back on a later pull. Run it where it matters, or accept that
   the base is only tidy on this machine. This is precisely why the MARK — which is an update, and
   does travel — is what the app filters on.

Usage:
    python scripts/purge_unreachable_profiles.py                      # dry run
    python scripts/purge_unreachable_profiles.py --min-failures 3     # dry run, explicit threshold
    python scripts/purge_unreachable_profiles.py --apply --backup out.json

Close the desktop app first: it holds the same SQLite file.
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tables that carry rows FOR a profile and are safe to remove with it. Interactions and
# qualification are deliberately absent: a profile holding either is never a purge candidate, so
# nothing of theirs is ever deleted here.
DEPENDENT_TABLES = (
    ('media', 'profile_id'),
    ('profile_stats_history', 'profile_id'),
    ('profile_following', 'profile_id'),
    ('scraped_profiles', 'profile_id'),
    ('filtered_profiles', 'profile_id'),
)


def default_db_path():
    env = os.environ.get('TAKTIK_DB_PATH')
    if env:
        return env
    return os.path.join(os.environ.get('APPDATA', ''), 'taktik-desktop', 'taktik-data.db')


def find_candidates(conn, min_failures, platform):
    """Unreachable enough times, and carrying nothing worth keeping."""
    return conn.execute(
        """
        SELECT sp.id, sp.legacy_profile_id, sp.username, sp.unreachable_count,
               substr(sp.unreachable_at, 1, 10) AS last_failure
        FROM social_profiles sp
        WHERE sp.platform = ?
          AND sp.unreachable_at IS NOT NULL
          AND COALESCE(sp.unreachable_count, 0) >= ?
          AND NOT EXISTS (SELECT 1 FROM interactions i
                           WHERE i.platform = sp.platform AND i.profile_id = sp.legacy_profile_id)
          AND NOT EXISTS (SELECT 1 FROM profile_qualification q
                           WHERE q.platform = sp.platform AND q.profile_id = sp.legacy_profile_id)
        ORDER BY sp.unreachable_count DESC, sp.username
        """,
        (platform, min_failures),
    ).fetchall()


def count_protected(conn, min_failures, platform):
    """Unreachable enough times but SPARED because they carry history."""
    return conn.execute(
        """
        SELECT COUNT(*) FROM social_profiles sp
        WHERE sp.platform = ?
          AND sp.unreachable_at IS NOT NULL
          AND COALESCE(sp.unreachable_count, 0) >= ?
          AND (EXISTS (SELECT 1 FROM interactions i
                        WHERE i.platform = sp.platform AND i.profile_id = sp.legacy_profile_id)
            OR EXISTS (SELECT 1 FROM profile_qualification q
                        WHERE q.platform = sp.platform AND q.profile_id = sp.legacy_profile_id))
        """,
        (platform, min_failures),
    ).fetchone()[0]


def collect_dependants(conn, legacy_ids):
    """Everything that would go with them, table by table — for the backup and the report."""
    out = {}
    if not legacy_ids:
        return out
    placeholders = ','.join('?' for _ in legacy_ids)
    for table, column in DEPENDENT_TABLES:
        try:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {column} IN ({placeholders})", legacy_ids
            ).fetchall()
            if rows:
                out[table] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            continue  # table absent on an older base
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    parser.add_argument('--min-failures', type=int, default=3,
                        help='consecutive failed runs before a profile is purgeable (default: 3)')
    parser.add_argument('--platform', default='instagram')
    parser.add_argument('--db', default=None)
    parser.add_argument('--backup', default=None, help='write every deleted row to this JSON file first')
    args = parser.parse_args()

    if args.min_failures < 1:
        print('--min-failures doit valoir au moins 1 : supprimer sans preuve est exactement ce que ce script evite.')
        return 1

    db_path = args.db or default_db_path()
    if not os.path.exists(db_path):
        print(f'Base introuvable : {db_path}')
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        candidates = find_candidates(conn, args.min_failures, args.platform)
        protected = count_protected(conn, args.min_failures, args.platform)

        print(f'Seuil : au moins {args.min_failures} echec(s) consecutif(s).\n')
        if protected:
            print(f'{protected} profil(s) injoignable(s) sont EPARGNES : ils portent des interactions '
                  'ou une qualification.')
        if not candidates:
            print('Aucun profil a purger.')
            return 0

        legacy_ids = [row['legacy_profile_id'] for row in candidates if row['legacy_profile_id'] is not None]
        dependants = collect_dependants(conn, legacy_ids)

        by_count = Counter(row['unreachable_count'] for row in candidates)
        print(f'\n{len(candidates)} profil(s) a purger :')
        for failures, n in sorted(by_count.items(), reverse=True):
            print(f'  {failures} echec(s) : {n}')
        print('\nLignes liees qui partiraient avec :')
        for table, rows in dependants.items():
            print(f'  {table:<26} {len(rows)}')
        print('\nExemples :')
        for row in candidates[:10]:
            print(f"  @{row['username']:<32} {row['unreachable_count']} echec(s), dernier {row['last_failure']}")

        if not args.apply:
            print("\nDry run — rien n'a ete supprime. Relancer avec --apply pour appliquer.")
            return 0

        if args.backup:
            with open(args.backup, 'w', encoding='utf-8') as handle:
                json.dump({'profiles': [dict(r) for r in candidates], 'dependants': dependants},
                          handle, ensure_ascii=False, indent=2, default=str)
            print(f'\nSauvegarde : {args.backup}')

        # One transaction: a purge that stops halfway would leave the dependants of a profile that
        # is already gone.
        ids = [row['id'] for row in candidates]
        with conn:
            if legacy_ids:
                placeholders = ','.join('?' for _ in legacy_ids)
                for table, column in DEPENDENT_TABLES:
                    try:
                        conn.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", legacy_ids)
                    except sqlite3.OperationalError:
                        continue
            conn.execute(f"DELETE FROM social_profiles WHERE id IN ({','.join('?' for _ in ids)})", ids)

        print(f'\n{len(ids)} profil(s) supprime(s), avec leurs lignes liees.')
        print('Rappel : la suppression est LOCALE — la synchronisation ne porte pas les effacements.')
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
