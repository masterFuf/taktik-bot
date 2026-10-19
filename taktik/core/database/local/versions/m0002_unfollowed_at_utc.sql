-- TAKTIK local database: schema version 2, unfollowed_at moved from local time to UTC.
-- Data only: no table, column, index or view changes.
--
-- The other dates of the follow graph (first_seen_at, last_seen_at) are SQLite's datetime('now'),
-- in UTC. social_graph_sync.unfollowed_at was Python's datetime.now(), the local time of the
-- machine that wrote it, until its writer moved to datetime('now') too. The table is local to
-- each machine and never synced, so the machine that runs this step is the one that wrote its
-- rows; SQLite's 'utc' modifier takes that machine's offset at each row's own date (summer or
-- winter time).
--
-- Rows left as they are:
-- - before 2026-06-06: copied from the former following_sync table, whose unfollow date was
--   already datetime('now'); the local-time writer of social_graph_sync arrived that day;
-- - unfollowed_at equal to last_seen_at: both stamped by SQLite in the same statement, so already
--   in UTC (the corrected writer ran before this step);
-- - a value SQLite cannot read as a date: datetime() would turn it into NULL, which reopens the row.
UPDATE social_graph_sync
   SET unfollowed_at = datetime(unfollowed_at, 'utc')
 WHERE unfollowed_at >= '2026-06-06'
   AND unfollowed_at IS NOT last_seen_at
   AND datetime(unfollowed_at, 'utc') IS NOT NULL;
