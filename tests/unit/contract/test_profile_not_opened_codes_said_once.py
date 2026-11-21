"""The codes of a profile a run could not open are declared once, in the contract.

`not_found` (the answered search lists the account nowhere), `search_slow` (the search did not load
in time) and `navigation_failed` (any other reason) were written in six places: Instagram's search,
its scraping and its cold DM, TikTok's search, its « Ces comptes » and the Lab. Each platform keeps
its own type of navigation failure (Instagram `ProfileNavigationFailure`, TikTok a code on its search)
and says it with the contract's codes; the app reads them from the generated contract
(`ProfileNotOpenedCode`, `PROFILE_NOT_OPENED_CODES`).
"""

from __future__ import annotations

import re

from taktik.core.contract.shared import (
    PROFILE_NAVIGATION_FAILED,
    PROFILE_NOT_FOUND,
    PROFILE_NOT_OPENED_CODE,
    PROFILE_SEARCH_SLOW,
)
from taktik.core.social_media.instagram.actions.atomic.navigation.search_results import (
    ProfileNavigationFailure,
    ProfileNavigationFailureReason,
)
from unit.paths import CORE

#: Where these words mean something else: the TikTok run's end (`completion_reason`, its own
#: catalogue), a comment the action did not find, the field of a TikTok cold DM counter.
OTHER_VOCABULARIES = {
    "taktik/core/contract/stop_reasons.py",
    "taktik/core/contract/tiktok.py",
    "taktik/core/social_media/instagram/services/comment/action.py",
    "taktik/core/social_media/tiktok/workflows/automation/followers/agent_handler.py",
    "taktik/core/social_media/tiktok/workflows/automation/followers/workflow.py",
    "taktik/core/social_media/tiktok/workflows/common/feed_interruptions.py",
    "taktik/core/social_media/tiktok/workflows/cold_dm/outreach.py",
}

_LITERAL = re.compile(r"""["'](?:skip_)?(?:not_found|search_slow|navigation_failed)["']""")


def test_the_three_codes_are_one_closed_set():
    assert PROFILE_NOT_OPENED_CODE.name == "ProfileNotOpenedCode"
    assert PROFILE_NOT_OPENED_CODE.values == (PROFILE_NOT_FOUND, PROFILE_SEARCH_SLOW, PROFILE_NAVIGATION_FAILED)


def test_instagram_says_every_failure_with_a_code_of_the_contract():
    said = {ProfileNavigationFailure("search", reason).unopened_code for reason in ProfileNavigationFailureReason}

    assert said == set(PROFILE_NOT_OPENED_CODE.values)


def test_tiktok_says_a_profile_not_opened_with_a_code_of_the_contract():
    from types import SimpleNamespace

    from taktik.core.social_media.tiktok.workflows.automation.target_profiles.workflow import (
        TargetProfilesWorkflow,
    )

    workflow = object.__new__(TargetProfilesWorkflow)
    actions = set()
    for failure in (PROFILE_NOT_FOUND, PROFILE_NAVIGATION_FAILED, None):
        workflow.navigation = SimpleNamespace(last_profile_navigation_failure=failure)
        actions.add(workflow._unopened_action())

    assert actions == {f"skip_{PROFILE_NOT_FOUND}", f"skip_{PROFILE_NAVIGATION_FAILED}"}


def test_no_code_is_written_outside_the_contract():
    written = []
    for root in ("taktik", "bridges"):
        for path in sorted((CORE / root).rglob("*.py")):
            relative = path.relative_to(CORE).as_posix()
            if relative == "taktik/core/contract/shared.py" or relative in OTHER_VOCABULARIES:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if _LITERAL.search(line):
                    written.append(f"{relative}:{number}: {line.strip()}")

    assert written == [], "a code of a profile not opened is read from the contract:\n" + "\n".join(written)
