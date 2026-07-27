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
class FeedSuggestionsSelectors:
    """Carousel "Suggested for you" (netego) insere dans le feed.

    Point d'entree du mode "follow des suggestions" : le carousel apparait apres
    quelques posts, avec un CTA "See all" qui ouvre l'ecran Discover people
    (cf. `DISCOVER_PEOPLE_SELECTORS`). Provenance : dump reel 9CHAY1PN, Instagram
    v410.0.0.53.71, 2026-07-26.

    Tous les marqueurs ci-dessous sont des resource-id, donc INDEPENDANTS de la
    langue : la detection du carousel et le tap du CTA n'ont besoin d'aucun
    libelle. Les textes ne servent qu'a l'observabilite (titre affiche).
    """

    # === Le bloc entier ===
    carousel_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_container_view"]',
    ])
    carousel_header: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_header"]',
    ])
    carousel_title: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_title"]',
    ])

    # === CTA "See all" / "Tout afficher" -> ecran Discover people ===
    carousel_see_all: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/netego_carousel_cta"]',
    ])

    # === Cartes inline du carousel (follow sans quitter le feed) ===
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

    # --- Fast-path dump XML : resource-id NUS (matches par sous-chaine) ---
    carousel_container_id: str = "netego_carousel_container_view"
    carousel_title_id: str = "netego_carousel_title"
    carousel_cta_id: str = "netego_carousel_cta"
    card_container_id: str = "suggested_entity_card_container"
    card_name_id: str = "suggested_entity_card_name"
    card_follow_button_id: str = "suggested_user_card_follow_button"


FEED_SUGGESTIONS_SELECTORS = FeedSuggestionsSelectors()


@dataclass
class FeedScrollSelectors:
    """Signatures UI du SCROLL INTELLIGENT du feed, lues en fast-path sur le hierarchy dump
    (perception des ancres, lecture légende/carousel, récupération). Centralisées ici (regle
    AGENTS : pas de selector en dur dans l'action). Issues de dumps réels Instagram v410 — voir
    `internal docs`."""

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

    # --- Garde du point d'appui des gestes verticaux sur une carte de post ---
    # Les tokens sont lus sur le resource-id court du dump (clone-safe). Le moteur de gestes
    # consomme leurs bounds, jamais des coordonnees Instagram codees en dur.
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
    # Dump indisponible sur une vue post : bande media centrale, exprimee en ratios d'ecran.
    # Elle evite le cluster like/comment/share a gauche et le bouton save a droite.
    gesture_fallback_safe_x_band: tuple = (0.46, 0.70)


FEED_SCROLL_SELECTORS = FeedScrollSelectors()
