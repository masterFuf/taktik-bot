"""Selectors for the Instagram notifications / activity surface.

Provenance: real device dumps (FR + EN), Instagram modern "Notifications" UI.
The resource-ids are language-neutral and confirmed identical across locales;
visible TEXT / content-desc fragments live in the per-language overlays
(``locales/fr.py`` + ``locales/en.py``) and are pulled via ``L("notification.<key>")``.

History: the previous layout keyed everything on ``row_news_text`` /
``row_news_container``. Instagram migrated the activity screen to
``activity_feed_*`` ids; those are now the primary signatures and the old
``row_news_*`` ids are kept ONLY as fallbacks at the tail of each list.
"""
from typing import Dict, List
from dataclasses import dataclass, field

from ..locales import L, L_all


@dataclass
class NotificationSelectors:
    """Selectors for the notifications/activity screen and the follow-requests sub-screen."""

    # =========================================================================
    # ENTRY / SCREEN (main notifications screen)
    # =========================================================================

    # --- Activity / heart entry (top action bar of the feed) ---
    # Primary: the language-neutral resource-id of the heart entry; fallback:
    # any node whose content-desc contains the localized "Notifications" word.
    _activity_entry_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/notification"]',
    ])

    @property
    def activity_entry(self) -> List[str]:
        return self._activity_entry_base + L("notification.activity_entry")

    # Backwards-compatible alias for legacy callers expecting `activity_tab`.
    @property
    def activity_tab(self) -> List[str]:
        return self.activity_entry + L("notification.activity_tab")

    # --- Notifications screen signal (action_bar_title + list container) ---
    _notifications_screen_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/activity_feed_list"]',
    ])

    @property
    def notifications_screen_indicators(self) -> List[str]:
        return self._notifications_screen_base + L("notification.notifications_screen_indicators")

    # Legacy alias.
    @property
    def activity_screen_indicators(self) -> List[str]:
        return self.notifications_screen_indicators + L("notification.activity_screen_indicators")

    # --- A single notification row ---
    notification_row: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/activity_feed_newsfeed_story_row"]',
        # Legacy fallbacks (stale ids, kept only as a safety net):
        '//*[@resource-id="com.instagram.android:id/row_news_text"]',
        '//*[@resource-id="com.instagram.android:id/row_news_container"]',
    ])

    # BARE resource-ids (no package prefix) for raw-XML scanning, where matching
    # is done by SUBSTRING. IG renders activity-feed rows with a bare id and the
    # follow-requests rows fully-qualified; a bare substring matches BOTH forms,
    # so scan/parse code stays robust across screens and IG versions. Centralized
    # here so that code carries no hardcoded resource-id literal.
    notification_row_resource_id: str = "activity_feed_newsfeed_story_row"
    follow_request_row_resource_id: str = "follow_list_container"
    follow_request_username_resource_id: str = "follow_list_username"
    follow_request_accept_resource_id: str = "row_requested_user_accept_secondary"
    follow_request_ignore_resource_id: str = "row_requested_user_ignore"

    # Legacy alias.
    @property
    def notification_item(self) -> List[str]:
        return self.notification_row

    # --- Filter button (top action bar) ---
    _filter_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_button_action"]',
    ])

    @property
    def filter_button(self) -> List[str]:
        return self._filter_button_base + L("notification.filter_button")

    # =========================================================================
    # INLINE FAMILIES (inside an activity_feed_newsfeed_story_row, main screen)
    # =========================================================================

    # --- Follow-request inline phrase (row text) ---
    @property
    def inline_follow_request_text(self) -> List[str]:
        return L("notification.inline_follow_request_text")

    # --- Inline Confirm button on a follow-request story row ---
    _inline_confirm_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/igds_button"]',
    ])

    @property
    def inline_confirm_button(self) -> List[str]:
        return self._inline_confirm_button_base + L("notification.inline_confirm_button")

    # --- Inline dismiss (close) on a follow-request story row ---
    @property
    def inline_dismiss_button(self) -> List[str]:
        return L("notification.inline_dismiss_button")

    # --- Follow-requests GROUPED header row (opens the sub-screen) ---
    # The grouped digest row has an EMPTY resource-id, so it can only be matched by
    # TEXT — which means the match must be locale-agnostic: the row is in the DEVICE
    # language, independent of the locale the selector layer was optimized for. Hence
    # L_all (union FR+EN) and not L, so a scan on an English device still detects it.
    @property
    def follow_requests_header(self) -> List[str]:
        return L_all("notification.follow_requests_header")

    # Raw text fragments of the grouped digest row (NOT xpath) — to drop that row
    # from the classified feed. Union FR+EN so it works whatever the row language.
    @property
    def follow_requests_header_text(self) -> List[str]:
        return L_all("notification.follow_requests_digest")

    # Legacy alias.
    @property
    def follow_requests_section(self) -> List[str]:
        return self.follow_requests_header + L("notification.follow_requests_section")

    # --- Comment-mention row + Reply button ---
    @property
    def comment_mention_text(self) -> List[str]:
        return L("notification.comment_mention_text")

    @property
    def reply_button(self) -> List[str]:
        # Text-based affordance with no stable resource-id -> union FR+EN so a
        # reply works whatever the device language.
        return L_all("notification.reply_button")

    # --- Comment reply / like row text ---
    @property
    def comment_like_text(self) -> List[str]:
        return L("notification.comment_like_text")

    # --- Message row text ---
    @property
    def message_row_text(self) -> List[str]:
        return L("notification.message_row_text")

    # Generic notification action text (legacy keep-all).
    _notification_action_text_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]',
    ])

    @property
    def notification_action_text(self) -> List[str]:
        return self._notification_action_text_base + L("notification.notification_action_text")

    @property
    def notification_username(self) -> List[str]:
        return L("notification.notification_username")

    # =========================================================================
    # FOLLOW-REQUESTS SUB-SCREEN ("Contacts a decouvrir" / "Discover people")
    # =========================================================================

    # --- Sub-screen signal (action_bar_title + accept resource-id present) ---
    _follow_requests_screen_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/recycler_view"]',
        '//*[@resource-id="com.instagram.android:id/row_requested_user_accept_secondary"]',
    ])

    @property
    def follow_requests_screen_indicators(self) -> List[str]:
        return self._follow_requests_screen_base + L("notification.follow_requests_screen_indicators")

    # --- A request row + username ---
    request_row: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_container"]',
    ])

    request_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
    ])

    # --- Accept button (Confirmer / Confirm) ---
    _request_accept_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_requested_user_accept_secondary"]',
    ])

    @property
    def request_accept_button(self) -> List[str]:
        return self._request_accept_button_base + L("notification.request_accept_button")

    # --- Ignore button (Supprimer / Remove) ---
    _request_ignore_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_requested_user_ignore"]',
    ])

    @property
    def request_ignore_button(self) -> List[str]:
        return self._request_ignore_button_base + L("notification.request_ignore_button")

    # --- Section "See all" / "Voir tout" header ---
    _see_all_header_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_header_action"]',
    ])

    @property
    def see_all_header(self) -> List[str]:
        return self._see_all_header_base + L("notification.see_all_header")

    # =========================================================================
    # NOTIFICATION TYPE CLASSIFIER (plain text fragments, not XPath)
    # =========================================================================

    # Order = classification PRIORITY. The more specific comment_* phrases are
    # checked before the bare post_comment / post_like ones so a "replied to
    # your comment" row is never mis-stolen by a "commented"/"liked" substring.
    _classifier_types_in_priority: List[str] = field(default_factory=lambda: [
        "comment_mention",
        "comment_reply",
        "comment_like",
        "post_comment",
        "post_like",
        "new_follower",
        "follow_request",
        "message",
        "shared",
    ])

    @property
    def classifier_fragments(self) -> "Dict[str, List[str]]":
        """Per-type localized text fragments for classifying an activity-feed row.

        Returns an ordered dict ``type -> [fragment, ...]`` where each fragment
        list is the UNION of FR + EN strings (via ``L_all``), so a row can be
        classified regardless of the device language: a notification line may be
        in any locale, independently of the locale the selector layer was
        optimized for. Dict insertion order is the classification PRIORITY order
        (more specific comment_* before bare post_comment / post_like). The
        ``"other"`` fallback is intentionally NOT included — the caller treats an
        unmatched row as ``other``.
        """
        return {
            type_name: L_all(f"notification.type_{type_name}")
            for type_name in self._classifier_types_in_priority
        }


NOTIFICATION_SELECTORS = NotificationSelectors()
