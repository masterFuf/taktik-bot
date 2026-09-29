"""The shared count parsers, against the separators a real phone emits.

Both were wrong on French counters, and in two different ways: `parse_count` returned 0, while
`ActionUtils.parse_number_from_text` TRUNCATED at the separator ('188 472' -> 188). The second is
the dangerous one — a plausible number does not look like a failure, so a follower threshold was
comparing against a hundredth of the real count with nothing in the logs to say so.

Instagram was never affected: it calls its own parser (`instagram/ui/extractors.py`), which
already normalised. That is also why nobody noticed for so long.
"""

import pytest

from taktik.core.shared.actions.utils import ActionUtils, parse_count

NNBSP = " "   # narrow no-break space — what French Android emits between thousands
NBSP = " "
THIN = " "


@pytest.mark.parametrize("separator", [NNBSP, NBSP, THIN, " "])
def test_parse_count_reads_french_thousands_whatever_the_space(separator):
    assert parse_count(f"5{separator}215") == 5215
    assert parse_count(f"188{separator}472") == 188472


@pytest.mark.parametrize("separator", [NNBSP, NBSP, THIN, " "])
def test_parse_number_from_text_does_not_truncate_at_the_separator(separator):
    """The regression that returned 188 for 188 472."""
    assert ActionUtils.parse_number_from_text(f"188{separator}472") == 188472
    assert ActionUtils.parse_number_from_text(f"1{separator}363") == 1363


def test_suffixed_counts_still_parse():
    """The formats that already worked must keep working — this is a normalisation, not a rewrite."""
    assert parse_count("18.5K") == 18500
    assert parse_count("166 K") == 166000
    assert parse_count("1,2M") == 1200000
    assert parse_count("3B") == 3_000_000_000
    assert parse_count("424") == 424


def test_suffix_after_a_narrow_space_parses_like_after_a_plain_one():
    """'169,2 K' with a narrow space is the French rendering of the same number."""
    assert parse_count(f"169,2{NNBSP}K") == parse_count("169,2 K") == 169200


def test_empty_and_junk_stay_at_their_old_answers():
    assert parse_count("") == 0
    assert parse_count("abc") == 0
    assert ActionUtils.parse_number_from_text("") is None


def test_both_parsers_now_agree_with_instagrams_own():
    """Instagram's local parser was already right; the shared ones now match it."""
    from taktik.core.social_media.instagram.ui.extractors import parse_number_from_text as ig

    for raw in (f"5{NNBSP}215", f"188{NNBSP}472", "39,7 K", "12.3K", "5215"):
        assert parse_count(raw) == ig(raw), raw
        assert ActionUtils.parse_number_from_text(raw) == ig(raw), raw
