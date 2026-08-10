"""Put `profile_qualification.ai_niche` back on the canonical slug.

Two defects, one column, one pass:

1. **The filter reaches 17% of the base.** Target Search sends a slug (`beauty_wellness`)
   and the query does `ai_niche = ?`, but 7 882 of the 9 502 qualified rows hold the
   human label ("Beauty & Wellness"). Filtering that bucket returns 166 profiles where
   1 564 exist. The slug is the canonical key — it is what the bot produces
   (`niche_category`) and what the UI sends; the label is a display concern.

2. **652 rows sit in "Other" while the model named a real category.** The canonicaliser
   learned to read those spellings (joiner-free lookup, real_estate -> business_marketing,
   …), but only for future qualifications. Their raw payload still carries the answer.

Both are repaired from data already stored — no AI call, no device.

`updated_at` is bumped on every touched row on purpose: without it the correction never
leaves this machine and never reaches the other synced installs.

Usage:
    python scripts/backfill_niche_categories.py            # dry run, prints the plan
    python scripts/backfill_niche_categories.py --apply    # writes

Close the desktop app first: it holds the same SQLite file.
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taktik.core.app.ai.providers.openrouter import AIService  # noqa: E402

try:
    from loguru import logger
    logger.remove()
except Exception:  # pragma: no cover - logging is a convenience here
    pass

CANONICAL = set(AIService.NICHE_CATEGORIES)


def resolve(ai_niche, raw_payload):
    """The slug this row should carry, or None to leave it alone.

    A label ("Beauty & Wellness") canonicalises straight to its slug. A row already in
    "other" gets a second chance from the model's own payload, which often names a
    category the old mapping could not read.
    """
    current = (ai_niche or '').strip()
    if not current:
        return None

    slug = AIService._canonicalize_niche_category(current)

    # "other" is where information goes to die; try the raw payload before accepting it.
    if slug == 'other' and raw_payload:
        try:
            named = (json.loads(raw_payload).get('niche_category') or '').strip()
        except Exception:
            named = ''
        if named and named.lower() not in ('other', 'unknown', 'spam'):
            recovered = AIService._canonicalize_niche_category(named)
            if recovered != 'other':
                return recovered

    return slug if slug != current else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    parser.add_argument('--db', default=os.path.join(os.environ.get('APPDATA', ''), 'taktik-desktop', 'taktik-data.db'))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print('database not found: %s' % args.db)
        return 1

    mode = '' if args.apply else '?mode=ro'
    con = sqlite3.connect('file:{}{}'.format(args.db.replace('\\', '/'), mode), uri=True)

    rows = con.execute("""
        SELECT platform, username, ai_niche, ai_classification
        FROM profile_qualification
        WHERE ai_niche IS NOT NULL AND ai_niche != ''
    """).fetchall()

    plan = []
    moves = Counter()
    for platform, username, ai_niche, raw in rows:
        target = resolve(ai_niche, raw)
        if target:
            plan.append((target, platform, username))
            moves['%s -> %s' % (ai_niche, target)] += 1

    print('rows with a niche : %d' % len(rows))
    print('rows to update    : %d' % len(plan))
    print()
    print('the 20 most common moves:')
    for move, count in moves.most_common(20):
        print('    %-46s %s' % (move, count))

    # Count only the rows that LEAVE "other". "Other -> other" is a casing fix, and
    # folding it into the rescue count would overstate the win by a third.
    rescued = sum(c for m, c in moves.items()
                  if m.lower().startswith('other ->') and not m.lower().endswith('-> other'))
    recased = sum(c for m, c in moves.items() if m == 'Other -> other')
    print()
    print('rescued from "Other" into a real bucket : %d' % rescued)
    print('"Other" merely re-cased to the slug     : %d' % recased)

    if not args.apply:
        print('\nDRY RUN — nothing written. Re-run with --apply.')
        return 0

    con.executemany(
        """
        UPDATE profile_qualification
        SET ai_niche = ?, updated_at = datetime('now')
        WHERE platform = ? AND username = ?
        """,
        plan,
    )
    con.commit()
    print('\nwritten: %d rows' % len(plan))
    con.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
