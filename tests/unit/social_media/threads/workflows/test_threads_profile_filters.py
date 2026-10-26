"""The Threads follower ceiling reads 0 as "no limit", by the rule the shared evaluator uses.

The page lets "Followers max" go down to 0; the filter compared literally and refused every profile
with a single follower. The rule is written once (`shared/filtering/profile_filters.exceeds_ceiling`)
and Threads calls it; merging the three filters (Threads, scraping, shared) is a 2.x chantier.
"""

import pytest

from taktik.core.social_media.threads.workflows.agent_handler import (
    threads_feed_config_from_payload,
    threads_search_config_from_payload,
)
from taktik.core.social_media.threads.workflows.search_and_interact import _passes_filters


def _config(reader, filters):
    payload = {"searchQuery": "creators", "filters": filters}
    return reader(payload)


READERS = [threads_search_config_from_payload, threads_feed_config_from_payload]


@pytest.mark.parametrize("reader", READERS, ids=["search", "feed"])
def test_a_zero_follower_ceiling_lets_any_profile_through(reader):
    logs = []
    config = _config(reader, {"minFollowers": 0, "maxFollowers": 0})
    passed = _passes_filters({"username": "creator", "followers": 48_000}, config.filters,
                             lambda level, message: logs.append(message))
    assert passed is True, logs


@pytest.mark.parametrize("reader", READERS, ids=["search", "feed"])
def test_a_follower_ceiling_still_refuses_the_profile_above_it(reader):
    logs = []
    config = _config(reader, {"maxFollowers": 10_000})
    passed = _passes_filters({"username": "creator", "followers": 48_000}, config.filters,
                             lambda level, message: logs.append(message))
    assert passed is False
    assert logs == ["⏭️ Filtered @creator — 48000 followers outside [0, 10000]"]
