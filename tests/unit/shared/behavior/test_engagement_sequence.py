"""Per-post engagement choreography — varied order, valid steps, intent-respecting."""

import random
from collections import Counter

from taktik.core.shared.behavior.engagement_sequence import plan_engagement_sequence


def test_empty_when_no_intent():
    assert plan_engagement_sequence(False, False) == []


def test_like_only_sequences_contain_like_never_comment():
    rng = random.Random(1)
    seqs = [tuple(plan_engagement_sequence(True, False, rng=rng)) for _ in range(300)]
    for s in seqs:
        assert 'like' in s and 'comment' not in s
        assert set(s) <= {'read', 'like'}
    # both a bare like and a read+like variant occur (not always the same)
    uniq = set(seqs)
    assert len(uniq) >= 2


def test_like_and_comment_always_has_both_varied_order():
    rng = random.Random(2)
    seqs = [tuple(plan_engagement_sequence(True, True, rng=rng)) for _ in range(400)]
    for s in seqs:
        assert 'like' in s and 'comment' in s
        assert set(s) <= {'read', 'like', 'comment'}
    uniq = set(seqs)
    # at least the read-first and like-first patterns both show up
    assert (('read', 'like', 'comment') in uniq) and (('like', 'read', 'comment') in uniq)
    # a no-read pattern also occurs
    assert ('like', 'comment') in uniq


def test_comment_only():
    rng = random.Random(3)
    seqs = [tuple(plan_engagement_sequence(False, True, rng=rng)) for _ in range(100)]
    for s in seqs:
        assert 'comment' in s and 'like' not in s


def test_steps_are_unique_within_a_sequence():
    rng = random.Random(4)
    for _ in range(200):
        s = plan_engagement_sequence(True, True, rng=rng)
        assert len(s) == len(set(s))   # never repeats a sub-action


def test_distribution_roughly_matches_weights():
    rng = random.Random(99)
    n = 4000
    c = Counter(tuple(plan_engagement_sequence(True, True, rng=rng)) for _ in range(n))
    # C (no read) ≈ 0.25, read-first ≈ 0.30 — sanity bounds, not exact
    assert 0.18 < c[('like', 'comment')] / n < 0.32
    assert 0.22 < c[('read', 'like', 'comment')] / n < 0.38
