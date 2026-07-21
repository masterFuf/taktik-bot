"""Budget distribution across multiple sources — pure-logic tests."""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.common.distribution import (
    DEFAULT_DISTRIBUTION,
    DISTRIBUTION_BALANCED,
    DISTRIBUTION_INTERLEAVED,
    DISTRIBUTION_SEQUENTIAL,
    normalize_distribution,
    run_distributed,
)


def make_runner(yields, stop_on=None):
    """run_source stub: each source yields min(quota, yields[source]) then runs dry."""
    left = dict(yields)
    calls = []

    def run_source(source, quota):
        available = left.get(source, 0)
        processed = min(quota, available)
        left[source] = available - processed
        calls.append((source, quota, processed))
        return processed, source == stop_on

    return run_source, calls


class TestNormalize:
    def test_valid_modes_pass_through(self):
        assert normalize_distribution("sequential") == DISTRIBUTION_SEQUENTIAL
        assert normalize_distribution(" Interleaved ") == DISTRIBUTION_INTERLEAVED

    def test_unknown_and_absent_default_to_balanced(self):
        assert normalize_distribution(None) == DEFAULT_DISTRIBUTION
        assert normalize_distribution("whatever") == DISTRIBUTION_BALANCED


class TestBalanced:
    def test_even_split(self):
        run, calls = make_runner({"a": 100, "b": 100})
        result = run_distributed(["a", "b"], 50, DISTRIBUTION_BALANCED, run)
        assert result["per_source"] == {"a": 25, "b": 25}
        assert [c[1] for c in calls] == [25, 25]

    def test_dry_source_hands_leftover_to_the_next(self):
        run, _ = make_runner({"a": 18, "b": 100})
        result = run_distributed(["a", "b"], 50, DISTRIBUTION_BALANCED, run)
        assert result["per_source"] == {"a": 18, "b": 32}
        assert result["processed"] == 50

    def test_odd_budget_rounds_up_first(self):
        run, calls = make_runner({"a": 100, "b": 100, "c": 100})
        result = run_distributed(["a", "b", "c"], 50, DISTRIBUTION_BALANCED, run)
        assert result["processed"] == 50
        assert [c[1] for c in calls] == [17, 17, 16]


class TestSequential:
    def test_first_source_gets_everything(self):
        run, calls = make_runner({"a": 100, "b": 100})
        result = run_distributed(["a", "b"], 50, DISTRIBUTION_SEQUENTIAL, run)
        assert result["per_source"] == {"a": 50}
        assert calls == [("a", 50, 50)]

    def test_second_source_gets_the_remainder(self):
        run, _ = make_runner({"a": 18, "b": 100})
        result = run_distributed(["a", "b"], 50, DISTRIBUTION_SEQUENTIAL, run)
        assert result["per_source"] == {"a": 18, "b": 32}


class TestInterleaved:
    def test_alternates_in_batches(self):
        run, calls = make_runner({"a": 100, "b": 100})
        result = run_distributed(["a", "b"], 40, DISTRIBUTION_INTERLEAVED, run, batch_size=10)
        assert result["per_source"] == {"a": 20, "b": 20}
        assert [c[0] for c in calls] == ["a", "b", "a", "b"]

    def test_dry_source_leaves_the_rotation(self):
        run, calls = make_runner({"a": 5, "b": 100})
        result = run_distributed(["a", "b"], 40, DISTRIBUTION_INTERLEAVED, run, batch_size=10)
        assert result["per_source"] == {"a": 5, "b": 35}
        # a: 5 then 0 (dry, removed) — b alone finishes the budget.
        assert [c[0] for c in calls] == ["a", "b", "a", "b", "b", "b"]

    def test_all_dry_ends_before_budget(self):
        run, _ = make_runner({"a": 3, "b": 4})
        result = run_distributed(["a", "b"], 40, DISTRIBUTION_INTERLEAVED, run, batch_size=10)
        assert result["processed"] == 7
        assert result["session_stop"] is False


class TestSessionStop:
    def test_stop_halts_distribution(self):
        run, calls = make_runner({"a": 100, "b": 100}, stop_on="a")
        result = run_distributed(["a", "b"], 50, DISTRIBUTION_BALANCED, run)
        assert result["session_stop"] is True
        assert [c[0] for c in calls] == ["a"]


class TestEdges:
    def test_empty_sources(self):
        run, calls = make_runner({})
        result = run_distributed([], 50, DISTRIBUTION_BALANCED, run)
        assert result["processed"] == 0 and calls == []

    def test_zero_budget(self):
        run, calls = make_runner({"a": 100})
        result = run_distributed(["a"], 0, DISTRIBUTION_BALANCED, run)
        assert result["processed"] == 0 and calls == []

    def test_single_source_balanced_equals_sequential(self):
        for mode in (DISTRIBUTION_BALANCED, DISTRIBUTION_SEQUENTIAL):
            run, calls = make_runner({"a": 100})
            run_distributed(["a"], 50, mode, run)
            assert calls == [("a", 50, 50)]
