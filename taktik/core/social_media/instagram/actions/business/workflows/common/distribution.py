"""Split a session budget across several sources (targets, hashtags, post URLs).

A workflow that receives several sources and one interaction budget has to decide
who gets how much. Three strategies, picked by the operator from the desktop app:

- ``balanced`` (default): each source gets ``remaining / sources_left`` — the split
  self-adjusts, so a source that runs dry hands its leftover to the next one.
  With a budget of 50 over two targets: 25 each; if the first only yields 18,
  the second gets 32.
- ``sequential``: sources are consumed in order, each getting the full remaining
  budget. The historical behaviour — maximises fill, but with a large first
  source the others are never reached.
- ``interleaved``: alternate between sources in small batches so the session does
  not hammer a single audience in one continuous block. Costs extra navigation
  (each rotation reopens a source), which is why it is opt-in.

The driver below owns the loop; callers provide a ``run_source(source, quota)``
callback that performs the actual interactions and reports back. Session
finalisation stays OUT of the callback — a per-source runner that finalises the
session would end it after the first source (see the ``finalize`` kwarg on the
workflow runners).
"""

import json
import math
from typing import Any, Callable, Dict, List, Optional, Tuple

DISTRIBUTION_BALANCED = "balanced"
DISTRIBUTION_SEQUENTIAL = "sequential"
DISTRIBUTION_INTERLEAVED = "interleaved"
DEFAULT_DISTRIBUTION = DISTRIBUTION_BALANCED

_VALID_MODES = (
    DISTRIBUTION_BALANCED,
    DISTRIBUTION_SEQUENTIAL,
    DISTRIBUTION_INTERLEAVED,
)

# Interleaved rotation size: big enough that the list-reopening overhead stays
# marginal, small enough that a 50-profile session still rotates a few times.
INTERLEAVED_BATCH_SIZE = 10


def normalize_distribution(raw: Any) -> str:
    """Map any payload value onto a valid mode; unknown/absent means balanced."""
    value = str(raw or "").strip().lower()
    return value if value in _VALID_MODES else DEFAULT_DISTRIBUTION


# run_source(source, quota) -> (processed, session_stop)
# ``processed`` is the number of profiles actually interacted with;
# ``session_stop`` is True when the run hit a session-level stop condition
# (duration up, global limits) — the driver then stops distributing entirely.
RunSource = Callable[[str, int], Tuple[int, bool]]

# on_progress(source, index, total, quota, processed, status) with status 'running'
# (before the source runs, processed = cumulated so far) or 'done' (after).
OnProgress = Callable[[str, int, int, int, int, str], None]


def ipc_source_progress(workflow_kind: str) -> OnProgress:
    """Progress reporter for the desktop app, in the bot's stdout-JSON IPC idiom.

    The live session panel shows WHICH source is being worked and how the budget
    spreads across them — without this, a distributed run is indistinguishable
    from a single-source one until the session recap.
    """

    def report(source: str, index: int, total: int, quota: int, processed: int, status: str) -> None:
        try:
            print(json.dumps({
                "type": "source_progress",
                "workflow": workflow_kind,
                "source": source,
                "index": index,
                "total": total,
                "quota": quota,
                "processed": processed,
                "status": status,
            }), flush=True)
        except Exception:
            pass

    return report


def run_distributed(
    sources: List[str],
    budget: int,
    mode: str,
    run_source: RunSource,
    batch_size: int = INTERLEAVED_BATCH_SIZE,
    on_progress: Optional[OnProgress] = None,
) -> Dict[str, Any]:
    """Drive ``run_source`` over ``sources`` until the budget or the sources run out.

    Returns ``{'processed': int, 'per_source': {source: int}, 'session_stop': bool}``.
    """
    mode = normalize_distribution(mode)
    per_source: Dict[str, int] = {}
    remaining = max(int(budget or 0), 0)
    session_stop = False

    def run_one(source: str, quota: int, index: int, total: int) -> int:
        nonlocal remaining, session_stop
        if on_progress:
            on_progress(source, index, total, quota, per_source.get(source, 0), 'running')
        processed, stop = run_source(source, quota)
        processed = max(int(processed or 0), 0)
        per_source[source] = per_source.get(source, 0) + processed
        remaining -= processed
        if stop:
            session_stop = True
        if on_progress:
            on_progress(source, index, total, quota, per_source[source], 'done')
        return processed

    if mode == DISTRIBUTION_INTERLEAVED:
        active = [source for source in sources if source]
        positions = {source: idx + 1 for idx, source in enumerate(active)}
        total = len(active)
        while remaining > 0 and active and not session_stop:
            for source in list(active):
                if remaining <= 0 or session_stop:
                    break
                quota = min(batch_size, remaining)
                processed = run_one(source, quota, positions[source], total)
                # A batch that yields nothing means the source is dry (list
                # exhausted or everything filtered) — stop rotating through it.
                if processed == 0:
                    active.remove(source)
    else:
        pending = [source for source in sources if source]
        for index, source in enumerate(pending):
            if remaining <= 0 or session_stop:
                break
            sources_left = len(pending) - index
            quota = (
                remaining
                if mode == DISTRIBUTION_SEQUENTIAL
                else math.ceil(remaining / sources_left)
            )
            run_one(source, quota, index + 1, len(pending))

    return {
        "processed": sum(per_source.values()),
        "per_source": per_source,
        "session_stop": session_stop,
    }
