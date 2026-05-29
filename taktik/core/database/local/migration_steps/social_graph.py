"""Instagram social graph migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_profile_following_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure profile_following has FK and classification fields."""
    try:
        cursor.execute("SELECT profile_id FROM profile_following LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding profile_id to profile_following")
        cursor.execute(
            "ALTER TABLE profile_following ADD COLUMN profile_id INTEGER "
            "REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL"
        )
        logger.info("Migration: Backfilling profile_id in profile_following from instagram_profiles")
        cursor.execute("""
            UPDATE profile_following
            SET profile_id = (
                SELECT ip.profile_id FROM instagram_profiles ip
                WHERE ip.username = profile_following.profile_username
            )
            WHERE profile_id IS NULL
        """)
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_profile_following_profile_id "
                "ON profile_following(profile_id)"
            )
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("SELECT following_id FROM profile_following LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding following_id to profile_following")
        cursor.execute(
            "ALTER TABLE profile_following ADD COLUMN following_id INTEGER "
            "REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL"
        )
        logger.info("Migration: Backfilling following_id in profile_following from instagram_profiles")
        cursor.execute("""
            UPDATE profile_following
            SET following_id = (
                SELECT ip.profile_id FROM instagram_profiles ip
                WHERE ip.username = profile_following.following_username
            )
            WHERE following_id IS NULL
        """)
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_profile_following_following_id "
                "ON profile_following(following_id)"
            )
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("SELECT niche_category FROM profile_following LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding niche_category, niche, gender, classified_at to profile_following")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN niche_category TEXT")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN niche TEXT")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN gender TEXT")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN classified_at TEXT")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_profile_following_niche_category "
                "ON profile_following(niche_category)"
            )
        except sqlite3.OperationalError:
            pass
