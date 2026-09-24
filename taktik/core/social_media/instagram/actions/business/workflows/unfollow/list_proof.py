"""When a read of a follow list proves something: the count it must reach, and how long to scroll.

Review of 2026-09-24. A list read was "complete" after a few scrolls that brought no new name:
a slow page, a scroll that failed in silence, or a list Instagram throttles looked exactly like the
end. The non-followers mode then took every account the read had not reached for a non-follower,
and the following sync marked every account it had not reached as unfollowed elsewhere. And with
100 scrolls at most (4 to 5 rows each), no list of more than about 450 accounts could ever end.

A read now proves its end against the EXACT count the unified list shows on its tab ("1 287
suivi(e)s", "673 followers", "48 following"): the names seen must reach it, give or take the few
accounts Instagram never lists (deactivated ones). Without that count, or after a failed scroll,
the read proves nothing. Pure functions: the screen is read by the mixins.

Decision of 2026-09-24 (Kevin), after a phone read of 653 followers of 673 shown: every name seen
was read, the read ended on the suggestions header, and the 20 missing were accounts Instagram
counts and never lists. The tolerance (13 there) called that read unproven, so the non-followers
mode found no candidate on that account, ever. A second rule now proves such a read: nothing seen
was left out AND the suggestions header ended the list, with a gap to the tab's count of 5 % at
most. Outside it, the count rule stands alone. The rule that proved a read is named in the log.
"""

from typing import Iterable, Mapping, Optional

# The separators a count is written with: space, no-break space, narrow no-break space.
_SPACES = (" ", " ", " ")


def parse_tab_count(text: Optional[str], labels: Iterable[str]) -> Optional[int]:
    """The exact count of a tab title, or None when the title gives none.

    "1 287 suivi(e)s" -> 1287, "673 followers" -> 673, "1,287 followers" -> 1287. An
    abbreviated count ("12,3 k followers", "1.2M followers") is not exact: None. So is a title
    whose words are not one of `labels`.
    """
    text = (text or "").strip()
    end = 0
    while end < len(text) and (text[end].isdigit() or text[end] in _SPACES or text[end] in ",."):
        end += 1
    number, rest = text[:end].strip(), text[end:].strip().lower()
    if not number or not any(label and rest.startswith(label.lower()) for label in labels):
        return None
    digits = number
    for space in _SPACES:
        digits = digits.replace(space, "")
    if "," in digits or "." in digits:
        groups = digits.replace(",", ".").split(".")
        # Thousands groups have 3 digits; anything else is a decimal, so an abbreviation.
        if not groups[0] or any(len(group) != 3 for group in groups[1:]):
            return None
        digits = "".join(groups)
    return int(digits) if digits.isdigit() else None


def count_tolerance(expected: int) -> int:
    """Accounts a complete read may miss: the ones Instagram counts but never lists."""
    return max(2, expected // 50)


# The rules that prove a read complete, as the log and the stats name them.
PROOF_BY_COUNT = "count"
PROOF_BY_SUGGESTIONS_END = "suggestions_end"

# The largest gap to the tab's count a read ended by the suggestions header may leave, in percent.
SUGGESTIONS_END_MAX_GAP_PERCENT = 5


def proof_of_read(seen: int, expected: Optional[int], scroll_failed: bool, *,
                  suggestions_reached: bool = False, left_out: Optional[Mapping[str, int]] = None,
                  ) -> Optional[str]:
    """The rule that proves a read of a list of `expected` accounts complete, or None.

    PROOF_BY_COUNT: the names seen reach the count, give or take `count_tolerance`.
    PROOF_BY_SUGGESTIONS_END: the suggestions header ended the list, no name seen was left out
    (`left_out` is empty: see LeftOutRows.summary) and the gap to the count is at most
    SUGGESTIONS_END_MAX_GAP_PERCENT of it. A failed scroll, or no count, proves nothing.
    """
    if scroll_failed or expected is None:
        return None
    if seen >= expected - count_tolerance(expected):
        return PROOF_BY_COUNT
    gap = expected - seen
    if suggestions_reached and not left_out and gap * 100 <= expected * SUGGESTIONS_END_MAX_GAP_PERCENT:
        return PROOF_BY_SUGGESTIONS_END
    return None


def read_is_complete(seen: int, expected: Optional[int], scroll_failed: bool, *,
                     suggestions_reached: bool = False,
                     left_out: Optional[Mapping[str, int]] = None) -> bool:
    """Did the read reach the end of a list of `expected` accounts, having seen `seen`?"""
    return proof_of_read(seen, expected, scroll_failed, suggestions_reached=suggestions_reached,
                         left_out=left_out) is not None


def describe_proof(rule: Optional[str], seen: int, expected: Optional[int]) -> str:
    """The end of a read, for the log: which rule proved it, or that none did."""
    total = expected if expected is not None else "?"
    if rule == PROOF_BY_COUNT:
        return f"{seen} read of {total}: complete (count, tolerance {count_tolerance(expected or 0)})"
    if rule == PROOF_BY_SUGGESTIONS_END:
        return (f"{seen} read of {total}: complete (suggestions header reached, nothing left out, "
                f"gap {(expected or 0) - seen} within {SUGGESTIONS_END_MAX_GAP_PERCENT} %)")
    return f"{seen} read of {total}: NOT proven complete"


# The share of the tab's count the base must already know before a sorted read may stop at its
# first known account, in percent.
INCREMENTAL_STOP_MIN_KNOWN_PERCENT = 50


def incremental_stop_allowed(known: int, expected: Optional[int]) -> bool:
    """May a read sorted by latest follow stop at the first account the base already knows?

    Only when the base knows at least half of the tab's count. On a phone (2026-09-24) the base
    knew 6 followings of about 1 900, one of them in 1 394th position: the read stopped there and
    the 500 oldest, the unfollow's first candidates, were never read. A base that knows so little
    is not a stop point; the read goes to the end, where its end can be proved. Without a count,
    the stop stays allowed, as before.
    """
    if expected is None:
        return True
    return known * 100 >= expected * INCREMENTAL_STOP_MIN_KNOWN_PERCENT


def scrolls_for(expected: Optional[int], floor: int, ceiling: int = 3000) -> int:
    """Scrolls a whole list of `expected` accounts may take (4 to 5 rows a scroll, with margin)."""
    if not expected:
        return floor
    return max(floor, min(ceiling, expected // 3 + 20))


__all__ = [
    "PROOF_BY_COUNT", "PROOF_BY_SUGGESTIONS_END", "SUGGESTIONS_END_MAX_GAP_PERCENT",
    "INCREMENTAL_STOP_MIN_KNOWN_PERCENT", "incremental_stop_allowed",
    "parse_tab_count", "count_tolerance", "proof_of_read", "read_is_complete", "describe_proof",
    "scrolls_for",
]
