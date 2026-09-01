"""Measure the TikTok catalogue against real screen captures.

Three questions, answered by the same walk over the same dumps:

    which fields SURVIVE a version bump           (43.1.4 -> 46.6.3)
    which fields the ENGLISH catalogue gets wrong (answering in FR, silent in EN)
    which silent fields are DEAD and which were never PHOTOGRAPHED

The last one is what makes the other two readable. A report saying "154 fields answer nowhere"
mixes a field that designates nothing -- dead code -- with a field whose screen was never
captured, which is a shopping list. Confusing them sends someone hunting a bug where there is only
a condition never met.

This module holds the decisions and no I/O: loading dumps, walking devices and printing belong to
the callers. That is what makes it testable without a phone, which matters because these rules
were WRONG twice before they were right -- once classing 52 fields as dead when 45 were waiting on
a popup that never appeared, once comparing profile fields against the profile MENU and reporting
six healthy fields as broken.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Dict, Iterable, List, Mapping, Sequence, Set

#: Surfaces our captures cover. A prefix absent from here has never been photographed.
SEEN_SURFACES: Set[str] = {
    "navigation", "video_state", "video_media", "video_engagement", "video_creator",
    "comment", "inbox", "conversation", "profile", "followers", "search", "settings",
    "logout", "popup", "scroll", "detection", "text_input", "feed",
}

#: Surfaces we know we have never visited -- the shopping list.
UNVISITED_SURFACES: Set[str] = {
    "signup", "country_picker", "auth", "publish_creation_entry", "publish_editor",
    "publish_caption", "publish_media_picker", "publish_progress", "publish_text",
    "publish_upload", "story",
}

#: Fields waiting on a STATE rather than a screen.
#:
#: A popup that never appeared is not a dead field, and neither is a story never opened, a video
#: already liked, an account set to private, a sticker never sent or a network error never hit.
#: Filing them as dead sends someone hunting a bug where there is only a condition never met;
#: leaving them among the suspects drowns the real ones.
#:
#: CURATED, and it reads as such: it comes from reading the names and the captures, not from an
#: inference this module could make. A field added here should be added knowingly.
STATE_DEPENDENT_FIELDS: Set[str] = {
    # A popup cannot be summoned; it appears or it does not.
    "popup.collections_close", "popup.collections_not_now", "popup.collections_popup",
    "popup.comment_input_area", "popup.comments_close_button", "popup.follow_friends_close",
    "popup.follow_friends_popup", "popup.promo_close_button", "popup.promo_banner",
    "popup.suggestion_close", "popup.suggestion_follow_back", "popup.suggestion_not_interested",
    "popup.age_verification_popup", "popup.link_email_not_now", "popup.notification_popup",
    "popup.notification_banner", "popup.system_deny_button", "popup.close_button",
    "popup.inbox_page_indicator", "popup.dismiss_button", "popup.promo_banner_anchors",
    "popup.gdpr_popup", "popup.gdpr_got_it_button", "popup.link_email_popup",
    "popup.system_dialog", "popup.suggestion_page_indicator",
    "popup.video_options_sheet", "popup.system_input_method_popup",
    # A story open in its viewer: a conditional surface, never visited.
    "profile.story_follow_button", "profile.story_message_input", "profile.story_timestamp",
    "profile.story_close_button", "profile.story_page_indicator",
    # A private account, a refused DM.
    "profile.private_indicator", "profile.privacy_blocked_message",
    "profile.unable_to_send_message", "followers.private_notice",
    # A video already liked, already favourited, an ad.
    "video_state.video_already_liked", "video_state.video_favorited_indicator",
    "video_state.video_liked_indicator", "video_state.unlike_indicator",
    "video_state.user_followed_indicator", "video_state.ad_label", "video_state.subscribe_button",
    # A sticker, a GIF, a group.
    "conversation.message_sticker", "conversation.message_gif", "conversation.sticker_suggestion",
    "conversation.games_button", "conversation.group_member_count", "inbox.group_member_count",
    # An error, an end of list, a spinner.
    "detection.error_message", "detection.network_error", "detection.rate_limit",
    "scroll.end_of_list", "scroll.loading_indicator",
    # An unread badge, a read receipt.
    "inbox.message_request_unread_badge", "inbox.seen_marker",
    # A new follower carrying the wave button, a reply in a thread.
    "inbox.say_hello_rows", "conversation.reply_button",
}

VERDICTS = ("alive", "state", "dead", "to_capture", "unclassified")


@dataclass(frozen=True)
class SurveyResult:
    """What the whole catalogue looks like against one corpus of captures."""

    alive: List[str] = dc_field(default_factory=list)
    state: List[str] = dc_field(default_factory=list)
    dead: List[str] = dc_field(default_factory=list)
    to_capture: List[str] = dc_field(default_factory=list)
    unclassified: List[str] = dc_field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(getattr(self, name)) for name in VERDICTS)


def surface_of(field_name: str) -> str:
    """The surface a field lives on, read off its own name (`inbox.unread_badge` -> `inbox`)."""
    return field_name.split(".", 1)[0]


def classify_field(field_name: str, answers_somewhere: bool) -> str:
    """One field's verdict.

    Order matters and is the whole point. A field that ANSWERS is alive whatever else is true of
    it -- no curated list can override a measurement. Only then does the state list get a say, and
    only then the surface.
    """
    if answers_somewhere:
        return "alive"
    if field_name in STATE_DEPENDENT_FIELDS:
        return "state"
    surface = surface_of(field_name)
    if surface in UNVISITED_SURFACES:
        return "to_capture"
    if surface in SEEN_SURFACES:
        return "dead"
    return "unclassified"


def survey(answers: Mapping[str, bool]) -> SurveyResult:
    """Classify every field of `answers` (field name -> did it resolve anywhere)."""
    buckets: Dict[str, List[str]] = {name: [] for name in VERDICTS}
    for field_name in sorted(answers):
        buckets[classify_field(field_name, answers[field_name])].append(field_name)
    return SurveyResult(**buckets)


@dataclass(frozen=True)
class DriftVerdict:
    """One field, seen from both versions."""

    field_name: str
    old_hits: int
    new_hits: int

    @property
    def verdict(self) -> str:
        if self.old_hits and self.new_hits:
            return "both"
        if self.old_hits:
            return "died_in_new"
        if self.new_hits:
            return "died_in_old"
        return "silent"


def drift(old_hits: Mapping[str, int], new_hits: Mapping[str, int]) -> List[DriftVerdict]:
    """Compare two per-version hit counts, field by field."""
    names = sorted(set(old_hits) | set(new_hits))
    return [DriftVerdict(name, old_hits.get(name, 0), new_hits.get(name, 0)) for name in names]


def survival_rate(verdicts: Sequence[DriftVerdict]) -> int:
    """Percentage of the fields that answered on the OLD version and still answer on the new one.

    Computed on that base and not on the whole catalogue: a field answering on neither version says
    nothing about the version bump, and counting it as a death would make an uncaptured screen look
    like a regression.
    """
    answered_before = [v for v in verdicts if v.old_hits]
    if not answered_before:
        return 100
    survived = sum(1 for v in answered_before if v.new_hits)
    return round(100 * survived / len(answered_before))


def english_suspects(
    french_answers: Mapping[str, bool],
    english_answers: Mapping[str, bool],
    families: Iterable[str],
) -> List[str]:
    """Fields that answer in FRENCH and read zero in ENGLISH on the same surface.

    `families` scopes the comparison to the field prefixes that actually live on the screen being
    compared. Without it the answer is noise: comparing `conversation.*` against a profile menu
    reported six healthy fields as broken, because the French capture happened to carry a control
    the English one did not.
    """
    prefixes = tuple(families)
    if not prefixes:
        return []
    return sorted(
        name for name, answered in french_answers.items()
        if answered and name.startswith(prefixes) and not english_answers.get(name, False)
    )


__all__ = [
    "SEEN_SURFACES", "UNVISITED_SURFACES", "STATE_DEPENDENT_FIELDS", "VERDICTS",
    "SurveyResult", "DriftVerdict",
    "surface_of", "classify_field", "survey", "drift", "survival_rate", "english_suspects",
]
