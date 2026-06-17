from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class FeedSelectors:
    """Sélecteurs pour le feed principal Instagram."""
    
    # === Conteneurs de posts dans le feed ===
    post_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]'
    ])
    
    # === Username de l'auteur du post ===
    post_author_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]'
    ])
    
    # === Avatar de l'auteur ===
    post_author_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]'
    ])
    
    # === Indicateurs de post sponsorisé — langue-dependants (overlay locales/) ===
    @property
    def sponsored_indicators(self) -> List[str]:
        return L("feed.sponsored_indicators")

    # === Indicateurs de Reel dans le feed — langue-dependants (overlay locales/) ===
    # NOTE: "//*[contains(@content-desc, "Reel")]" trop large — matche le bouton nav "Reels" (toujours présent)
    # clips_* resource-ids supprimés 2026-03-07 (0/30 sur v417, voir SELECTOR_CLEANUP_BACKUP_2026-03-07.md)
    @property
    def reel_indicators(self) -> List[str]:
        return L("feed.reel_indicators")

    # === Compteur de likes dans le feed — base neutre + overlay locales/ ===
    _likes_count_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_textview_likes"]',
    ])

    @property
    def likes_count_button(self) -> List[str]:
        return self._likes_count_button_base + L("feed.likes_count_button")

    # === Bouton like dans le feed — base neutre + overlay locales/ ===
    _like_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[@resource-id="com.instagram.android:id/like_button"]',
    ])

    @property
    def like_button(self) -> List[str]:
        return self._like_button_base + L("feed.like_button")

    # === Détection post déjà liké — langue-dependants (overlay locales/) ===
    @property
    def already_liked_indicators(self) -> List[str]:
        return L("feed.already_liked_indicators")

    # === Bouton commentaire dans le feed — base neutre + overlay locales/ ===
    _comment_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
    ])

    @property
    def comment_button(self) -> List[str]:
        return self._comment_button_base + L("feed.comment_button")

    # === Champ de saisie commentaire — base neutre + overlay locales/ ===
    _comment_input_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//android.widget.EditText',
    ])

    @property
    def comment_input(self) -> List[str]:
        return self._comment_input_base + L("feed.comment_input")

    # === Bouton envoyer commentaire — base neutre + overlay locales/ ===
    _comment_send_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_post_button_click_area"]',
    ])

    @property
    def comment_send_button(self) -> List[str]:
        return self._comment_send_button_base + L("feed.comment_send_button")

FEED_SELECTORS = FeedSelectors()


@dataclass
class FeedScrollSelectors:
    """Signatures UI du SCROLL INTELLIGENT du feed, lues en fast-path sur le hierarchy dump
    (perception des ancres, lecture légende/carousel, récupération). Centralisées ici (regle
    AGENTS : pas de selector en dur dans l'action). Issues de dumps réels Instagram v410 — voir
    `taktik-docs/bot/security/feed-scroll-engineering.md`."""

    # --- Perception du feed : leaf resource-ids lus dans le dump ---
    header_id: str = "row_feed_photo_profile_name"      # header/auteur (1 par post plein-cadre)
    like_button_id: str = "row_feed_button_like"        # barre d'engagement = preuve "post vu en entier"
    action_bar_id: str = "main_feed_action_bar"         # barre du haut du feed (présente seulement en haut)
    tab_bar_id: str = "tab_bar"                         # barre de navigation du bas
    secondary_label_id: str = "secondary_label"         # sous-titre ("Suggestions") sous un header
    clips_root_id: str = "root_clips_layout"            # viewer Reels plein écran
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

    # --- Récupération vers le feed (xpaths d'action ciblés) ---
    back_button_xpath: str = ('//*[@content-desc="Retour" or @content-desc="Back"'
                              ' or @content-desc="Revenir en arrière"]')
    feed_tab_xpath: str = '//*[contains(@resource-id,"feed_tab")]'
    home_tab_xpath: str = '//*[@content-desc="Accueil" or @content-desc="Home"]'

    # --- Légende (v410 : IgTextLayoutView resource-id vide, extenseur = Button enfant content-desc exact) ---
    caption_layout_class: str = "com.instagram.ui.widget.textview.IgTextLayoutView"
    caption_expand_descs: tuple = ("plus", "more")             # content-desc EXACT du bouton "dérouler"
    caption_expand_suffixes: tuple = (" plus", " more")        # fin d'un texte tronqué

    # --- Carousel inline ---
    carousel_viewpager_id: str = "carousel_viewpager"
    carousel_media_group_id: str = "carousel_media_group"
    carousel_index_id: str = "carousel_index_indicator_text_view"
    carousel_index_pattern: str = r"^(\d+)\s*/\s*(\d+)$"


FEED_SCROLL_SELECTORS = FeedScrollSelectors()
