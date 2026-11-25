"""The account's excluded terms travel from the run's file to its session, where the profile filter, the
interaction engine and the like and comment of a post read them.

`excludedTerms` is filled by the app from the frame of the account the phone runs
(`taktik/core/contract/shared.py`); the reader keeps them in the built config
(`excluded_terms`), the session holds them (`SessionManager.excluded_terms`). The dead `blacklist_words`
key, which nothing read, is gone. Invented terms only.
"""

import pytest

from taktik.core.shared.filtering.excluded_terms import ExcludedTerms
from taktik.core.social_media.instagram.workflows.automation.config_builder import build_instagram_automation_config
from taktik.core.social_media.instagram.workflows.common.session import SessionManager


def _built(**extra):
    return build_instagram_automation_config({"workflowType": "target_followers", "target": "a_source", **extra})


def test_the_two_lists_reach_the_runs_session():
    built = _built(excludedTerms={"profileTerms": ["zorvak"], "postTerms": ["brindille"]})

    assert built["excluded_terms"] == {"profile_terms": ["zorvak"], "post_terms": ["brindille"]}
    assert SessionManager(built).excluded_terms == ExcludedTerms(profile_terms=("zorvak",), post_terms=("brindille",))


def test_a_run_without_the_block_has_no_term():
    assert SessionManager(_built()).excluded_terms == ExcludedTerms()


def test_a_config_swap_reads_the_terms_again():
    session = SessionManager(_built())

    session.update_config(_built(excludedTerms={"profileTerms": ["zorvak"]}))

    assert session.excluded_terms.profile_terms == ("zorvak",)


def test_a_block_that_is_not_two_lists_refuses_the_run():
    with pytest.raises(ValueError, match="excludedTerms"):
        _built(excludedTerms={"profileTerms": "zorvak"})


def test_the_dead_blacklist_words_key_is_gone():
    assert "blacklist_words" not in _built()["filters"]
