"""`BaseStatsManager.profiles_visited` has one sentence in the contract, wherever a line carries it.

The automation's counters said « Profiles opened. », the bench's « Profiles visited. », while the loops
count a profile that passed the filters, acted on or not (likers3, 2026-10-25). Threads and TikTok
keep their own counters of the same name: they count what they say, a profile opened.
"""

from __future__ import annotations

import dataclasses

from taktik.core.contract import diagnostics, instagram_automation
from taktik.core.contract.schema import Field
from taktik.core.contract.shared import PROFILES_VISITED


def _fields(value, seen):
    if id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, Field):
        yield value
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _fields(item, seen)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for spec in dataclasses.fields(value):
            yield from _fields(getattr(value, spec.name), seen)


def _profiles_visited_docs(module):
    seen: set = set()
    found = []
    for name in dir(module):
        for field in _fields(getattr(module, name), seen):
            if field.key == "profiles_visited":
                found.append(field.doc)
    return found


def test_the_stats_manager_counter_is_said_one_way():
    docs = _profiles_visited_docs(instagram_automation) + _profiles_visited_docs(diagnostics)

    assert len(docs) >= 3, docs
    assert set(docs) == {PROFILES_VISITED}
