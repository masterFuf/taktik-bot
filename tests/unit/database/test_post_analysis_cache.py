"""A post's vision analysis is paid once, not once per account.

Profile qualifications were already reused across sessions and accounts
(_load_cached_qualification), but a POST analysis was re-paid every time — including when
the very same post had just been analysed for another account of the fleet. Only the FACTS
are cached (what the post shows, its language); the per-account verdict is never stored.

The cache is keyed on the caption, so the rule fails closed: a miss only costs the call we
would have made anyway, a wrong hit would describe a different post.
"""

import sqlite3

import pytest

from taktik.core.database.instagram_post_analysis import InstagramPostAnalysis
from taktik.core.database.instagram_post_identity import (
    build_post_ref,
    is_discriminating_post_ref,
)
from taktik.core.database.local.schema import create_schema
from taktik.core.database.repositories.instagram import PostAnalysisRepository

CAPTION = "Nouvelle collection printemps disponible en boutique"


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return PostAnalysisRepository(conn)


def test_schema_stores_facts_and_never_a_verdict():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(post_analysis)")}
    assert {"post_ref", "description", "post_language", "ai_model", "ai_cost_usd", "hit_count"} <= cols
    # The per-account verdict must NOT live here: it is relative to the operating account.
    assert not {"relevant", "relevance_tier", "should_comment", "score"} & cols


def test_same_post_is_stored_once_and_reused(repo):
    ref = build_post_ref("alice", CAPTION)
    repo.record(post_ref=ref, description="A spring collection flatlay", post_author="alice",
                post_caption=CAPTION, post_language="french", ai_model="m1", ai_cost_usd=0.001)

    found = repo.find_by_ref(ref)
    assert found["description"] == "A spring collection flatlay"
    assert found["post_language"] == "french"


def test_reanalysis_upserts_instead_of_raising(repo):
    """A post can be re-analysed (cache skipped, weak caption…): the UNIQUE key must not blow up."""
    ref = build_post_ref("alice", CAPTION)
    repo.record(post_ref=ref, description="first", post_author="alice", post_caption=CAPTION)
    repo.record(post_ref=ref, description="second", post_author="alice", post_caption=CAPTION)

    assert repo.query("SELECT COUNT(*) AS n FROM post_analysis")[0]["n"] == 1
    assert repo.find_by_ref(ref)["description"] == "second"


def test_reuse_is_counted_so_the_saving_is_measurable(repo):
    ref = build_post_ref("alice", CAPTION)
    repo.record(post_ref=ref, description="d", post_author="alice", post_caption=CAPTION,
                ai_cost_usd=0.001)
    repo.mark_reused(ref)
    repo.mark_reused(ref)

    assert repo.find_by_ref(ref)["hit_count"] == 2
    summary = repo.savings_summary()
    assert summary["analyses"] == 1
    assert summary["reuses"] == 2
    assert summary["saved_usd"] == pytest.approx(0.002)


def test_hit_count_survives_a_reanalysis(repo):
    ref = build_post_ref("alice", CAPTION)
    repo.record(post_ref=ref, description="d", post_author="alice", post_caption=CAPTION)
    repo.mark_reused(ref)
    repo.record(post_ref=ref, description="refreshed", post_author="alice", post_caption=CAPTION)

    assert repo.find_by_ref(ref)["hit_count"] == 1


# ── The fail-closed rule ────────────────────────────────────────────────────

def test_a_weak_caption_is_not_cacheable():
    # Without a discriminating caption the ref degrades to the author alone, which would
    # collide across ALL of that author's captionless posts — serving the wrong analysis.
    assert is_discriminating_post_ref(CAPTION) is True
    assert is_discriminating_post_ref("Merci !") is False
    assert is_discriminating_post_ref("") is False
    assert is_discriminating_post_ref(None) is False

    assert InstagramPostAnalysis.cache_key("alice", CAPTION) == build_post_ref("alice", CAPTION)
    assert InstagramPostAnalysis.cache_key("alice", "Merci !") is None
    assert InstagramPostAnalysis.cache_key("alice", None) is None


def test_load_and_store_are_noops_when_the_post_cannot_be_keyed():
    # No DB access at all, so this must hold even without a database available.
    assert InstagramPostAnalysis.load("alice", None) is None
    assert InstagramPostAnalysis.store("alice", None, "some description") is None


def test_two_posts_of_the_same_author_do_not_share_an_analysis(repo):
    other = "Behind the scenes de notre atelier ce matin"
    ref_a = build_post_ref("alice", CAPTION)
    ref_b = build_post_ref("alice", other)
    assert ref_a != ref_b

    repo.record(post_ref=ref_a, description="collection", post_author="alice", post_caption=CAPTION)
    assert repo.find_by_ref(ref_b) is None


def test_the_cache_is_shared_across_accounts():
    """The whole point: the key carries no account, so any account reuses the same facts."""
    # Same post seen by two different operating accounts -> same key.
    assert build_post_ref("alice", CAPTION) == build_post_ref("Alice", CAPTION)
