"""Unit tests for schema.py and migrations.py."""
import sqlite3
import pytest

from taktik.core.database.local.schema import create_schema
from taktik.core.database.local.migrations import run_migrations, _validate_sql_identifier


# ─── _validate_sql_identifier ─────────────────────────────────────────────────

class TestValidateSqlIdentifier:
    def test_valid_simple(self):
        assert _validate_sql_identifier("username") == "username"

    def test_valid_with_numbers(self):
        assert _validate_sql_identifier("col1") == "col1"

    def test_valid_with_underscore(self):
        assert _validate_sql_identifier("followers_count") == "followers_count"

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_sql_identifier("Username")

    def test_rejects_dash(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_sql_identifier("col-name")

    def test_rejects_space(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_sql_identifier("col name")

    def test_rejects_sql_injection(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_sql_identifier("id; DROP TABLE--")

    def test_rejects_leading_digit(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_sql_identifier("1col")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_sql_identifier("")


# ─── create_schema ─────────────────────────────────────────────────────────────

EXPECTED_TABLES = {
    # Instagram
    "instagram_accounts",
    "instagram_profiles",
    "interaction_history",
    "filtered_profiles",
    "sessions",
    "profile_stats_history",
    "instagram_posts",
    "scraping_sessions",
    "processed_hashtag_posts",
    "daily_stats",
    "following_sync",
    "followers_sync",
    "scraped_profiles",
    "scraped_comments",
    # TikTok
    "tiktok_accounts",
    "tiktok_profiles",
    "tiktok_interaction_history",
    "tiktok_sessions",
    "tiktok_filtered_profiles",
    "tiktok_daily_stats",
    # Gmail
    "gmail_accounts",
}


class TestCreateSchema:
    @pytest.fixture
    def fresh_conn(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        yield con
        con.close()

    def _get_tables(self, con):
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {r["name"] for r in rows}

    def test_all_tables_created(self, fresh_conn):
        create_schema(fresh_conn)
        tables = self._get_tables(fresh_conn)
        missing = EXPECTED_TABLES - tables
        assert not missing, f"Missing tables after create_schema: {missing}"

    def test_idempotent(self, fresh_conn):
        """Calling create_schema twice must not raise."""
        create_schema(fresh_conn)
        create_schema(fresh_conn)  # second call — should be no-op
        tables = self._get_tables(fresh_conn)
        assert EXPECTED_TABLES <= tables

    def test_instagram_accounts_columns(self, fresh_conn):
        create_schema(fresh_conn)
        info = fresh_conn.execute("PRAGMA table_info(instagram_accounts)").fetchall()
        cols = {r["name"] for r in info}
        assert {"account_id", "username", "is_bot", "created_at"} <= cols

    def test_sessions_foreign_key(self, fresh_conn):
        create_schema(fresh_conn)
        # Inserting a session with a non-existent account_id must fail when FKs are on
        fresh_conn.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            fresh_conn.execute(
                "INSERT INTO sessions (account_id, session_name, target_type, target) VALUES (999, 'x', 'y', 'z')"
            )
            fresh_conn.commit()

    def test_indexes_created(self, fresh_conn):
        create_schema(fresh_conn)
        rows = fresh_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = {r["name"] for r in rows}
        assert "idx_accounts_username" in index_names
        assert "idx_profiles_username" in index_names
        assert "idx_tiktok_accounts_username" in index_names


# ─── run_migrations ────────────────────────────────────────────────────────────

class TestRunMigrations:
    @pytest.fixture
    def base_conn(self):
        """Connection with schema but NO migrations yet."""
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        create_schema(con)
        yield con
        con.close()

    def test_migrations_idempotent(self, base_conn):
        """run_migrations can be called multiple times without error."""
        run_migrations(base_conn)
        run_migrations(base_conn)

    def test_scraped_comments_columns_added(self, base_conn):
        """Migrations must add scraping_session_id, profile_id, target_username, is_reply."""
        run_migrations(base_conn)
        info = base_conn.execute("PRAGMA table_info(scraped_comments)").fetchall()
        cols = {r["name"] for r in info}
        assert "scraping_session_id" in cols
        assert "profile_id" in cols
        assert "target_username" in cols
        assert "is_reply" in cols

    def test_instagram_profiles_extra_columns(self, base_conn):
        """Migrations must ensure account_based_in and date_joined exist."""
        run_migrations(base_conn)
        info = base_conn.execute("PRAGMA table_info(instagram_profiles)").fetchall()
        cols = {r["name"] for r in info}
        assert "account_based_in" in cols
        assert "date_joined" in cols

    def test_scraping_sessions_platform_column(self, base_conn):
        run_migrations(base_conn)
        info = base_conn.execute("PRAGMA table_info(scraping_sessions)").fetchall()
        cols = {r["name"] for r in info}
        assert "platform" in cols

    def test_scraped_profiles_ai_columns(self, base_conn):
        run_migrations(base_conn)
        info = base_conn.execute("PRAGMA table_info(scraped_profiles)").fetchall()
        cols = {r["name"] for r in info}
        for col in ("ai_score", "ai_qualified", "ai_analysis", "qualification_criteria", "scored_at"):
            assert col in cols, f"Missing column: {col}"

    def test_legacy_tiktok_scraped_profiles_are_migrated(self, base_conn):
        base_conn.execute("DROP TABLE IF EXISTS tiktok_scraped_profiles")
        base_conn.execute("""
            CREATE TABLE tiktok_scraped_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraping_id INTEGER,
                username TEXT,
                display_name TEXT,
                followers_count INTEGER,
                following_count INTEGER,
                likes_count INTEGER,
                posts_count INTEGER,
                bio TEXT,
                is_private INTEGER,
                is_verified INTEGER,
                is_enriched INTEGER,
                scraped_at TEXT
            )
        """)
        base_conn.execute("""
            INSERT INTO tiktok_scraped_profiles (
                scraping_id, username, display_name, followers_count,
                following_count, likes_count, posts_count, bio,
                is_private, is_verified, is_enriched, scraped_at
            )
            VALUES (42, 'creator_legacy', 'Legacy Creator', 1000, 50, 12345, 12,
                    'Old bio', 0, 1, 1, '2026-01-01T00:00:00')
        """)

        run_migrations(base_conn)

        profile = base_conn.execute(
            "SELECT username, biography, followers_count FROM tiktok_profiles WHERE username = ?",
            ("creator_legacy",),
        ).fetchone()
        assert profile is not None
        assert profile["biography"] == "Old bio"
        assert profile["followers_count"] == 1000

        info = base_conn.execute("PRAGMA table_info(tiktok_scraped_profiles)").fetchall()
        cols = {r["name"] for r in info}
        assert "profile_id" in cols
        assert "bio" not in cols

        link = base_conn.execute("""
            SELECT tsp.scraping_id, tp.username
            FROM tiktok_scraped_profiles tsp
            JOIN tiktok_profiles tp ON tp.profile_id = tsp.profile_id
        """).fetchone()
        assert link["scraping_id"] == 42
        assert link["username"] == "creator_legacy"

    def test_legacy_discovery_tables_are_dropped(self, base_conn):
        for table in (
            "discovery_campaigns",
            "discovered_profiles",
            "discovery_interactions",
            "discovery_progress",
            "discovery_templates",
        ):
            base_conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")

        run_migrations(base_conn)
        run_migrations(base_conn)

        tables = {
            row["name"]
            for row in base_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        assert "discovery_campaigns" not in tables
        assert "discovered_profiles" not in tables
        assert "discovery_interactions" not in tables
        assert "discovery_progress" not in tables
        assert "discovery_templates" not in tables
