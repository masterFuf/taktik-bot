from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class FeedSelectors:
    """Selectors for the Instagram main feed."""
    
    # === Post containers in the feed ===
    post_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]'
    ])
    
    # === Post author username ===
    post_author_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]'
    ])
    
    # === Avatar de l'auteur ===
    post_author_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]'
    ])
    
    # === Sponsored-post markers — language-dependent (locales overlay) ===
    @property
    def sponsored_indicators(self) -> List[str]:
        return L("feed.sponsored_indicators")

    # === Reel markers in the feed — language-dependent (locales overlay) ===
    # NOTE: a bare contains() on "Reel" is too broad — it also matches the "Reels"
    # nav button, always present. clips_* resource-ids removed (0/30 on v417).
    @property
    def reel_indicators(self) -> List[str]:
        return L("feed.reel_indicators")

    # === Like counter in the feed — neutral base + locales overlay ===
    _likes_count_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_textview_likes"]',
    ])

    @property
    def likes_count_button(self) -> List[str]:
        return self._likes_count_button_base + L("feed.likes_count_button")

    # === Like button in the feed — neutral base + locales overlay ===
    _like_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[@resource-id="com.instagram.android:id/like_button"]',
    ])

    @property
    def like_button(self) -> List[str]:
        return self._like_button_base + L("feed.like_button")

    # === Already-liked detection — language-dependent (locales overlay) ===
    @property
    def already_liked_indicators(self) -> List[str]:
        return L("feed.already_liked_indicators")

    # === Comment button in the feed — neutral base + locales overlay ===
    _comment_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
    ])

    @property
    def comment_button(self) -> List[str]:
        return self._comment_button_base + L("feed.comment_button")

    # === Comment input field — neutral base + locales overlay ===
    _comment_input_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//android.widget.EditText',
    ])

    @property
    def comment_input(self) -> List[str]:
        return self._comment_input_base + L("feed.comment_input")

    # === Comment send button — neutral base + locales overlay ===
    _comment_send_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_post_button_click_area"]',
    ])

    @property
    def comment_send_button(self) -> List[str]:
        return self._comment_send_button_base + L("feed.comment_send_button")

FEED_SELECTORS = FeedSelectors()


@dataclass
class FeedSuggestionsSelectors:
    """The "Suggested for you" carousel inserted in the feed.

    Entry point of the suggestions-follow mode: the carousel appears after a few posts,
    with a "See all" CTA that opens the people discovery screen
    (cf. `DISCOVER_PEOPLE_SELECTORS`). Provenance : dump reel device, Instagram
    v410.0.0.53.71, 2026-07-26.

    Every marker below is a resource-id, so INDEPENDENT of the language: detecting the
    carousel and tapping the CTA need no label at all. The texts only serve observability.
    """

    # === The whole block ===
    carousel_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_container_view"]',
    ])
    carousel_header: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_header"]',
    ])
    carousel_title: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_title"]',
    ])

    # === "See all" CTA -> people discovery screen ===
    carousel_see_all: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_cta"]',
    ])

    # === Inline carousel cards (follow without leaving the feed) ===
    card_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/suggested_entity_card_container"]',
    ])
    card_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/suggested_entity_card_name"]',
    ])
    card_follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/suggested_user_card_follow_button"]',
    ])
    card_dismiss: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/dismiss_button"]',
    ])

    # --- Fast-path XML dump: BARE resource-ids (substring matches) ---
    carousel_container_id: str = "netego_carousel_container_view"
    carousel_title_id: str = "netego_carousel_title"
    carousel_cta_id: str = "netego_carousel_cta"
    card_container_id: str = "suggested_entity_card_container"
    card_name_id: str = "suggested_entity_card_name"
    card_follow_button_id: str = "suggested_user_card_follow_button"


FEED_SUGGESTIONS_SELECTORS = FeedSuggestionsSelectors()


@dataclass
class FeedScrollSelectors:
    """UI signatures of the feed smart scroll, read fast-path from the hierarchy dump
    anchor perception, caption and carousel reading, recovery). Centralized here, so no
    selector is hardcoded in the action itself.
    `internal docs`."""

    # --- Feed perception: leaf resource-ids read from the dump ---
    header_id: str = "row_feed_photo_profile_name"      # header / author (one per full-frame post)
    profile_header_id: str = "row_feed_profile_header"  # full header row; its content-desc carries
                                                        # "author a publié un(e) photo le <date>" —
                                                        # author + publish date for free, no gesture
    buttons_row_id: str = "row_feed_view_group_buttons" # like/comment/share/save row (post bottom edge)
    like_button_id: str = "row_feed_button_like"        # engagement bar = proof the post was fully seen
    action_bar_id: str = "main_feed_action_bar"         # top bar of the feed (only present at the top)
    tab_bar_id: str = "tab_bar"                         # bottom navigation bar
    secondary_label_id: str = "secondary_label"         # subtitle under a header
    clips_root_id: str = "root_clips_layout"            # fullscreen reels viewer
    feed_marker_ids: tuple = ("row_feed_photo_profile_name", "main_feed_action_bar",
                              "reels_tray_container", "tab_bar")
    video_ids: tuple = ("video_container", "clips_video_container", "clips_media_component")
    profile_ids: tuple = ("row_profile_header", "profile_header_follow_button",
                          "profile_viewpager", "profile_tabs_container")

    # --- Marqueurs de contenu non-organique (à skipper comme un humain) ---
    ad_desc_tokens: tuple = ("sponsoris", "sponsored")          # "Sponsorisée Photo de…" / "Reel sponsorisé…"
    suggested_desc_prefixes: tuple = ("suggestion", "suggested")  # media content-desc "Suggestion Photo de…"
    suggested_desc_contains: tuple = ("reels suggérés", "suggested reels")
    suggested_label_prefix: str = "suggest"                     # secondary_label "Suggestions"/"Suggested"

    # --- Recovery back to the feed (targeted action xpaths) ---
    back_button_xpath: str = ('//*[@content-desc="Retour" or @content-desc="Back"'
                              ' or @content-desc="Revenir en arrière"]')
    feed_tab_xpath: str = '//*[contains(@resource-id,"feed_tab")]'
    home_tab_xpath: str = '//*[@content-desc="Accueil" or @content-desc="Home"]'

    # --- Légende (v410 : IgTextLayoutView resource-id vide, extenseur = Button enfant content-desc exact) ---
    caption_layout_class: str = "com.instagram.ui.widget.textview.IgTextLayoutView"
    caption_expand_descs: tuple = ("plus", "more")             # EXACT content-desc of the expand button
    caption_expand_suffixes: tuple = (" plus", " more")        # end of a truncated text
    caption_collapse_suffixes: tuple = (" moins", " less")     # end of an EXPANDED text (collapse control)

    # --- Carousel inline ---
    carousel_viewpager_id: str = "carousel_viewpager"
    carousel_media_group_id: str = "carousel_media_group"
    carousel_index_id: str = "carousel_index_indicator_text_view"
    carousel_index_pattern: str = r"^(\d+)\s*/\s*(\d+)$"

    # --- Guard on the touch-down point of vertical gestures over a post card ---
    # The tokens are read from the short resource-id of the dump, which stays valid on
    # a clone. The gesture engine consumes their bounds, never a hardcoded coordinate.
    gesture_action_row_ids: tuple = ("row_feed_view_group_buttons",)
    gesture_action_id_tokens: tuple = (
        ("like", ("row_feed_button_like", "like_button")),
        ("comment", ("row_feed_button_comment", "comment_button")),
        ("share", ("row_feed_button_share", "row_feed_button_send", "direct_share_button")),
        ("save", ("row_feed_button_save", "save_button")),
    )
    gesture_post_marker_ids: tuple = (
        "row_feed_photo_profile_name",
        "row_feed_profile_header",
        "row_feed_view_group_buttons",
    )
    # Dump unavailable on a post view: a central media band expressed as screen ratios.
    # It avoids the like/comment/share cluster on the left and the save button on the right.
    gesture_fallback_safe_x_band: tuple = (0.46, 0.70)


FEED_SCROLL_SELECTORS = FeedScrollSelectors()
