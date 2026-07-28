"""Lift the workflow of each past session out of its config blob and into its own column.

A session records WHAT it targeted — `Auto_USER_villedeluxembourg`, target_type USER — but never
WHICH workflow produced it. Measured on the real base: `workflow_type` is filled on 254 of 1 027
rows, all of them TikTok. Every Instagram session has it NULL.

So the Sessions page, Analytics, and anything asking "what did I run" have been reading a name and
a target type and inferring the rest. `Auto_USER_` covers Target, Feed, Unfollow and the following
sync alike; `POST_URL` covers both Post Likers and Smart Comment.

The information was never missing, only misplaced. Every Instagram workflow writes its own name
into `config_used.session_settings.workflow_type` at launch, and that value is still there on all
773 rows:

    target_followers  668     unfollow          21
    hashtag            42     feed              17
    sync_following     24     notifications      1

Two things worth knowing before trusting the result. `feed` ran 17 times, so the 719 `Auto_USER_`
sessions were never as ambiguous as their names suggest — 656 are `target_followers`. And the 12
`POST_URL` sessions are labelled `target_followers` too, because the bot drives post likers
through the followers workflow; a reader mapping these onto the front's pages has to know that.

It also settles a second defect on the same column: TikTok held `FOLLOWERS` (58) beside
`followers` (68), two spellings of one workflow, so every grouping counted it twice. Two writers,
one column, no normalizer between them — the bot shouted, Electron did not. Lowercase wins because
it is what the rest of the TikTok vocabulary already uses (`for_you`, `search`, `hashtag`), and the
bot writer is corrected in the same change.

Both write paths are fixed separately (`SessionRepository.create` now derives the column from the
same config; the TikTok followers repository now writes lowercase), so this runs once, over the
history.

Usage:
    python scripts/backfill_session_workflow_type.py            # dry run
    python scripts/backfill_session_workflow_type.py --apply

Stop the bot first: this writes to the table a running session is appending to.
"""

import argparse
import json
import os
import sqlite3
from collections import Counter


def workflow_from_config(raw):
    """The workflow name a session was launched with, or None if the blob does not carry one."""
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    settings = payload.get('session_settings')
    if not isinstance(settings, dict):
        return None
    value = settings.get('workflow_type')
    return str(value)[:50] if value else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    parser.add_argument('--db', default=os.path.join(os.environ.get('APPDATA', ''),
                                                     'taktik-desktop', 'taktik-data.db'))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print('database not found: %s' % args.db)
        return 1

    uri = 'file:{}{}'.format(args.db.replace('\\', '/'), '' if args.apply else '?mode=ro')
    con = sqlite3.connect(uri, uri=True)

    rows = con.execute("""
        SELECT id, config_used FROM sessions_unified
        WHERE (workflow_type IS NULL OR workflow_type = '')
    """).fetchall()

    plan = []
    unrecoverable = 0
    for session_id, config in rows:
        workflow = workflow_from_config(config)
        if workflow:
            plan.append((workflow, session_id))
        else:
            unrecoverable += 1

    # Spellings that are the same workflow written two ways. Keyed lowercase, valued canonical,
    # so adding a pair later needs no code — only a line.
    NORMALIZE = {'FOLLOWERS': 'followers'}
    miscased = con.execute(
        "SELECT workflow_type, COUNT(*) FROM sessions_unified WHERE workflow_type IN (%s) GROUP BY workflow_type"
        % ','.join('?' * len(NORMALIZE)), tuple(NORMALIZE)).fetchall()

    counts = Counter(workflow for workflow, _ in plan)
    print('sessions with an empty workflow_type : %d' % len(rows))
    print('recoverable from the config          : %d' % len(plan))
    print('carrying nothing to recover          : %d' % unrecoverable)
    print()
    for workflow, n in counts.most_common():
        print('    %-24s %d' % (workflow, n))

    if miscased:
        print()
        print('graphies a normaliser :')
        for value, n in miscased:
            print('    %-24s %4d  ->  %s' % (value, n, NORMALIZE[value]))

    if not args.apply:
        print('\nDRY RUN — nothing written. Re-run with --apply.')
        return 0

    # `updated_at` is bumped: without it the correction never leaves this machine, and the base is
    # shared across four.
    for workflow, session_id in plan:
        con.execute(
            "UPDATE sessions_unified SET workflow_type = ?, updated_at = datetime('now') WHERE id = ?",
            (workflow, session_id))
    for wrong, right in NORMALIZE.items():
        con.execute(
            "UPDATE sessions_unified SET workflow_type = ?, updated_at = datetime('now') WHERE workflow_type = ?",
            (right, wrong))
    con.commit()

    (filled,) = con.execute(
        "SELECT COUNT(*) FROM sessions_unified WHERE workflow_type IS NOT NULL AND workflow_type != ''"
    ).fetchone()
    (total,) = con.execute('SELECT COUNT(*) FROM sessions_unified').fetchone()
    print('\nwritten: %d rows' % len(plan))
    print('workflow_type now filled on %d of %d sessions' % (filled, total))
    con.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
