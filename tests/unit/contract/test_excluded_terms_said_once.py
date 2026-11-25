"""The reasons and the places of the account's excluded terms are declared once, in the contract, and the
rule on data says a place with the same words.

`taktik/core/shared/filtering/excluded_terms.py` lives below the contract (`shared` imports no transverse
family), so it says where it found a term by the key of the profile filter's vocabulary it read; the
contract's `ExcludedTermPlace` names those same keys, and the caption. The app reads both catalogues from
the generated contract (`ExcludedTermReason`, `ExcludedTermPlace`).
"""

from taktik.core.contract.shared import (
    CAPTION,
    EXCLUDED_TERM,
    EXCLUDED_TERM_PLACE,
    EXCLUDED_TERM_REASON,
    POST_CAPTION_UNREAD,
    POST_EXCLUDED_TERM,
    TERM_EXCLUSION_EVENT,
)
from taktik.core.contract.instagram_automation import INSTAGRAM_AUTOMATION
from taktik.core.shared.filtering.excluded_terms import HANDLE_FIELD, TEXT_FIELDS


def test_the_places_are_the_keys_the_rule_reads_and_the_caption():
    assert EXCLUDED_TERM_PLACE.name == "ExcludedTermPlace"
    assert EXCLUDED_TERM_PLACE.values == (HANDLE_FIELD, *TEXT_FIELDS, CAPTION)


def test_the_reasons_are_one_closed_set():
    assert EXCLUDED_TERM_REASON.name == "ExcludedTermReason"
    assert EXCLUDED_TERM_REASON.values == (EXCLUDED_TERM, POST_EXCLUDED_TERM, POST_CAPTION_UNREAD)


def test_the_automation_declares_the_block_and_the_line():
    assert INSTAGRAM_AUTOMATION.setting("excludedTerms") is not None
    assert TERM_EXCLUSION_EVENT in INSTAGRAM_AUTOMATION.events
