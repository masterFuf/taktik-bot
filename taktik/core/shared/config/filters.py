"""Where a workflow configuration keeps its profile filters — answered in one place.

A configuration reaches a workflow in more than one shape. The app, the scheduler and
the command line send a nested block; the runners that rebuild a config put the same
criteria as flat keys next to everything else; and a rebuilt config renames the block
along the way. Every reader used to re-answer the question itself, with the same
defensive expression copied around, and the copies were not equivalent — some returned
``None`` when the key existed but was empty.

The failure mode this guards against is silent, and has happened twice. Two halves of a
system read two different shapes of the same setting: as long as the operator configures
nothing, both shapes hold the same values and nothing looks wrong. The day a threshold
is actually set, one half sees it and the other keeps the defaults.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

#: Nested block names, most specific first. A rebuilt config carries the criteria under
#: ``filter_criteria``; a config coming straight from a producer carries them under
#: ``filters``.
_NESTED_KEYS = ("filters", "filter_criteria")


def resolve_filter_criteria(config: Mapping[str, Any] | None) -> Dict[str, Any]:
    """The filter criteria of ``config``, whichever shape the producer used.

    Flat keys sitting on the config are the base, the nested blocks are layered on top,
    the most specific last. Nothing is dropped on the way through: this is a merge and
    not a reconstruction, so a criterion added by a producer reaches its reader without
    anyone having to widen a list here first.

    Always returns a dict — a key present but empty reads as absent, which is what the
    callers that guarded with ``or {}`` already meant.
    """
    if not config:
        return {}

    resolved: Dict[str, Any] = {
        key: value for key, value in config.items() if key not in _NESTED_KEYS
    }
    for key in _NESTED_KEYS:
        block = config.get(key)
        if isinstance(block, Mapping):
            resolved.update(block)
    return resolved
