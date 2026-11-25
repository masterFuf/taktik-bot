"""The one comparison of a text with a list of terms, shared by the DM rule and the account's excluded
terms (`taktik/core/shared/text.py`).

In a text (a bio, a name, a caption, a DM), a term catches the words it starts, case and accents
aside. In a handle, which glues its words together (`leazorvak`), it is looked for anywhere. The
terms are invented: nothing here names a real account or brand.
"""

import pytest

from taktik.core.shared.text import term_in_handle, term_starting_a_word


def test_a_term_at_the_start_of_a_word_of_a_bio_is_found():
    assert term_starting_a_word("Fan de Zorvakshop depuis 2019", ("zorvak",)) == "zorvak"


def test_a_longer_word_that_holds_the_term_without_starting_with_it_is_not_found():
    assert term_starting_a_word("Fan de superzorvak depuis 2019", ("zorvak",)) is None


def test_a_text_is_compared_case_and_accents_aside_and_the_term_comes_back_as_declared():
    assert term_starting_a_word("LES ECUREUILS du parc", ("Écureuil",)) == "Écureuil"


def test_the_first_term_of_the_list_found_is_the_one_said():
    assert term_starting_a_word("brindille et zorvak", ("zorvak", "brindille")) == "zorvak"


def test_a_term_after_a_mention_or_a_hashtag_starts_a_word():
    assert term_starting_a_word("merci @zorvak_officiel et #zorvaklove", ("zorvak",)) == "zorvak"


def test_nothing_is_found_in_an_empty_text():
    assert term_starting_a_word(None, ("zorvak",)) is None
    assert term_starting_a_word("", ("zorvak",)) is None


def test_a_term_in_the_middle_of_a_handle_is_found():
    assert term_in_handle("leazorvak", ("zorvak",)) == "zorvak"


def test_a_handle_is_compared_without_its_dots_underscores_case_and_accents():
    assert term_in_handle("lea_ZORVAK.paris", ("Zorvák",)) == "Zorvák"


def test_a_term_written_in_two_words_is_found_in_a_handle_that_glues_them():
    assert term_in_handle("la.zorvakbrindille", ("zorvak brindille",)) == "zorvak brindille"


def test_a_handle_without_the_term_is_not_excluded():
    assert term_in_handle("leabrindille", ("zorvak",)) is None


@pytest.mark.parametrize("term", ["!!!", "🔥", "  ", ""])
def test_a_term_a_handle_cannot_hold_never_matches_every_handle(term):
    assert term_in_handle("leazorvak", (term,)) is None


def test_nothing_is_found_in_an_empty_handle():
    assert term_in_handle(None, ("zorvak",)) is None
