"""Read one row of TikTok's Activity page.

The row is a whole sentence, not a set of fields: `Kuluna et Kendal.vd_2 a aimé ta vidéo. 11 juin`.
Everything a workflow needs is inside that sentence, and everything TikTok does to render it
politely is in the way. Measured on 66 real rows across both languages on 2026-08-30:

- Every name is wrapped in BIDI ISOLATES, `\\u2068name\\u2069`. That is a gift rather than a
  nuisance: it says exactly where a name starts and ends, which no amount of splitting on commas
  would, since names contain commas, `et`, and emoji.
- The DATE is letter-spaced with WORD JOINERS: `1\\u20605\\u2060 \\u2060j\\u2060u\\u2060i\\u2060n`
  renders as `15 juin`. Read raw, every date is a different string.
- Emoji are eaten by the dump as everywhere else, so `tristan.cld34..` and `vic............` are
  names, not corrupt data.
- A row can name several people, and then count the rest: `X, Y et 45 autres`.

The names are DISPLAY NAMES, as on every other TikTok list. A workflow that wants to act on one
must open the row, exactly as the comment sheet and the new-followers page both force.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

#: What TikTok inserts for rendering and what a reader has to take back out. `⁠` is the word
#: joiner that letter-spaces every date; the rest are direction marks.
_INVISIBLE = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮⁠﻿"), None)

#: Isolate marks. Stripped only AFTER the names inside them have been read.
_ISOLATES = dict.fromkeys(map(ord, "⁦⁧⁨⁩"), None)

_NAME_IN_ISOLATE = re.compile("⁨(.*?)⁩", re.DOTALL)

#: `et 45 autres` / `and 45 others`. Both languages in one expression: this text follows the app's
#: language, but a run started before a language change would otherwise read every row as
#: single-actor and lose the count entirely.
_OTHERS = re.compile(r"\bet\s+(\d+)\s+autres\b|\band\s+(\d+)\s+others?\b", re.IGNORECASE)

#: `a aimé 12 publications` / `liked 12 posts` -- one person, several of our videos, counted
#: rather than listed. Found by the parser reporting it as `unknown` rather than filing it under
#: the first phrase it half-matched, which is the whole reason `unknown` is a real outcome.
_LIKED_POSTS = re.compile(
    r"a aimé\s+(\d+)\s+publications?|liked\s+(\d+)\s+posts?", re.IGNORECASE
)

#: What each row says happened. Measured, not translated: every phrase below was read off a real
#: Activity page. Order matters -- `liked your comment` must be tested before `liked your`.
ACTIVITY_KINDS = (
    ("like_comment", ("a aimé ton commentaire", "liked your comment")),
    ("like_video", ("a aimé ta vidéo", "ont aimé ta vidéo", "liked your video")),
    ("save_video", ("a enregistré ta vidéo", "ont enregistré ta vidéo", "saved your video")),
    ("repost", ("a republié ta vidéo", "reposted your video")),
    ("profile_view", ("a vu ton profil", "ont vu ton profil", "viewed your profile")),
    ("follow_request_approved", ("a approuvé ta demande d'abonnement",
                                 "approved your follow request")),
    ("comment", ("a commenté", "commented")),
    ("follow", ("s'est abonné", "started following you", "followed you")),
    ("mention", ("t'a mentionné", "mentioned you")),
)

#: Rows whose author acted ON US and can be answered. A profile view names people who did nothing
#: to answer, so it is a signal and not an invitation.
ENGAGING_KINDS = frozenset({
    "like_video", "like_posts", "save_video", "like_comment", "repost", "comment", "follow",
    "mention",
})


@dataclass
class ActivityRow:
    """One line of the Activity page, taken apart."""

    kind: str = "unknown"
    #: Display names, in the order the row lists them. NEVER handles.
    usernames: List[str] = field(default_factory=list)
    #: How many more people the row counted without naming (`et 45 autres`).
    others_count: int = 0
    #: The date exactly as rendered, joiners removed: `15 juin`, `3 j`, `20 h`.
    age_label: str = ""
    #: For a comment row, what was written.
    comment: str = ""
    #: For a `like_posts` row, how many of our videos this person liked in one go.
    post_count: int = 0
    #: The row as read, kept so an unrecognised one can be looked at rather than guessed about.
    raw: str = ""

    @property
    def actor_count(self) -> int:
        """How many people this row is about, named or not."""
        return len(self.usernames) + self.others_count

    @property
    def is_engaging(self) -> bool:
        return self.kind in ENGAGING_KINDS


def clean_row_text(text: Optional[str]) -> str:
    """The row as a human sees it: no direction marks, no word joiners, single spaces.

    Also folds the non-breaking spaces TikTok puts inside counts, so `20 h` and `20\\u00a0h` are
    the same string.
    """
    if not text:
        return ""
    cleaned = unicodedata.normalize("NFC", text).translate(_INVISIBLE).translate(_ISOLATES)
    cleaned = cleaned.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_activity_row(text: Optional[str]) -> ActivityRow:
    """Take one Activity row apart. Never raises; an unreadable row comes back `unknown`.

    `unknown` is a real outcome and not a failure: TikTok adds notification types without warning,
    and a parser that guessed would file them under whatever it happened to match first.
    """
    raw = text or ""
    row = ActivityRow(raw=raw)
    if not raw.strip():
        return row

    # Names first, while the isolates are still there to delimit them.
    row.usernames = [name.strip() for name in _NAME_IN_ISOLATE.findall(raw) if name.strip()]

    body = clean_row_text(raw)
    if not row.usernames:
        # No isolates at all: some builds render a single-actor row without them. Everything up to
        # the verb is then the name, and the verb is what locates it.
        row.usernames = _names_before_verb(body)

    others = _OTHERS.search(body)
    if others:
        row.others_count = int(others.group(1) or others.group(2) or 0)

    liked_posts = _LIKED_POSTS.search(body)
    if liked_posts:
        row.kind = "like_posts"
        row.post_count = int(liked_posts.group(1) or liked_posts.group(2) or 0)
        row.age_label = _trailing_date(body[liked_posts.end():])
        return row

    lowered = body.casefold()
    for kind, phrases in ACTIVITY_KINDS:
        for phrase in phrases:
            position = lowered.find(phrase.casefold())
            if position < 0:
                continue
            row.kind = kind
            tail = body[position + len(phrase):]
            if kind == "comment":
                row.comment = tail.lstrip(" :").strip()
            row.age_label = _trailing_date(tail)
            break
        if row.kind != "unknown":
            break

    if not row.age_label:
        row.age_label = _trailing_date(body)
    return row


# ----------------------------------------------------------------------------------------------


#: `15 juin`, `3 j`, `20 h`, `1 Jul`, `14 Aug`. Deliberately loose: this is a LABEL, kept as the
#: screen wrote it. Parsing it into a date would invent a year the screen never gave.
_TRAILING_DATE = re.compile(
    r"(\d{1,2}\s*[a-zéû.]{1,9}|\d{1,3}\s*[a-z]{1,4})\s*$", re.IGNORECASE
)


def _trailing_date(text: str) -> str:
    match = _TRAILING_DATE.search((text or "").rstrip(" ."))
    return match.group(1).strip() if match else ""


def _names_before_verb(body: str) -> List[str]:
    """Everything before the first known verb, when the row carried no isolates."""
    lowered = body.casefold()
    best = len(body)
    for _kind, phrases in ACTIVITY_KINDS:
        for phrase in phrases:
            position = lowered.find(phrase.casefold())
            if 0 <= position < best:
                best = position
    head = body[:best].strip(" ,")
    return [head] if head else []


__all__ = [
    "ACTIVITY_KINDS",
    "ENGAGING_KINDS",
    "ActivityRow",
    "clean_row_text",
    "parse_activity_row",
]
