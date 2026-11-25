"""The account's excluded terms on data alone (`taktik/core/shared/filtering/excluded_terms.py`).

A profile term in a profile's handle (anywhere), its name or its bio (at the start of a word) leaves
the profile out; the lists come with the run (`excludedTerms`). Invented terms only.
"""

import pytest

from taktik.core.shared.filtering.excluded_terms import (
    ExcludedTerms,
    excluded_terms_from_payload,
    profile_term_found,
)


def test_a_term_in_the_middle_of_the_handle_leaves_the_profile_out():
    found = profile_term_found({"username": "leazorvak", "full_name": "Léa", "biography": ""}, ("zorvak",))

    assert found == ("zorvak", "username")


def test_a_term_at_the_start_of_a_word_of_the_bio_leaves_the_profile_out():
    profile = {"username": "lea.photo", "full_name": "Léa", "biography": "Ambassadrice Zorvak 2026"}

    assert profile_term_found(profile, ("zorvak",)) == ("zorvak", "biography")


def test_a_longer_word_of_the_bio_that_holds_the_term_further_in_keeps_the_profile():
    profile = {"username": "lea.photo", "full_name": "Léa", "biography": "Ambassadrice superzorvak 2026"}

    assert profile_term_found(profile, ("zorvak",)) is None


def test_a_term_starting_a_word_of_the_name_leaves_the_profile_out():
    profile = {"username": "lea.photo", "full_name": "Léa de Zorvak", "biography": None}

    assert profile_term_found(profile, ("zorvak",)) == ("zorvak", "full_name")


def test_the_handle_is_read_before_the_name_and_the_bio():
    profile = {"username": "zorvak.lea", "full_name": "Zorvak", "biography": "Zorvak"}

    assert profile_term_found(profile, ("zorvak",)) == ("zorvak", "username")


def test_without_terms_nothing_is_read():
    assert profile_term_found({"username": "leazorvak"}, ()) is None


def test_a_profile_read_without_name_or_bio_is_judged_on_what_was_read():
    assert profile_term_found({"username": "lea"}, ("zorvak",)) is None


def test_the_block_reads_the_two_lists_trimmed_without_the_empty_ones():
    terms = excluded_terms_from_payload({"profileTerms": [" zorvak ", ""], "postTerms": ["brindille"]})

    assert terms == ExcludedTerms(profile_terms=("zorvak",), post_terms=("brindille",))


def test_no_block_is_no_term():
    assert excluded_terms_from_payload(None) == ExcludedTerms()
    assert excluded_terms_from_payload({}) == ExcludedTerms()


@pytest.mark.parametrize("block", ["zorvak", ["zorvak"], {"profileTerms": "zorvak"}, {"postTerms": [1]}])
def test_a_block_that_is_not_two_lists_of_texts_refuses_the_run(block):
    with pytest.raises(ValueError):
        excluded_terms_from_payload(block)


def test_the_built_config_carries_the_two_lists_and_gives_them_back():
    terms = ExcludedTerms(profile_terms=("zorvak",), post_terms=("brindille",))

    assert ExcludedTerms.from_config(terms.as_config()) == terms
    assert ExcludedTerms.from_config(None) == ExcludedTerms()
