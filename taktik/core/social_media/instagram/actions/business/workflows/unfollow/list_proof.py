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
"""

from typing import Iterable, Optional

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


def read_is_complete(seen: int, expected: Optional[int], scroll_failed: bool) -> bool:
    """Did the read reach the end of a list of `expected` accounts, having seen `seen`?"""
    if scroll_failed or expected is None:
        return False
    return seen >= expected - count_tolerance(expected)


def scrolls_for(expected: Optional[int], floor: int, ceiling: int = 3000) -> int:
    """Scrolls a whole list of `expected` accounts may take (4 to 5 rows a scroll, with margin)."""
    if not expected:
        return floor
    return max(floor, min(ceiling, expected // 3 + 20))


__all__ = ["parse_tab_count", "count_tolerance", "read_is_complete", "scrolls_for"]
