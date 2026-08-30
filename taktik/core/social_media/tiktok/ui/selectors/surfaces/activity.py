"""The Activity page: who liked, saved, reposted, commented, or looked.

Reached from the inbox, one row down from "Nouveaux followers". It is the only surface that tells
an account what its own content did -- which is why it is also where a bot learns who to answer.

Everything here holds BOTH languages in one expression rather than going through the locale
overlay. Measured 2026-08-30: the section headers already do this in `inbox.py` for the same
reason, and the reason is worth repeating. A run started before someone changed the app language
would otherwise find nothing at all, and finding nothing on this page is indistinguishable from
an account nobody has interacted with.

The ROWS are not selected by language. A row is anything on this page carrying a bidi isolate --
`\\u2068name\\u2069` -- which every row does and no chrome does. Parsing what it says is
`services/notifications/activity.py`, deliberately apart: the reading is version-dependent, the
sentence is not.
"""

from typing import List
from dataclasses import dataclass, field


@dataclass
class ActivitySelectors:
    """The Activity page and its rows."""

    #: The inbox row that opens this page.
    activity_entry: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Activité" or @text="Activity"]',
        '//android.widget.TextView[@text="Activité" or @text="Activity"]'
        '/ancestor::*[@clickable="true"][1]',
    ])

    #: We are on the page when its FILTER control is up.
    #:
    #: The title was tried first and is wrong: the inbox carries a TextView reading `Activité` too
    #: -- it is the row that opens this page -- and it is not clickable either, since the
    #: clickable is its ancestor. So the indicator fired on the inbox, `open_activity` believed it
    #: was already there, never tapped, and the read came back empty from the wrong screen. An
    #: anchor that cannot say no.
    #:
    #: `Priorité`/`Autres` were the other candidate and are worse: they only exist when there IS
    #: activity, so an account with none would read as "the page did not open".
    #:
    #: Measured 2026-08-30 on all three screens, which is the only way this was settled:
    #:
    #:              feed   inbox   activity
    #:   Filtres      0      0        1     <- kept
    #:   :id/pzx      0      0        3     <- kept as the fallback
    #:   :id/iil      1      0        9     <- DROPPED, it answers on the feed
    #:
    #: `iil` was in this list until that table was made. It would have reported the feed as the
    #: Activity page, which is how a read comes back empty from the wrong screen and nobody knows.
    page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Filtres" or @content-desc="Filters"]',
        '//*[contains(@resource-id, ":id/pzx")]',
    ])

    #: Opens the full list. Absent when the account has few enough notifications to fit.
    see_all_button: List[str] = field(default_factory=lambda: [
        '//*[@text="Tout voir" or @text="See all" or @text="View all"]',
    ])

    #: One notification. Anchored on the bidi isolate every row carries around its first name --
    #: language-free, and it excludes the headers, the tabs and the suggested-accounts block,
    #: none of which carry one.
    row: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "⁨")]',
    ])

    #: The section headers, useful only to tell priority rows from the rest.
    section_header: List[str] = field(default_factory=lambda: [
        '//*[@text="Priorité" or @text="Priority" or @text="Autres" or @text="Others"]',
    ])


ACTIVITY_SELECTORS = ActivitySelectors()

__all__ = ["ACTIVITY_SELECTORS", "ActivitySelectors"]
