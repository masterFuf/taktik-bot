"""One reading of a Lab yes/no parameter (`lab_flag`) and of a count (`lab_int`), for every action.

Five actions read their switches their own way: the feed browsing took any unknown text for yes,
the cold DM, the unfollows and the suggestions for no. The reading is now one: absent or empty
gives the action's default, a known yes or no is read, anything else is refused by name.
"""

import pytest

from bridges.tools.lab.action_test.params import lab_flag, lab_int


@pytest.mark.parametrize("value", [True, 1, "1", "true", "TRUE", " yes ", "oui"])
def test_a_yes_is_read_as_yes(value):
    assert lab_flag({"x": value}, "x", False) is True


@pytest.mark.parametrize("value", [False, 0, "0", "false", "No", "non"])
def test_a_no_is_read_as_no(value):
    assert lab_flag({"x": value}, "x", True) is False


@pytest.mark.parametrize("params", [{}, {"x": None}, {"x": ""}], ids=["absent", "none", "empty"])
@pytest.mark.parametrize("default", [True, False])
def test_an_absent_value_is_the_default(params, default):
    assert lab_flag(params, "x", default) is default


def test_a_text_that_says_neither_is_refused_by_name():
    with pytest.raises(ValueError, match="skip_ads"):
        lab_flag({"skip_ads": "sometimes"}, "skip_ads", True)


# `lab_int`, the same contract for a count.


@pytest.mark.parametrize("value, expected", [(3, 3), ("4", 4), (" 12 ", 12)])
def test_a_count_is_read(value, expected):
    assert lab_int({"n": value}, "n", 1) == expected


@pytest.mark.parametrize("params", [{}, {"n": None}, {"n": ""}], ids=["absent", "none", "empty"])
def test_an_absent_count_is_the_default(params):
    assert lab_int(params, "n", 5) == 5


@pytest.mark.parametrize("value", ["three", "2.5", True])
def test_a_count_that_is_not_a_whole_number_is_refused_by_name(value):
    with pytest.raises(ValueError, match="max_stories"):
        lab_int({"max_stories": value}, "max_stories", 3)
