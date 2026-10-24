"""Repair two records the Instagram scraping runs wrote wrong, now that the runs write them right.

1. `scraping_sessions.scraping_type`: a hashtag or post_url session was stored as 'followers', the
   writer's default, although it read the likers or commenters of posts. Its type is read back from
   the config the session saved, by the rule the run itself types its session with
   (`saved_post_session_type`, workflows/scraping/persistence.py): 'likers', 'commenters',
   'likers+commenters' or 'none'. A session whose config does not say which lists it read (no
   config, unreadable, another run's, a setting absent) is listed and left as it is.
2. `profile_stats_history`: a run saved each profile twice, and each save wrote a snapshot. The
   second snapshot is removed when it is the exact double of the first, inside the same completed
   run, and only then (rule in full: `StatsSnapshotDoubleRepository`,
   taktik/core/database/repositories/instagram/profile/).

Usage (desktop app closed):
    python scripts/repairs/repair_scraping_runs.py              # dry run: counts and 5 examples each
    python scripts/repairs/repair_scraping_runs.py --apply      # backup, one transaction, journal
    python scripts/repairs/repair_scraping_runs.py --db path/to/taktik-data.db

The dry run opens the base read only. --apply first copies the base next to itself through
SQLite's backup API (`<name>.backup-<timestamp>-pre-scraping-runs.db`, the backup of
`repair_collab_post_authors.py`), writes nothing if the copy fails, then writes both repairs in one
transaction and lists every changed row in a journal next to the backup (same name,
`.journal.txt`).

The session types travel with the sync (`updated_at` moves). The removed snapshots do not: the sync
carries no deletion, so a double already pushed stays in the remote base.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from repair_collab_post_authors import (  # noqa: E402
    backup_database,
    default_db_path,
    open_read_only,
)
from taktik.core.database.instagram_scraping_repair import ScrapingRunRepair  # noqa: E402
from taktik.core.social_media.instagram.workflows.scraping.persistence import (  # noqa: E402
    POST_SOURCE_TYPES,
    saved_post_session_type,
)

BACKUP_LABEL = "pre-scraping-runs"
EXAMPLES = 5


def repair_for(conn):
    """The repair, wired to the rule the run types its post sessions with."""
    return ScrapingRunRepair(conn, tuple(POST_SOURCE_TYPES.values()), saved_post_session_type)


def _first(items, examples):
    return items if examples is None else items[:examples]


def _more(items, examples):
    if examples is not None and len(items) > examples:
        return [f"  ... et {len(items) - examples} autre(s)"]
    return []


def _who(pair):
    return f"@{pair.username}" if pair.username else f"profil {pair.profile_id}"


def render(plan, examples, applied=False):
    """The plan as lines: every row when `examples` is None (the journal), else the first few."""
    sessions, stats = plan.session_types, plan.stats_doubles
    lines = []

    verb = "retypee(s)" if applied else "a retyper"
    lines.append(f"scraping_sessions.scraping_type : {len(sessions.fixes)} session(s) {verb}, "
                 f"{len(sessions.undecided)} non tranchee(s) (laissees telles quelles)")
    for session in _first(sessions.fixes, examples):
        lines.append(f"  session {session.scraping_id} {session.source_type} {session.source_name!r} "
                     f"({session.start_time}) : {session.stored} -> {session.new_type}")
    lines += _more(sessions.fixes, examples)
    if sessions.undecided:
        lines.append("  Non tranchees :")
        for session in _first(sessions.undecided, examples):
            lines.append(f"    session {session.scraping_id} {session.source_type} {session.source_name!r} "
                         f"({session.start_time}) : {session.reason}")
        lines += ["  " + line for line in _more(sessions.undecided, examples)]

    verb = "retire(s)" if applied else "a retirer"
    lines.append("")
    lines.append(f"profile_stats_history : {len(stats.doubles)} releve(s) en double {verb}")
    for pair in _first(stats.doubles, examples):
        lines.append(f"  releve {pair.second_id} ({pair.second_at}) de {_who(pair)}, run {pair.scraping_id} : "
                     f"double exact du releve {pair.first_id} ({pair.first_at}), "
                     f"abonnes/abonnements/posts {pair.counters()}")
        if examples is None:
            lines.append(f"    ligne retiree : {json.dumps(dict(pair.second_row), ensure_ascii=False)}")
    lines += _more(stats.doubles, examples)

    left = [
        (stats.different, "deux releves differents dans le run (deux lectures)"),
        (stats.shared, "paire couverte aussi par un autre run du profil"),
    ]
    for pairs, why in left:
        if not pairs:
            continue
        lines.append(f"  Laisses : {len(pairs)} {why}")
        for pair in _first(pairs, examples):
            others = f", autres runs {list(pair.other_runs)}" if pair.other_runs else ""
            lines.append(f"    releves {pair.first_id} et {pair.second_id} de {_who(pair)}, run {pair.scraping_id} : "
                         f"{pair.counters('first')} puis {pair.counters('second')}{others}")
        lines += ["  " + line for line in _more(pairs, examples)]
    if stats.crowded:
        lines.append(f"  Laisses : {len(stats.crowded)} run(s) avec plus de deux releves du meme profil")
        for crowded in _first(stats.crowded, examples):
            who = f"@{crowded.username}" if crowded.username else f"profil {crowded.profile_id}"
            lines.append(f"    run {crowded.scraping_id}, {who} : releves {list(crowded.snapshot_ids)}")
        lines += ["  " + line for line in _more(stats.crowded, examples)]
    return lines


def write_journal(path, db_path, backup, plan):
    header = [
        f"Reparation des runs de scraping, {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Base : {db_path}",
        f"Sauvegarde : {backup}",
        "",
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as journal:
        journal.write("\n".join(header + render(plan, None, applied=True)) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the repair (default: dry run)")
    parser.add_argument("--db", default=None, help="path to taktik-data.db")
    parser.add_argument("--examples", type=int, default=EXAMPLES,
                        help=f"rows shown per section (default: {EXAMPLES})")
    args = parser.parse_args(argv)

    # A pseudo the Windows console cannot print comes out as '?' instead of stopping the script.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")

    db_path = args.db or default_db_path()
    if not os.path.exists(db_path):
        print(f"Base introuvable : {db_path}")
        return 1

    conn = open_read_only(db_path)
    try:
        plan = repair_for(conn).plan()
    finally:
        conn.close()

    if not args.apply:
        print(f"Base : {db_path} (lecture seule)\n")
        print("\n".join(render(plan, args.examples)))
        if plan.has_work:
            print("\nDry run - rien n'a ete ecrit. Relancer avec --apply pour appliquer (sauvegarde d'abord).")
        else:
            print("\nRien a reparer.")
        return 0

    if not plan.has_work:
        print("Rien a reparer : aucune sauvegarde faite, rien ecrit.")
        return 0

    try:
        backup = backup_database(db_path, label=BACKUP_LABEL)
    except Exception as exc:
        print(f"Sauvegarde impossible, rien ecrit : {exc}")
        return 1
    print(f"Sauvegarde : {backup}\n")

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        done = repair_for(conn).apply()
    except Exception as exc:
        print(f"Echec, transaction annulee, rien ecrit : {exc}")
        return 1
    finally:
        conn.close()

    print("Applique en une transaction :\n")
    print("\n".join(render(done, args.examples, applied=True)))

    journal = backup.with_suffix(".journal.txt")
    try:
        write_journal(journal, db_path, backup, done)
    except OSError as exc:
        print(f"\nJournal impossible a ecrire ({journal}) : {exc}. Le voici en entier :\n")
        print("\n".join(render(done, None, applied=True)))
        return 1
    print(f"\nJournal : {journal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
