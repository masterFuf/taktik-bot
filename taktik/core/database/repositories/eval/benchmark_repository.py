"""Benchmark repository — owner of `ai_benchmark_runs` and `ai_benchmark_results`.

Bot is the source of truth: it is the side that calls the models. The desktop reads these two
tables to render the admin benchmark page, and writes nothing.

See `local/schemas/ai_benchmarks.py` for why the answers are stored as JSON rather than as
columns per task.
"""

from typing import Any, List, Optional

from loguru import logger

from .._base.base_repository import BaseRepository


class AIBenchmarkRepository(BaseRepository):
    """Runs and their per-case results."""

    def start_run(
        self,
        seed: Optional[int],
        sample_size: int,
        budget_usd: Optional[float],
        config_json: Optional[str],
        note: Optional[str] = None,
    ) -> Optional[int]:
        """Open a run and return its id."""
        try:
            cursor = self.execute(
                """
                INSERT INTO ai_benchmark_runs (status, seed, sample_size, budget_usd, config, note)
                VALUES ('running', ?, ?, ?, ?, ?)
                """,
                (seed, sample_size, budget_usd, config_json, note),
            )
            return cursor.lastrowid
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error opening benchmark run: {exc}")
            return None

    def record_result(
        self,
        run_id: int,
        task: str,
        case_ref: str,
        model: str,
        served_model: Optional[str],
        cost_usd: Optional[float],
        seconds: Optional[float],
        baseline_json: Optional[str],
        candidate_json: Optional[str],
        agreement_json: Optional[str],
    ) -> bool:
        """Store one case answered by one model."""
        try:
            self.execute(
                """
                INSERT INTO ai_benchmark_results
                    (run_id, task, case_ref, model, served_model, cost_usd, seconds,
                     baseline, candidate, agreement)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, task, case_ref[:200], model, served_model, cost_usd, seconds,
                 baseline_json, candidate_json, agreement_json),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error storing benchmark result: {exc}")
            return False

    def finish_run(self, run_id: int, status: str, total_cost_usd: float) -> bool:
        """Close a run with how it ended and what it cost."""
        try:
            self.execute(
                """
                UPDATE ai_benchmark_runs
                   SET status = ?, total_cost_usd = ?, finished_at = datetime('now')
                 WHERE id = ?
                """,
                (status, round(total_cost_usd, 6), run_id),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error closing benchmark run: {exc}")
            return False

    def recent_runs(self, limit: int = 50) -> List[Any]:
        """The last runs, newest first — used by the CLI to point at what it just wrote."""
        try:
            return self.query(
                "SELECT * FROM ai_benchmark_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error reading benchmark runs: {exc}")
            return []
