"""The single vocabulary for "why did this Instagram session end".

Every terminal path used to invent its own answer. Two conventions had grown side by side --
formatted English sentences ("Follows limit reached (5/5)") and bare snake_case codes
("no_valid_post") -- and the desktop app recovered the meaning by running regular expressions
over the sentences. Any motive nobody had thought to match reached the operator as raw English,
and a motive nobody had thought to SET reached them as a completed run.

This module is the one place a stop motive is built. Each factory returns a `StopReason`
carrying three things:

- ``code``     the stable identifier the desktop app translates. This is the real payload.
- ``params``   the numbers the translated sentence needs, never pre-formatted into the text.
- ``text``     the English sentence, kept BYTE-FOR-BYTE identical to what each path emits today.

That last point is the whole safety argument of this change. As long as `text` reproduces the
current output exactly, routing every caller through this catalogue cannot alter what a run
reports -- which is verifiable by comparison rather than by replaying sessions on a device.
`text` is transitional: it disappears once no consumer reads it, and `code` remains.

Some codes deliberately differ from their legacy text (``posts_cap`` emits ``budget_reached``,
``list_unavailable`` emits ``followers_list_unavailable``). The code is the vocabulary we want;
the text is the legacy we must not disturb yet.

SCOPE -- this catalogue answers ONLY "why did the session end". Three neighbouring notions keep
their own vocabularies and must not be merged into it: why a PROFILE was rejected
(``filtered_profiles.reason``, which feeds the funnel analytics), the outcome of a sub-pass
(``feed/suggestions``, diagnostic only, never surfaced), and the process lifecycle
(STOPPED / INTERRUPTED, owned by the desktop side).

The terminal STATUS is now DERIVED from the family (see ``terminal_status``). It used to be the
caller's decision, and every caller decided the same thing: ``COMPLETED``, whatever had happened.
Measured on 25 consecutive runs, 23 were filed COMPLETED — including five that ended on
``navigation_lost`` and one that never managed to open the followers list and stopped after 44
seconds with zero interactions. The motive was right there in the log; the status contradicted it,
so the operator had no way to tell a finished run from a failed one.
"""


from typing import Any, Dict


#: Does the operator need to go and look? That is the only question the family answers, and the
#: reason there are three of them rather than the five this started with: on five, three names
#: made the developer reading them guess something else. The precise motive is always in `code`.
FAMILY_OK = "ok"          # stopped as expected -- nothing to do
FAMILY_FAILED = "failed"  # did not run -- go look
FAMILY_MANUAL = "manual"  # someone pressed stop


#: Terminal status of a session, derived from the reason's family. `failed` is the only family
#: that means "this did not run" — `ok` covers every legitimate end (limits reached, sources
#: exhausted, list finished) and `manual` is the operator's own stop, which the caller already
#: reports as STOPPED.
STATUS_COMPLETED = "COMPLETED"
STATUS_INTERRUPTED = "INTERRUPTED"


#: Motives that describe ONE source, not the session. A run over several targets splits its
#: budget between them; when a list runs dry that says nothing about the targets still waiting,
#: so the driver must hand over instead of cancelling what they were allotted. Everything else
#: — the duration, the global caps, a lost navigation — ends the session wherever it happens.
#:
#: Measured before this existed: a two-target run whose first list repeated itself stopped after
#: 25 minutes with the second target never opened, and filed itself COMPLETED.
_SOURCE_SCOPED_CODES = frozenset({
    "end_of_list",
    "end_of_list_repeated",
    "end_of_list_suggestions",
    "no_new_profiles",
    "known_streak",
    "scroll_streak",
    "scroll_budget",
})


def ends_the_session(reason: Any) -> bool:
    """Does this motive stop the whole run, or only the source it came from?

    Unknown and empty motives end the session: a driver that cannot place a motive must not
    keep spending budget on a run it no longer understands.
    """
    if not reason:
        return False
    code = getattr(reason, "code", None) or str(reason).strip().lower()
    return code not in _SOURCE_SCOPED_CODES


def terminal_status(reason: Any, default: str = STATUS_COMPLETED) -> str:
    """The status a run ending on `reason` deserves.

    Accepts a `StopReason` (which carries its family) or the bare legacy string a few call sites
    still pass. An unknown string keeps `default`: a motive nobody declared must not silently
    reclassify a run as failed — the mistake would be the same one this function fixes, in the
    other direction.
    """
    family = getattr(reason, "family", None)
    if family is None:
        family = _FAMILY_BY_CODE.get(str(reason or "").strip().lower())
    return STATUS_INTERRUPTED if family == FAMILY_FAILED else default


class StopReason(str):
    """One reason a session ended. Built only by the factories below.

    It IS the legacy English sentence -- ``str(reason)``, ``f"{reason}"`` and
    ``reason == "Follows limit reached (5/5)"`` all behave exactly as they did when this was a
    plain string. That is deliberate: the motive is passed from hand to hand through eight
    callers before reaching the terminal path, and making it a separate type would have meant
    touching every one of them for no gain. Subclassing `str` lets the structured code travel
    with the sentence, and lets it travel for free.

    On top of the sentence it carries `code` (what the desktop app translates), `params` (the
    numbers that sentence needs) and `family` (does the operator need to go and look).
    """

    code: str
    params: Dict[str, Any]
    family: str

    def __new__(cls, code: str, family: str, text: str, params: Dict[str, Any]) -> "StopReason":
        reason = super().__new__(cls, text)
        reason.code = code
        reason.family = family
        reason.params = dict(params)
        return reason

    @property
    def text(self) -> str:
        """The English sentence. Same value as the object itself; named for readability."""
        return str(self)

    def event_fields(self) -> Dict[str, Any]:
        """The fields to merge into the ``session_stop`` event.

        Purely additive: ``reason`` keeps carrying the legacy sentence, so a desktop build that
        predates the catalogue behaves exactly as before, while a current one reads the code.
        """
        return {
            "reason": self.text,
            "reason_code": self.code,
            "reason_params": dict(self.params),
        }


def _reason(code: str, family: str, text: str, **params: Any) -> StopReason:
    return StopReason(code, family, text, params)


# -- ok: the run stopped as expected -------------------------------------------
#
# Limits first: duration, profiles, follows, likes, the warmup caps, the hashtag budget.

def duration_cap(minutes: Any) -> StopReason:
    # `minutes` rather than `limit_minutes`: the param names become the placeholders of the
    # translated sentence, so they are read by whoever writes the translations.
    return _reason(
        "duration_cap", FAMILY_OK,
        f"Maximum session duration reached ({minutes} minutes)",
        minutes=minutes,
    )


def profiles_cap(count: Any, limit: Any) -> StopReason:
    return _reason(
        "profiles_cap", FAMILY_OK,
        f"Profiles limit reached ({count}/{limit})",
        count=count, limit=limit,
    )


def follows_cap(count: Any, limit: Any) -> StopReason:
    return _reason(
        "follows_cap", FAMILY_OK,
        f"Follows limit reached ({count}/{limit})",
        count=count, limit=limit,
    )


def likes_cap(count: Any, limit: Any) -> StopReason:
    return _reason(
        "likes_cap", FAMILY_OK,
        f"Likes limit reached ({count}/{limit})",
        count=count, limit=limit,
    )


def daily_budget(count: Any, limit: Any) -> StopReason:
    return _reason(
        "daily_budget", FAMILY_OK,
        f"Daily action budget reached ({count}/{limit})",
        count=count, limit=limit,
    )


def session_action_cap(count: Any, limit: Any) -> StopReason:
    return _reason(
        "session_action_cap", FAMILY_OK,
        f"Session action cap reached ({count}/{limit})",
        count=count, limit=limit,
    )


def posts_cap(count: Any, limit: Any) -> StopReason:
    """Hashtag posts budget spent. Legacy text is the bare code ``budget_reached``."""
    return _reason(
        "posts_cap", FAMILY_OK,
        "budget_reached",
        count=count, limit=limit,
    )


# Then: nothing left to process.

def end_of_list(seen: int, total: int) -> StopReason:
    # The legacy sentence groups thousands (`:,`); reproduce it exactly, separators included.
    return _reason(
        "end_of_list", FAMILY_OK,
        f"End of followers list ({seen:,}/{total:,} seen)",
        seen=seen, total=total,
    )


def end_of_list_repeated() -> StopReason:
    return _reason(
        "end_of_list_repeated", FAMILY_OK,
        "End of followers list (same profiles repeated)",
    )


def end_of_list_suggestions() -> StopReason:
    return _reason(
        "end_of_list_suggestions", FAMILY_OK,
        "End of followers list (suggestions section)",
    )


def no_new_profiles(seen: Any) -> StopReason:
    return _reason(
        "no_new_profiles", FAMILY_OK,
        f"No new followers found ({seen} profiles seen)",
        seen=seen,
    )


def known_streak(streak: Any, seen: Any) -> StopReason:
    return _reason(
        "known_streak", FAMILY_OK,
        f"No new followers after {streak} known usernames in a row ({seen} seen)",
        streak=streak, seen=seen,
    )


def scroll_budget(scrolls: Any, seen: Any) -> StopReason:
    """The loop's own scroll allowance ran out, mid-list.

    Not a source that ended: a run stopped by this has followers left to work and budget left
    to spend. It reached a ceiling internal to the loop — including the gestures a private-zone
    transport bills to the same allowance, which is deliberate (a transport that under-reports
    lets a run fling past its cap). Saying so is what separates it from a run that finished.
    """
    return _reason(
        "scroll_budget", FAMILY_OK,
        f"Scroll allowance exhausted ({scrolls} scrolls, {seen} usernames seen)",
        scrolls=scrolls, seen=seen,
    )


def scroll_streak(scrolls: Any, seen: Any) -> StopReason:
    return _reason(
        "scroll_streak", FAMILY_OK,
        f"No new followers after {scrolls} scroll attempts ({seen} seen)",
        scrolls=scrolls, seen=seen,
    )


#: Codes a caller may still pass as a plain string. Only the FAILED ones need listing: anything
#: absent keeps the caller's default, which is the safe direction.
_FAMILY_BY_CODE = {
    "navigation_lost": FAMILY_FAILED,
    "stuck_at_top": FAMILY_FAILED,
    "action_blocked": FAMILY_FAILED,
    "list_unavailable": FAMILY_FAILED,
    "followers_list_unavailable": FAMILY_FAILED,
    "empty_plan": FAMILY_FAILED,
}


def sources_exhausted() -> StopReason:
    return _reason(
        "sources_exhausted", FAMILY_OK,
        "Sources exhausted (no further progress)",
    )


def no_valid_post() -> StopReason:
    return _reason("no_valid_post", FAMILY_OK, "no_valid_post")


def no_new_post() -> StopReason:
    return _reason("no_new_post", FAMILY_OK, "no_new_post")


def posts_examined_cap(examined: Any, limit: Any) -> StopReason:
    """Hashtag examined-posts ceiling. Legacy text is the bare code ``max_posts_examined``."""
    return _reason(
        "posts_examined_cap", FAMILY_OK,
        "max_posts_examined",
        examined=examined, limit=limit,
    )


# Then: the requested work is done.

def completed(interactions: Any) -> StopReason:
    return _reason(
        "completed", FAMILY_OK,
        f"Workflow completed ({interactions} interactions)",
        interactions=interactions,
    )


# -- failed: the run did not run ------------------------------------------------
#
# Includes an empty plan and a missing target list. Neither is a crash, but both mean the same
# thing to the operator: it did not run, go and look at the settings.

def action_blocked() -> StopReason:
    """Instagram is showing "Try again later": it is rate-limiting this account right now.

    Told apart from `navigation_lost` on purpose. They looked identical from the outside — the
    run cannot reach its list either way — but they call for opposite moves: a lost navigation
    is worth retrying, a block is worth stopping on. Five runs filed as lost navigation were
    this dialog, and the difference decides whether the next gesture makes things worse.
    """
    return _reason("action_blocked", FAMILY_FAILED, "action_blocked")


def stuck_at_top(scans: Any) -> StopReason:
    """Scrolling stopped advancing: the same head of list came back N scans in a row."""
    return _reason(
        "stuck_at_top", FAMILY_FAILED,
        f"Stuck at the top of the list ({scans} scans without advancing)",
        scans=scans,
    )


def navigation_lost() -> StopReason:
    return _reason("navigation_lost", FAMILY_FAILED, "navigation_lost")


def list_unavailable() -> StopReason:
    """Followers list gone (suggestions screen / navigation drift)."""
    return _reason("list_unavailable", FAMILY_FAILED, "followers_list_unavailable")


def empty_plan() -> StopReason:
    return _reason("empty_plan", FAMILY_FAILED, "empty_plan")


def no_targets() -> StopReason:
    return _reason("no_targets", FAMILY_FAILED, "no_targets")


def crashed(error: Any) -> StopReason:
    """The run died on an unhandled exception.

    The critical catch used to log, mark the row ERROR and return — without emitting
    ``session_stop``. The desktop's live card then hung forever on a run that was already dead,
    and the session kept no motive at all. A crash is a stop reason like any other; it is simply
    the one nobody had declared.
    """
    text = str(error).strip() or error.__class__.__name__
    return _reason("crashed", FAMILY_FAILED, f"Workflow crashed: {text[:200]}", error=text[:200])


# -- manual: someone pressed stop ----------------------------------------------

def manual_stop() -> StopReason:
    return _reason("manual_stop", FAMILY_MANUAL, "Manual stop (Ctrl+C)")
