"""File under its first author every pseudo that is the author line of a collaboration post.

A post in collaboration names several accounts on its author line ("a et b", "a and b",
"a et 2 autres personnes"). The extraction now keeps the first handle
(`username_from_author_header`); this script repairs what was stored before, through
`CollabAuthorRepository` (taktik/core/database/repositories/instagram/post_author/):

- `processed_hashtag_posts.post_author` takes the first handle, so the 7-day guard matches the
  post again;
- a phantom Instagram profile named after the line is MARKED unreachable (never deleted), and the
  interactions this device wrote under it move to the first handle's profile when it exists.

Other pseudo columns are counted and left alone, notification actors included: an aggregated
notification names several people on purpose.

Local only for `processed_hashtag_posts` and the moved interactions (the first is not synced, the
second is append-only in the sync); the mark on a phantom travels, as any update of
`social_profiles` does.

Usage:
    python scripts/repair_collab_post_authors.py              # dry run: counts and examples
    python scripts/repair_collab_post_authors.py --apply      # backup, then one transaction
    python scripts/repair_collab_post_authors.py --db path/to/taktik-data.db

The dry run opens the base read only. --apply first copies the base next to itself through
SQLite's backup API (`<name>.backup-<timestamp>-pre-collab-authors.db`), after checking the disk
has room for it, and writes nothing if the copy fails.

Close the desktop app before --apply: it holds the same SQLite file.
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taktik.core.database.repositories.instagram.post_author import (  # noqa: E402
    COUNTED_ONLY,
    CollabAuthorRepository,
)

# Why each counted column is left alone, as the report says it.
LEFT_ALONE = {
    "interactions.target_username": "reprises seulement avec leur profil fantome, et si ce PC les a ecrites",
    "posted_comments.post_author": "compte seulement",
    "posted_comments.target_username": "compte seulement",
    "post_analysis.post_author": "compte seulement",
    "notifications.actor_username": "notification groupee : plusieurs acteurs voulus, pas un auteur de post",
}

BACKUP_LABEL = "pre-collab-authors"


def default_db_path():
    """The same file the desktop app opens (TAKTIK_DB_PATH wins, as it does for the bot)."""
    env = os.environ.get('TAKTIK_DB_PATH')
    if env:
        return env
    return os.path.join(os.environ.get('APPDATA', ''), 'taktik-desktop', 'taktik-data.db')


def open_read_only(db_path):
    return sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)


def backup_path_for(db_path, now=None):
    path = Path(db_path)
    stamp = (now or datetime.now()).strftime('%Y%m%d-%H%M%S')
    return path.with_name(f"{path.stem}.backup-{stamp}-{BACKUP_LABEL}{path.suffix}")


def backup_database(db_path):
    """Copy the base next to itself; returns the copy's path. Raises if the copy cannot be trusted."""
    source = Path(db_path)
    wal = source.with_name(source.name + '-wal')
    size = source.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
    needed = size + size // 10
    free = shutil.disk_usage(source.parent).free
    if free < needed:
        raise RuntimeError(
            f"Place insuffisante pour la sauvegarde : {free / 1e9:.2f} Go libres, "
            f"{needed / 1e9:.2f} Go necessaires."
        )

    target = backup_path_for(db_path)
    if target.exists():
        raise RuntimeError(f"La sauvegarde existe deja : {target}")
    src = open_read_only(db_path)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    except Exception:
        src.close()
        target.unlink(missing_ok=True)
        raise
    src.close()

    check = open_read_only(target)
    try:
        if check.execute("PRAGMA quick_check(1)").fetchone()[0] != 'ok':
            raise RuntimeError(f"La sauvegarde ne passe pas quick_check : {target}")
    finally:
        check.close()
    return target


def print_plan(plan, examples):
    print(f"processed_hashtag_posts.post_author : {len(plan.hashtag_posts)} ligne(s) a reprendre")
    for fix in plan.hashtag_posts[:examples]:
        if fix.drop:
            what = "supprimee (une ligne plus recente range deja ce post sous ce pseudo)"
        elif fix.replaces_id is not None:
            what = f"renommee, remplace la ligne {fix.replaces_id} plus ancienne"
        else:
            what = "renommee"
        print(f"  #{fix.hashtag:<22} compte {fix.account_id:<6} {fix.stored!r}")
        print(f"      -> @{fix.author} ({what}, traitee le {fix.processed_at})")

    print(f"\nsocial_profiles.username (instagram) : {len(plan.phantom_profiles)} profil(s) fantome(s)")
    for fix in plan.phantom_profiles[:examples]:
        if fix.moves_interactions:
            what = f"{fix.own_interactions} interaction(s) -> profil {fix.author_profile_id} (@{fix.author})"
        elif fix.author_profile_id is None:
            what = f"@{fix.author} absent de la base : interactions laissees ({fix.own_interactions})"
        else:
            what = "aucune interaction de ce PC a deplacer"
        mark = "deja marque" if fix.already_marked else "marque injoignable"
        print(f"  profil {fix.profile_id} {fix.stored!r} : {mark} ; {what}")

    print("\nColonnes seulement comptees (rien n'y est ecrit) :")
    for table, column in COUNTED_ONLY:
        key = f"{table}.{column}"
        if key not in plan.counted:
            print(f"  {key:<34} (absente de cette base)")
            continue
        print(f"  {key:<34} {plan.counted[key]:>5}   {LEFT_ALONE.get(key, '')}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='write the repair (default: dry run)')
    parser.add_argument('--db', default=None, help='path to taktik-data.db')
    parser.add_argument('--examples', type=int, default=10, help='rows shown per section (default: 10)')
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass

    db_path = args.db or default_db_path()
    if not os.path.exists(db_path):
        print(f'Base introuvable : {db_path}')
        return 1

    if not args.apply:
        conn = open_read_only(db_path)
        try:
            plan = CollabAuthorRepository(conn).plan()
        finally:
            conn.close()
        print(f'Base : {db_path} (lecture seule)\n')
        print_plan(plan, args.examples)
        if plan.has_work:
            print("\nDry run - rien n'a ete ecrit. Relancer avec --apply pour appliquer (sauvegarde d'abord).")
        else:
            print('\nRien a reprendre.')
        return 0

    conn = open_read_only(db_path)
    try:
        has_work = CollabAuthorRepository(conn).plan().has_work
    finally:
        conn.close()
    if not has_work:
        print('Rien a reprendre : aucune sauvegarde faite, rien ecrit.')
        return 0

    try:
        backup = backup_database(db_path)
    except Exception as exc:
        print(f'Sauvegarde impossible, rien ecrit : {exc}')
        return 1
    print(f'Sauvegarde : {backup}\n')

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        done = CollabAuthorRepository(conn).apply()
    except Exception as exc:
        print(f'Echec, transaction annulee, rien ecrit : {exc}')
        return 1
    finally:
        conn.close()
    print('Applique en une transaction :\n')
    print_plan(done, args.examples)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
