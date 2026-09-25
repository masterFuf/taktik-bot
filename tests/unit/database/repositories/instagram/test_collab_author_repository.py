"""The author line of a collaboration post, stored whole where one handle was expected, is repaired.

Before the extraction kept the first handle (`username_from_author_header`), the hashtag pass
filed "a et b" as the post author, and a like recorded under it created a profile nobody can open.
Run against the real schema (create_schema + migrations) on a temporary file; every handle here
is invented.
"""

import pytest

from taktik.core.database.repositories.instagram.hashtag import ProcessedHashtagPostRepository
from taktik.core.database.repositories.instagram.interaction import InteractionRepository
from taktik.core.database.repositories.instagram.post_author import (
    CollabAuthorRepository,
    collab_first_author,
)
from taktik.core.database.repositories.instagram.profile import ProfileRepository

COLLAB = "lina.photo et marc_studio"


@pytest.mark.parametrize("value, author", [
    ("lina.photo et marc_studio", "lina.photo"),
    ("atelier_nord and bois.clair", "atelier_nord"),
    ("Atelier_Nord   and   @bois.clair", "atelier_nord"),
    ("atelier_nord et 2\u00a0autres personnes", "atelier_nord"),
    ("atelier_nord and 12 others", "atelier_nord"),
    ("  lina.photo\u00a0et\u00a0marc_studio  ", "lina.photo"),
])
def test_a_collaboration_line_gives_its_first_handle(value, author):
    assert collab_first_author(value) == author


@pytest.mark.parametrize("value", [
    None, "", "lina.photo", "lina.photo   ",
    "Send message", "Envoyer un message",          # other text with a space, no collaboration
    "rock and roll lover",                         # no handle after the conjunction
    "J\u2019aime et 2 autres",                     # an interface label, not a handle
    ".lina et marc_studio",                        # not a valid handle
    "lina.photo et marc studio",                   # the second part is no handle either
    "Marie et Paul - Atelier",                     # a display name
])
def test_anything_else_is_no_collaboration(value):
    assert collab_first_author(value) is None


def _hashtag_post(conn, author, caption_hash="h1", processed_at="2026-01-10 10:00:00",
                  account_id=1, hashtag="velo"):
    cursor = conn.execute(
        "INSERT INTO processed_hashtag_posts (account_id, hashtag, post_author, post_caption_hash, "
        "processed_at) VALUES (?, ?, ?, ?, ?)",
        (account_id, hashtag, author, caption_hash, processed_at),
    )
    conn.commit()
    return cursor.lastrowid


def _authors(conn):
    return {row["id"]: row["post_author"]
            for row in conn.execute("SELECT id, post_author FROM processed_hashtag_posts")}


def test_the_plan_writes_nothing(conn):
    row_id = _hashtag_post(conn, COLLAB)
    ProfileRepository(conn).get_or_create(COLLAB)

    plan = CollabAuthorRepository(conn).plan()

    assert [fix.row_id for fix in plan.hashtag_posts] == [row_id]
    assert [fix.stored for fix in plan.phantom_profiles] == [COLLAB]
    assert _authors(conn) == {row_id: COLLAB}
    marked = conn.execute("SELECT unreachable_at FROM social_profiles WHERE username = ?", (COLLAB,)).fetchone()
    assert marked["unreachable_at"] is None


def test_the_hashtag_memory_matches_the_post_again(conn):
    """The run now looks the post up under its first handle; the old row must answer that key."""
    _hashtag_post(conn, COLLAB, processed_at=None)
    conn.execute("UPDATE processed_hashtag_posts SET processed_at = datetime('now')")
    conn.commit()
    memory = ProcessedHashtagPostRepository(conn)
    assert memory.is_processed(1, "velo", "lina.photo", post_caption_hash="h1") is False

    CollabAuthorRepository(conn).apply()

    assert memory.is_processed(1, "velo", "lina.photo", post_caption_hash="h1") is True


def test_a_newer_row_for_the_same_post_wins(conn):
    collab_id = _hashtag_post(conn, COLLAB, processed_at="2026-01-10 10:00:00")
    clean_id = _hashtag_post(conn, "lina.photo", processed_at="2026-01-12 10:00:00")

    CollabAuthorRepository(conn).apply()

    assert _authors(conn) == {clean_id: "lina.photo"}
    assert collab_id not in _authors(conn)


def test_an_older_row_for_the_same_post_gives_way(conn):
    clean_id = _hashtag_post(conn, "lina.photo", processed_at="2026-01-08 10:00:00")
    collab_id = _hashtag_post(conn, COLLAB, processed_at="2026-01-10 10:00:00")

    CollabAuthorRepository(conn).apply()

    assert _authors(conn) == {collab_id: "lina.photo"}
    assert clean_id not in _authors(conn)


def test_two_lines_of_the_same_post_end_as_one_row(conn):
    _hashtag_post(conn, COLLAB, processed_at="2026-01-10 10:00:00")
    newest = _hashtag_post(conn, "lina.photo et 2 autres personnes", processed_at="2026-01-11 10:00:00")

    CollabAuthorRepository(conn).apply()

    assert _authors(conn) == {newest: "lina.photo"}


def test_a_line_spaced_only_with_no_break_spaces_is_found(conn):
    row_id = _hashtag_post(conn, "lina.photo\u00a0et\u00a02\u00a0autres\u00a0personnes")

    assert [fix.row_id for fix in CollabAuthorRepository(conn).plan().hashtag_posts] == [row_id]


def test_without_a_caption_hash_the_row_is_only_renamed(conn):
    clean_id = _hashtag_post(conn, "lina.photo", caption_hash=None)
    collab_id = _hashtag_post(conn, COLLAB, caption_hash=None)

    CollabAuthorRepository(conn).apply()

    assert _authors(conn) == {clean_id: "lina.photo", collab_id: "lina.photo"}


def _with_target_username(conn):
    """The desktop migration adds this denormalised column; the bot schema has none."""
    conn.execute("ALTER TABLE interactions ADD COLUMN target_username TEXT")
    conn.commit()


def _profile_row(conn, username):
    return conn.execute(
        "SELECT legacy_profile_id, unreachable_at, unreachable_count, updated_at "
        "FROM social_profiles WHERE platform = 'instagram' AND username = ?",
        (username,),
    ).fetchone()


def test_a_like_filed_under_the_line_moves_to_the_first_author(conn):
    _with_target_username(conn)
    profiles = ProfileRepository(conn)
    author_id, _ = profiles.get_or_create("lina.photo")
    phantom_id, _ = profiles.get_or_create(COLLAB)
    conn.execute("UPDATE social_profiles SET updated_at = '2026-01-01 00:00:00' WHERE username = ?", (COLLAB,))
    interactions = InteractionRepository(conn)
    own_like = interactions.record(account_id=1, profile_id=phantom_id, interaction_type="LIKE")
    own_comment = interactions.record(account_id=1, profile_id=phantom_id, interaction_type="COMMENT")
    conn.execute("UPDATE interactions SET target_username = ? WHERE id = ?", (COLLAB, own_comment))
    conn.execute(
        "INSERT INTO interactions (platform, account_id, profile_id, interaction_type, origin_device_id, "
        "target_username) VALUES ('instagram', 9, ?, 'LIKE', 'another-device', 'someone.else')",
        (phantom_id,),
    )
    conn.commit()

    done = CollabAuthorRepository(conn).apply()

    assert [(fix.stored, fix.author_profile_id, fix.own_interactions) for fix in done.phantom_profiles] == [
        (COLLAB, author_id, 2)
    ]
    rows = {row["id"]: row for row in conn.execute("SELECT id, profile_id, target_username, origin_device_id FROM interactions")}
    assert rows[own_like]["profile_id"] == author_id
    assert rows[own_like]["target_username"] is None
    assert rows[own_comment]["profile_id"] == author_id
    assert rows[own_comment]["target_username"] == "lina.photo"
    foreign = [row for row in rows.values() if row["origin_device_id"] == "another-device"]
    assert foreign[0]["profile_id"] == phantom_id
    assert foreign[0]["target_username"] == "someone.else"

    phantom = _profile_row(conn, COLLAB)
    assert phantom is not None, "a phantom is marked, never deleted"
    assert phantom["unreachable_at"] is not None
    assert phantom["unreachable_count"] == 1
    assert phantom["updated_at"] > "2026-01-01 00:00:00"
    assert _profile_row(conn, "lina.photo")["unreachable_at"] is None


def test_without_the_first_author_in_base_the_phantom_is_only_marked(conn):
    phantom_id, _ = ProfileRepository(conn).get_or_create(COLLAB)
    like = InteractionRepository(conn).record(account_id=1, profile_id=phantom_id, interaction_type="LIKE")

    done = CollabAuthorRepository(conn).apply()

    assert [(fix.author, fix.author_profile_id) for fix in done.phantom_profiles] == [("lina.photo", None)]
    assert conn.execute("SELECT profile_id FROM interactions WHERE id = ?", (like,)).fetchone()[0] == phantom_id
    assert _profile_row(conn, COLLAB)["unreachable_at"] is not None
    assert _profile_row(conn, "lina.photo") is None, "no profile is invented"


def test_the_phantom_gets_the_mark_of_a_profile_the_bot_could_not_open(db):
    """Same statement as LocalDatabaseService.mark_profile_unreachable, not a second spelling."""
    conn = db._get_connection()
    ProfileRepository(conn).get_or_create(COLLAB)
    ProfileRepository(conn).get_or_create("gone.account")

    CollabAuthorRepository(conn).apply()
    assert db.mark_profile_unreachable("gone.account") is True

    phantom, gone = _profile_row(conn, COLLAB), _profile_row(conn, "gone.account")
    assert (phantom["unreachable_count"], gone["unreachable_count"]) == (1, 1)
    assert phantom["unreachable_at"] is not None and gone["unreachable_at"] is not None


def test_a_second_run_changes_nothing(conn):
    _hashtag_post(conn, COLLAB)
    profiles = ProfileRepository(conn)
    profiles.get_or_create("lina.photo")
    phantom_id, _ = profiles.get_or_create(COLLAB)
    InteractionRepository(conn).record(account_id=1, profile_id=phantom_id, interaction_type="LIKE")
    repo = CollabAuthorRepository(conn)
    repo.apply()

    assert repo.plan().has_work is False
    repo.apply()
    assert _profile_row(conn, COLLAB)["unreachable_count"] == 1


def test_other_text_with_a_space_is_left_alone(conn):
    profiles = ProfileRepository(conn)
    profiles.get_or_create("Send message", full_name="Marie et Paul - Atelier")
    profiles.get_or_create("lina.photo", full_name="Lina et Marc")
    row_id = _hashtag_post(conn, "lina.photo")

    plan = CollabAuthorRepository(conn).plan()

    assert plan.has_work is False
    CollabAuthorRepository(conn).apply()
    assert _profile_row(conn, "Send message")["unreachable_at"] is None
    assert _authors(conn) == {row_id: "lina.photo"}


def test_notification_actors_are_counted_not_written(conn):
    conn.execute(
        "INSERT INTO notifications (platform, account_id, actor_username, content_hash, sync_id) "
        "VALUES ('instagram', 1, 'lina.photo and marc_studio', 'hash-1', 'sync-1')"
    )
    conn.commit()

    plan = CollabAuthorRepository(conn).plan()
    CollabAuthorRepository(conn).apply()

    assert plan.counted["notifications.actor_username"] == 1
    assert plan.has_work is False
    actor = conn.execute("SELECT actor_username FROM notifications").fetchone()[0]
    assert actor == "lina.photo and marc_studio"


def test_a_failure_midway_leaves_the_base_as_it_was(conn, monkeypatch):
    row_id = _hashtag_post(conn, COLLAB)
    ProfileRepository(conn).get_or_create(COLLAB)
    repo = CollabAuthorRepository(conn)

    def boom(_fixes):
        raise RuntimeError("disk full")

    monkeypatch.setattr(repo, "_apply_phantom_profiles", boom)
    with pytest.raises(RuntimeError):
        repo.apply()

    assert _authors(conn) == {row_id: COLLAB}
    assert conn.in_transaction is False
