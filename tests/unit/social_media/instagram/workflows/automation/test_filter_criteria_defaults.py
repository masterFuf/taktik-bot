"""The ceilings `FilterCriteria` falls back on are the declaration's, not a copy of their own.

The declaration (`contract/instagram_automation.py`) gives "Max followers" 50000 and "Max following"
7500, the numbers the page shows and the builder applies. `FilterCriteria` carried 100000 and
10000, written a second time: an action without the keys was filtered with ceilings nobody had
chosen.
"""

import pytest

from taktik.core.contract.instagram_automation import FILTERS
from taktik.core.social_media.instagram.workflows.automation.config import FilterCriteria


def _declared(key):
    return FILTERS.field_by_key(key).default


@pytest.mark.parametrize("criteria", [FilterCriteria(), FilterCriteria.from_action({})],
                         ids=["dataclass", "action_without_the_keys"])
def test_the_fallback_ceilings_are_the_declared_defaults(criteria):
    assert criteria.max_followers == _declared("maxFollowers")
    assert criteria.max_following == _declared("maxFollowing")


def test_a_ceiling_the_action_carries_wins_over_the_declared_default():
    criteria = FilterCriteria.from_action({"filters": {"max_followers": 0, "max_following": 900}})
    assert criteria.max_followers == 0
    assert criteria.max_following == 900
