"""Recording a model benchmark — one place, so a result can be read months later.

Write-side facade, sibling of `instagram_posted_comments.py` and `instagram_post_analysis.py`:
the caller says what happened, this decides how it is stored. It never raises — a benchmark that
cannot write its row must still finish its calls and print its table, because the calls are the
part that costs money.

The reader lives on the desktop side (the admin benchmark page). Nothing here reads back beyond
what a run needs to continue.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger


class AIBenchmark:
    """Write side of `ai_benchmark_runs` / `ai_benchmark_results`."""

    @staticmethod
    def _db():
        from taktik.core.database.local.service import get_local_database

        return get_local_database()

    @staticmethod
    def start_run(
        *,
        seed: Optional[int],
        sample_size: int,
        budget_usd: Optional[float],
        config: Dict[str, Any],
        note: Optional[str] = None,
    ) -> Optional[int]:
        """Open a run and return its id, or None if the base would not have it.

        Opened BEFORE the first call, not after the last: a run that dies mid-way is then visible
        as `running` with the cases it did finish, instead of vanishing with everything it cost.
        """
        try:
            return AIBenchmark._db().ai_benchmarks.start_run(
                seed=seed,
                sample_size=sample_size,
                budget_usd=budget_usd,
                config_json=json.dumps(config, ensure_ascii=False),
                note=note,
            )
        except Exception as exc:  # noqa: BLE001 — accounting must never break the run
            logger.debug(f"Benchmark run could not be opened: {exc}")
            return None

    @staticmethod
    def record(
        *,
        run_id: Optional[int],
        task: str,
        case_ref: str,
        model: str,
        served_model: Optional[str],
        cost_usd: Optional[float],
        seconds: Optional[float],
        baseline: Any,
        candidate: Any,
        agreement: Any = None,
    ) -> None:
        """Store one case, as soon as it is answered."""
        if not run_id:
            return
        def dump(value: Any) -> Optional[str]:
            return json.dumps(value, ensure_ascii=False) if value is not None else None

        try:
            AIBenchmark._db().ai_benchmarks.record_result(
                run_id=run_id,
                task=task,
                case_ref=case_ref,
                model=model,
                served_model=served_model,
                cost_usd=cost_usd,
                seconds=seconds,
                baseline_json=dump(baseline),
                candidate_json=dump(candidate),
                agreement_json=dump(agreement),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Benchmark result could not be stored: {exc}")

    @staticmethod
    def finish_run(*, run_id: Optional[int], status: str, total_cost_usd: float) -> None:
        """Close a run: how it ended, and what it cost in total."""
        if not run_id:
            return
        try:
            AIBenchmark._db().ai_benchmarks.finish_run(
                run_id=run_id, status=status, total_cost_usd=total_cost_usd
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Benchmark run could not be closed: {exc}")


__all__ = ["AIBenchmark"]
