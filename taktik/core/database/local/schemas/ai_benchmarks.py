"""DDL for model benchmarks — what a candidate model answered, on inputs we already paid for.

Owner: the evaluation tooling. Source of truth = the Bot (it is the one calling the models);
the desktop reads it to render the benchmark page.

Why the results are stored rather than left in files: a benchmark is not a one-off. The model in
use will stop being served, a cheaper one will appear, a prompt will change — and each time the
question is the same: "is this better or worse than what we run today, and on what evidence".
That answer is only worth something if it can be put next to the previous one, months apart, on
the same sample. JSONL in a temp folder answers it once.

Two tables, because a run and its cases are two different lifetimes: the run is the decision
(which models, which sample, what it cost, was it stopped), a result is one case seen by one
model. Reading "how did model X do on task Y" is then a GROUP BY, not a file walk.

`baseline`, `candidate` and `agreement` stay JSON on purpose: the shape of an answer belongs to
the task (a classification has a niche, a comment has a text), and columns per task would mean a
migration every time a new AI feature becomes testable — which is exactly what this table exists
to make cheap.
"""

from __future__ import annotations

import sqlite3


def create_ai_benchmark_tables(cursor: sqlite3.Cursor) -> None:
    """Create the benchmark tables if they do not exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_benchmark_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at TEXT,
            -- 'running' while it works, then 'completed' / 'stopped' (budget or operator) /
            -- 'error'. A run left 'running' by a crash is visibly unfinished rather than
            -- silently partial.
            status TEXT NOT NULL DEFAULT 'running',
            -- The sample is reproducible: same seed, same cases. That is what makes two runs
            -- months apart comparable at all.
            seed INTEGER,
            sample_size INTEGER,
            budget_usd REAL,
            total_cost_usd REAL DEFAULT 0,
            -- Tasks, models per task, persona account, taxonomy size — everything needed to
            -- explain a number, and to run exactly the same thing again.
            config TEXT,
            note TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_benchmark_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            -- 'profile' | 'comment' | 'post' | 'verdict' — the closed vocabulary of ai/spend.py,
            -- so a cost and a benchmark name the same things.
            task TEXT NOT NULL,
            -- What this case IS: a username, a post reference. Enough to find it again.
            case_ref TEXT NOT NULL,
            -- The model we ASKED for, and the one the gateway actually served. They differ more
            -- often than one would like, and a benchmark that cannot tell them apart is a
            -- benchmark of nothing.
            model TEXT NOT NULL,
            served_model TEXT,
            cost_usd REAL,
            seconds REAL,
            baseline TEXT,
            candidate TEXT,
            agreement TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def create_ai_benchmark_indexes(cursor: sqlite3.Cursor) -> None:
    """Indexes for the two questions the page asks: a run's cases, and a model's record."""
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_benchmark_results_run ON ai_benchmark_results(run_id, task)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_benchmark_results_model ON ai_benchmark_results(model, task)"
    )
