"""Mark unreachable every profile stored under a pseudo that no platform would register as a handle.

A handle is letters, digits, "." and "_" within the platform's bounds (Instagram 1-30, TikTok
2-24). The rows repaired here were stored before the profile writers refused anything else
(`require_handle`): a button label read as a pseudo ("Send message"), a handle followed by spaces
or holding control characters, a biography squeezed into one word, a TikTok display name. The
repair lives in `InvalidHandleRepository` (taktik/core/database/repositories/social_profiles/).

Each row is MARKED unreachable (`MARK_UNREACHABLE_SQL`), never deleted: the sync carries updates,
not deletions, so the mark reaches the other installs where a delete would not. What points at a
row (qualification, scraping link, cached image) is counted and left as it is.

Usage:
    python scripts/repair_invalid_profile_handles.py              # dry run: rows and references
    python scripts/repair_invalid_profile_handles.py --apply      # backup, then one transaction
    python scripts/repair_invalid_profile_handles.py --db path/to/taktik-data.db

The dry run opens the base read only. --apply first copies the base next to itself through
SQLite's backup API (`<name>.backup-<timestamp>-pre-invalid-handles.db`), after checking the disk
has room for it and that the copy passes quick_check, and writes nothing if the copy fails. The
backup is the one of `repair_collab_post_authors.py`.

Close the desktop app before --apply: it holds the same SQLite file.
"""

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from repair_collab_post_authors import (  # noqa: E402
    backup_database,
    default_db_path,
    open_read_only,
)
from taktik.core.database.repositories.social_profiles import InvalidHandleRepository  # noqa: E402

BACKUP_LABEL = "pre-invalid-handles"


def print_plan(plan, examples, applied=False):
    to_mark = plan.to_mark
    verb = "marque(s)" if applied else "a marquer"
    print(f"social_profiles.username : {len(plan.profiles)} pseudo(s) qui ne sont pas des pseudos, "
          f"{len(to_mark)} {verb} injoignable(s)")
    for profile in plan.profiles[:examples]:
        state = "deja marque" if profile.already_marked else ("marque" if applied else "a marquer")
        print(f"  {profile.platform:<9} profil {profile.profile_id} {profile.stored!r}")
        print(f"      cree le {profile.created_at} ; {state}")
        if profile.references:
            refs = ", ".join(f"{name} {count}" for name, count in profile.references)
            print(f"      lignes qui y renvoient (laissees telles quelles) : {refs}")
        else:
            print("      aucune ligne n'y renvoie")
    if len(plan.profiles) > examples:
        print(f"  ... et {len(plan.profiles) - examples} autre(s) (--examples pour tout afficher)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='write the repair (default: dry run)')
    parser.add_argument('--db', default=None, help='path to taktik-data.db')
    parser.add_argument('--examples', type=int, default=50, help='rows shown (default: 50)')
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass

    db_path = args.db or default_db_path()
    if not os.path.exists(db_path):
        print(f'Base introuvable : {db_path}')
        return 1

    conn = open_read_only(db_path)
    try:
        plan = InvalidHandleRepository(conn).plan()
    finally:
        conn.close()

    if not args.apply:
        print(f'Base : {db_path} (lecture seule)\n')
        print_plan(plan, args.examples)
        if plan.has_work:
            print("\nDry run - rien n'a ete ecrit. Relancer avec --apply pour appliquer (sauvegarde d'abord).")
        else:
            print('\nRien a marquer.')
        return 0

    if not plan.has_work:
        print('Rien a marquer : aucune sauvegarde faite, rien ecrit.')
        return 0

    try:
        backup = backup_database(db_path, label=BACKUP_LABEL)
    except Exception as exc:
        print(f'Sauvegarde impossible, rien ecrit : {exc}')
        return 1
    print(f'Sauvegarde : {backup}\n')

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        done = InvalidHandleRepository(conn).apply()
    except Exception as exc:
        print(f'Echec, transaction annulee, rien ecrit : {exc}')
        return 1
    finally:
        conn.close()
    print('Applique en une transaction :\n')
    print_plan(done, args.examples, applied=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
