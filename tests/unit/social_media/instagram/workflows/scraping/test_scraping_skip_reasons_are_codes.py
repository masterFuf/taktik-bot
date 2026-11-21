"""Every reason the scraping puts on `profile_skipped` is a code the app phrases, never English words.

The filters of the scraping became codes on 2026-11-20 (`_get_profile_filter_reason`), and the empty
profile page on 2026-11-21 (`profile_read_empty`). Three reasons were still sentences in English that
the Activity showed as they came, in a French app: a profile the run navigated to and never reached,
the same on a phone with no proven network, and another profile on screen after the tap. They are
codes now, with their phrase in the app's table (`src/lib/instagram/skipReasons.ts`).
"""

import re

import pytest

from taktik.core.social_media.instagram.workflows.scraping import list_scraping

CODE = re.compile(r"[a-z][a-z_]*")


@pytest.mark.parametrize("name", [
    "UNREACHABLE_REASON",
    "NOT_OPENED_OFFLINE_REASON",
    "PROFILE_READ_EMPTY_REASON",
    "OTHER_PROFILE_REASON",
])
def test_each_reason_of_the_scraping_is_a_code(name):
    reason = getattr(list_scraping, name)

    assert CODE.fullmatch(reason), f"{name} = {reason!r} is words, not a code"


def test_the_reasons_that_mark_a_profile_unreachable_are_codes():
    assert all(CODE.fullmatch(reason) for reason in list_scraping.MARKED_UNREACHABLE_REASONS)
