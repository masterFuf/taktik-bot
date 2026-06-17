from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ...locales import L

@dataclass
class PostSelectors:
    """Sélecteurs pour les publications (posts et reels)."""
    
    # === Conteneurs de base ===
    post_container: str = '//androidx.recyclerview.widget.RecyclerView/android.widget.FrameLayout'
    post_image: str = '//android.widget.ImageView[contains(@resource-id, "image_view")]'
    post_video: str = '//android.widget.VideoView'
    all_button_nodes_selector: str = '//android.widget.Button'
    all_view_group_nodes_selector: str = '//android.view.ViewGroup'
    
    username: str = '//android.widget.TextView[contains(@resource-id, "row_feed_photo_profile_name")]'
    caption: str = '//android.widget.TextView[contains(@resource-id, "row_feed_comment_textview_comment")]'
    caption_layout_selector: str = '//com.instagram.ui.widget.textview.IgTextLayoutView'
    caption_layout_class_name: str = 'com.instagram.ui.widget.textview.IgTextLayoutView'
    caption_expand_labels: List[str] = field(default_factory=lambda: ["more", "plus"])
    caption_tail_pattern: str = r"\s+(more|plus|less|moins)\s*$"
    like_count: str = '//android.widget.TextView[contains(@resource-id, "row_feed_textview_likes")]'
    comment_count: str = '//android.widget.TextView[contains(@resource-id, "row_feed_textview_comment_count")]'
    text_view_class_name: str = "android.widget.TextView"
    button_class_name: str = "android.widget.Button"
    
    # === Éléments spéciaux ===
    carousel_indicator: str = '//androidx.viewpager.widget.ViewPager/following-sibling::*[1]'
    reels_player: str = '//android.view.ViewGroup[contains(@resource-id, "reel_player_container")]'
    first_post_grid: str = '//*[@resource-id="com.instagram.android:id/image_button"]'
    
    # === Extraction d'auteur (PostUrlBusiness) ===
    profile_image_selectors: List[str] = field(default_factory=lambda: [
        # Reel-specific selector (check first)
        '//*[@resource-id="com.instagram.android:id/clips_author_profile_pic"]',
        # Regular post selector
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]'
    ])
    
    header_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]'
    ])
    post_profile_header_resource_id: str = "com.instagram.android:id/row_feed_profile_header"
    post_author_name_resource_id: str = "com.instagram.android:id/row_feed_photo_profile_name"
    post_landing_indicator_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/row_feed_button_comment",
        "com.instagram.android:id/row_feed_button_like",
        "com.instagram.android:id/like_button",
    ])
    post_reel_landing_indicator_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/clips_single_media_component",
        "com.instagram.android:id/like_button",
    ])
    post_media_description_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/carousel_image",
        "com.instagram.android:id/row_feed_photo_imageview",
    ])
    post_date_pattern: str = (
        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4}$"
    )
    post_date_search_pattern: str = (
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4})"
    )
    author_from_media_description_pattern: str = r"by\s+([\w][\w.]{0,29})"
    
    _username_extraction_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/username"]',
        '//*[@resource-id="com.instagram.android:id/profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]',
        # Pour les reels
        '//*[@resource-id="com.instagram.android:id/clips_author_info"]//android.widget.TextView',
        # Sélecteurs génériques
        '//android.widget.TextView[starts-with(@text, "@")]',
    ])

    @property
    def username_extraction_selectors(self) -> List[str]:
        return self._username_extraction_selectors_base + L("post.username_extraction_selectors")
    
    # === Détection et extraction de likes ===
    _like_count_selectors_base: List[str] = field(default_factory=lambda: [
        # PRIORITY 1: Reel-specific selector (most specific, check first)
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        # PRIORITY 2: Regular post selectors
        # Sélecteur le plus fiable : TOUJOURS le premier Button avec texte (= likes)
        # Structure Instagram : ViewGroup[0]=J'aime, Button[1]=Likes, ViewGroup[2]=Commentaire, Button[3]=Nb commentaires, Button[4-6]=Partages
        '(//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]/android.widget.Button[@text])[1]',
        # Fallback : bouton juste après le conteneur du bouton J'aime
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]/*[@resource-id="com.instagram.android:id/row_feed_button_like"]/parent::*/following-sibling::android.widget.Button[@text][1]',
        # Autres fallbacks pour compatibilité
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]/android.widget.Button[@text and @clickable="true"][1]',
        '//*[@resource-id="com.instagram.android:id/row_feed_like_count_facepile"]',
    ])

    @property
    def like_count_selectors(self) -> List[str]:
        return self._like_count_selectors_base + L("post.like_count_selectors")
    
    button_like_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]//android.widget.Button[@text and @clickable="true"]',
        '//android.widget.Button[@clickable="true" and @text]',
        '//android.widget.Button[@clickable="true" and string-length(@text) > 0 and string-length(@text) < 10]'
    ])
    
    _photo_like_selectors_base: List[str] = field(default_factory=lambda: [
        # Ancien sélecteur générique en dernier recours
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]',
    ])

    @property
    def photo_like_selectors(self) -> List[str]:
        return self._photo_like_selectors_base + L("post.photo_like_selectors")
    
    # === Reels spécifiques ===
    _reel_like_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        '//*[@resource-id="com.instagram.android:id/likes_count"]',
        # Sélecteurs pour Reels en mode feed (bouton sans resource-id)
        '//android.widget.Button[@clickable="true" and string-length(@text) > 0 and string-length(@text) < 10]',
        '//android.widget.Button[contains(@text, ",")]',  # Ex: "1,561"
        '//android.widget.Button[contains(@text, "K")]',  # Ex: "15K"
        '//android.widget.Button[contains(@text, "M")]'   # Ex: "1.5M"
    ])

    @property
    def reel_like_selectors(self) -> List[str]:
        return self._reel_like_selectors_base + L("post.reel_like_selectors")
    
    # clips_* resource-ids supprimés 2026-03-07 (0/30 sur v417, voir SELECTOR_CLEANUP_BACKUP_2026-03-07.md)
    @property
    def reel_indicators(self) -> List[str]:
        return L("post.reel_indicators")
    
    # === Sélecteurs automation.py ===
    _automation_reel_specific_indicators_base: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[@text='Reel']",
        "//android.widget.TextView[contains(@text, 'reel')]",
        "//android.view.ViewGroup[@content-desc='Reel']",
    ])

    @property
    def automation_reel_specific_indicators(self) -> List[str]:
        return self._automation_reel_specific_indicators_base + L("post.automation_reel_specific_indicators")
    
    @property
    def video_controls(self) -> List[str]:
        return L("post.video_controls")
    
    @property
    def classic_post_indicators(self) -> List[str]:
        return L("post.classic_post_indicators")
    
    _post_elements_base: List[str] = field(default_factory=lambda: [
        # Combo bilingue (EN "like" + FR "J'aime") -> neutre, gardé pour toutes les
        # langues ; bytes d'origine conservés (échappement single-quote historique).
        "//android.widget.TextView[contains(@text, 'like') or contains(@text, 'J\\'aime')]",
    ])

    @property
    def post_elements(self) -> List[str]:
        return self._post_elements_base + L("post.post_elements")

    _automation_like_indicators_base: List[str] = field(default_factory=lambda: [
        "//android.widget.Button[contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9')]",
        "//android.widget.TextView[contains(@text, 'like') and (contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9'))]",
    ])

    @property
    def automation_like_indicators(self) -> List[str]:
        return self._automation_like_indicators_base + L("post.automation_like_indicators")
    
    _automation_like_count_selectors_base: List[str] = field(default_factory=lambda: [
        "//android.widget.Button[matches(@text, '^[0-9]+$')]",
        "//android.view.ViewGroup[@resource-id='com.instagram.android:id/row_feed_button_like']/parent::*/following-sibling::android.widget.Button",
        "//android.widget.TextView[@resource-id='com.instagram.android:id/row_feed_textview_likes']"
    ])

    @property
    def automation_like_count_selectors(self) -> List[str]:
        return self._automation_like_count_selectors_base + L("post.automation_like_count_selectors")
    
    heart_icon_selector: str = "//android.view.ViewGroup[@content-desc='Like'] | //android.view.ViewGroup[@resource-id='com.instagram.android:id/row_feed_button_like']"
    
    # === Sélecteurs like_business.py ===
    _like_button_advanced_selectors_base: List[str] = field(default_factory=lambda: [
        # ViewGroup cliquable qui contient le bouton like
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]/parent::*[@clickable="true"]',
        # Fallback sur le ViewGroup parent
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]/../..',
    ])

    @property
    def like_button_advanced_selectors(self) -> List[str]:
        # Sélecteurs génériques (localisés)
        return self._like_button_advanced_selectors_base + L("post.like_button_advanced_selectors")
    
    _post_view_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_share"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]',
    ])

    @property
    def post_view_indicators(self) -> List[str]:
        return self._post_view_indicators_base + L("post.post_view_indicators")

    ai_crop_header_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "row_feed_profile_header")]',
        '//*[contains(@resource-id, "row_feed_photo_profile_name")]',
        '//*[contains(@resource-id, "clips_author_info")]',
    ])

    ai_crop_button_row_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "row_feed_view_group_buttons")]',
        '//*[contains(@resource-id, "row_feed_button_like")]',
        '//*[contains(@resource-id, "row_feed_button_comment")]',
    ])
    
    @property
    def next_post_button_selectors(self) -> List[str]:
        return L("post.next_post_button_selectors")
    
    _back_button_selectors_base: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@resource-id="com.instagram.android:id/action_bar_button_back"]',
    ])

    @property
    def back_button_selectors(self) -> List[str]:
        return self._back_button_selectors_base + L("post.back_button_selectors")
    
    photo_imageview_selector: str = '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]'
    
    # === Post Metadata Extraction (for hashtag workflow) ===
    # Auteur du post (Reel view)
    _reel_author_username_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/clips_author_username"]',
        '//*[@resource-id="com.instagram.android:id/clips_author_info_component"]//android.widget.Button',
    ])

    @property
    def reel_author_username_selectors(self) -> List[str]:
        return self._reel_author_username_selectors_base + L("post.reel_author_username_selectors")
    
    # Caption du post (Reel view)
    # La caption est dans un ViewGroup imbriqué avec content-desc contenant le texte + hashtags
    # Note: La caption peut être rétractée (avec "…"), il faut cliquer dessus pour l'ouvrir
    reel_caption_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.widget.ScrollView//android.view.ViewGroup[@content-desc]',
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.view.ViewGroup[@content-desc and @clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//*[@content-desc]',
    ])
    
    # Date du post (Reel view) - visible quand la caption est ouverte
    # Format: "31 October 2025"
    reel_date_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.view.ViewGroup[@content-desc and contains(@content-desc, " ") and not(contains(@content-desc, "#"))]',
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.view.ViewGroup[@text]',
    ])
    
    # Auteur du post (Regular post view)
    post_author_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]',
    ])
    
    # Caption du post (Regular post view)
    post_caption_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_comment_textview_comment"]',
    ])
    
    # Likes count (for both views)
    post_likes_count_selectors: List[str] = field(default_factory=lambda: [
        # Reel view - content-desc contains "The like number is X"
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        # Regular post view
        '//*[@resource-id="com.instagram.android:id/row_feed_textview_likes"]',
    ])
    
    # Comments count (for both views)
    post_comments_count_selectors: List[str] = field(default_factory=lambda: [
        # Reel view - content-desc contains "Comment number isX"
        '//*[@resource-id="com.instagram.android:id/comment_count"]',
        # Regular post view
        '//*[@resource-id="com.instagram.android:id/row_feed_textview_comment_count"]',
    ])
    
    reel_indicators_like_business: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reel")]',
        '//*[contains(@content-desc, "reel")]',
        # clips_video_container & video_container supprimés 2026-03-07 (0/30 sur v417)
    ])
    
    like_count_button_selector: str = '//android.widget.Button[@text and string-length(@text) > 0]'
    
    # === Sélecteurs hashtag_business.py ===
    hashtag_post_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/image_button"]',
        '//*[@resource-id="com.instagram.android:id/layout_container" and @clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/image_preview"]'
    ])
    
    _reel_player_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Audio"]',
        '//*[@resource-id="com.instagram.android:id/clips_video_player"]'
    ])

    @property
    def reel_player_indicators(self) -> List[str]:
        return self._reel_player_indicators_base + L("post.reel_player_indicators")
    
    carousel_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/carousel_media_group"]',
        '//*[@resource-id="com.instagram.android:id/carousel_viewpager"]',
        '//*[@resource-id="com.instagram.android:id/carousel_video_media_group"]'
    ])
    
    _post_detail_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]',
    ])

    @property
    def post_detail_indicators(self) -> List[str]:
        return self._post_detail_indicators_base + L("post.post_detail_indicators")
    
    _like_button_indicators_base: List[str] = field(default_factory=lambda: [
        "//android.widget.Button[contains(@content-desc, 'J')]",  # "J'aime"
        "//android.widget.Button[contains(@content-desc, 'like')]",
        "//*[contains(@resource-id, 'row_feed_button_like')]"
    ])

    @property
    def like_button_indicators(self) -> List[str]:
        return self._like_button_indicators_base + L("post.like_button_indicators")
    
    _comment_button_indicators_base: List[str] = field(default_factory=lambda: [
        "//*[contains(@resource-id, 'row_feed_button_comment')]"
    ])

    @property
    def comment_button_indicators(self) -> List[str]:
        return self._comment_button_indicators_base + L("post.comment_button_indicators")
    
    # === Commentaires ===
    _photo_comment_selectors_base: List[str] = field(default_factory=lambda: [
        # Ancien sélecteur générique en dernier recours
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]'
    ])

    @property
    def photo_comment_selectors(self) -> List[str]:
        return self._photo_comment_selectors_base + L("post.photo_comment_selectors")
    
    _comment_button_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]/parent::*[@clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
    ])

    @property
    def comment_button_selectors(self) -> List[str]:
        return self._comment_button_selectors_base + L("post.comment_button_selectors")
    
    comment_field_selector: str = '//*[contains(@resource-id, "layout_comment_thread_edittext")]'
    _comment_field_selectors_base: List[str] = field(default_factory=lambda: [
        # IG v410's composer field is an AutoCompleteTextView with id
        # `layout_comment_thread_edittext_multiline` (not plain EditText, not the un-suffixed
        # id) and the hint "Rejoindre la conversation…" — so the old EditText/exact-id/hint
        # selectors all missed. The contains() on the thread-edittext id matches both the
        # base and the `_multiline` variant, any class. Keep it FIRST.
        '//*[contains(@resource-id, "layout_comment_thread_edittext")]',
        '//*[@resource-id="com.instagram.android:id/comment_box_text"]',
        '//*[@resource-id="com.instagram.android:id/inline_compose_box"]',
        '//*[contains(@resource-id, "comment_box")]',
        '//*[contains(@hint, "Rejoindre la conversation")]',
        '//*[contains(@hint, "Join the conversation")]',
        '//*[contains(@resource-id, "comment_edittext")]',
        '//android.widget.AutoCompleteTextView[contains(@resource-id, "comment")]',
        '//android.widget.EditText[contains(@resource-id, "comment")]',
        '//android.widget.AutoCompleteTextView[@focused="true"]',
        '//android.widget.EditText[@focused="true"]',
        '//android.widget.EditText[@clickable="true"]',
        '//android.widget.EditText',
    ])

    @property
    def comment_field_selectors(self) -> List[str]:
        return self._comment_field_selectors_base + L("post.comment_field_selectors")
    _post_comment_button_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_post_button_icon"]',
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_post_button_click_area"]',
        '//*[@text="Pubblicare" and @clickable="true"]',
    ])

    @property
    def post_comment_button_selectors(self) -> List[str]:
        return self._post_comment_button_selectors_base + L("post.post_comment_button_selectors")
    
    # === "Liked by" text selectors (for opening likers list from post view) ===
    _liked_by_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[starts-with(@text, "liked by")]',
    ])

    @property
    def liked_by_selectors(self) -> List[str]:
        return self._liked_by_selectors_base + L("post.liked_by_selectors")
    
    # === Comments list & username extraction ===
    comments_list_resource_id: str = 'com.instagram.android:id/sticky_header_list'
    
    comment_username_selectors: List[str] = field(default_factory=lambda: [
        # Username buttons have empty content-desc; action buttons (Reply, See translation, like counts)
        # always have content-desc matching their text — so @content-desc="" is the key discriminator.
        '//android.widget.Button[not(@resource-id) and @content-desc="" and @text!=""]',
        # Fallback scoped to the comments RecyclerView (handles clone APK parent IDs via contains)
        '//*[contains(@resource-id, "sticky_header_list")]//android.widget.Button[@content-desc="" and @text!=""]',
    ])
    
    _comments_view_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/sticky_header_list"]',
    ])

    @property
    def comments_view_indicators(self) -> List[str]:
        return self._comments_view_indicators_base + L("post.comments_view_indicators")
    
    comment_sort_button: str = '//*[@content-desc="For you"]'
    
    expand_replies_selector: str = '//*[contains(@content-desc, "View") and contains(@content-desc, "more repl")]'
    
    # === Autres éléments posts ===
    _video_player_selectors_base: List[str] = field(default_factory=lambda: [
        '//android.widget.VideoView',
        '//android.view.TextureView',
    ])

    @property
    def video_player_selectors(self) -> List[str]:
        return self._video_player_selectors_base + L("post.video_player_selectors")
    
    media_elements_selector: str = '//android.widget.ImageView | //android.widget.VideoView'
    
    _timestamp_selectors_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@content-desc, "min")]',
        '//android.widget.TextView[contains(@content-desc, "h")]',
        '//android.widget.TextView[contains(@content-desc, "week")]',
        '//android.widget.TextView[contains(@content-desc, "month")]',
        '//*[contains(@content-desc, "min")]'
    ])

    @property
    def timestamp_selectors(self) -> List[str]:
        return self._timestamp_selectors_base + L("post.timestamp_selectors")
    
    _save_button_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "row_feed_button_save")]'
    ])

    @property
    def save_button_selectors(self) -> List[str]:
        return self._save_button_selectors_base + L("post.save_button_selectors")
    
    # Share button (feed post & reel) — used to open the share sheet and retrieve the post URL.
    # Uses contains(@resource-id) so the selector remains valid for clone APKs whose
    # package name differs from com.instagram.android.
    share_button_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/row_feed_button_share",
        "com.instagram.android:id/row_feed_button_send",
    ])
    _share_button_selectors_base: List[str] = field(default_factory=lambda: [
        # Reels: clips/direct share button (resource-id ends in "direct_share_button")
        '//*[contains(@resource-id, "direct_share_button")]',
        # Regular feed posts: action-bar share button (resource-id ends in "row_feed_button_share")
        '//*[contains(@resource-id, "row_feed_button_share")]',
        '//*[@content-desc="Envoyer le post"]',
    ])

    @property
    def share_button_selectors(self) -> List[str]:
        # Content-desc fallbacks (FR + EN) via overlay
        return self._share_button_selectors_base + L("post.share_button_selectors")

    # "Copy link" action inside Instagram's share sheet (FR + EN) — via overlay
    @property
    def copy_link_labels(self) -> List[str]:
        return L("post.copy_link_labels")

    @property
    def copy_link_description_labels(self) -> List[str]:
        return L("post.copy_link_description_labels")
    copy_link_selectors: List[str] = field(default_factory=lambda: [
        '//*[@text="Copy link"]',
        '//*[@content-desc="Copy link"]',
        '//*[@text="Copier le lien"]',
        '//*[@content-desc="Copier le lien"]',
    ])

    # URL text element visible in the Android system share picker after tapping "Copy link"
    share_picker_url_selectors: List[str] = field(default_factory=lambda: [
        '//*[starts-with(@text, "https://www.instagram.com/p/")]',
        '//*[starts-with(@text, "https://www.instagram.com/reel/")]',
        '//*[starts-with(@text, "https://www.instagram.com/tv/")]',
    ])

    # Background dimmer that stays visible after the share sheet is dismissed.
    # Uses contains(@resource-id) for clone APK compatibility.
    share_sheet_dimmer: str = '//*[contains(@resource-id, "background_dimmer")]'

    # === Caption selectors ===
    caption_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_comment_text"]',
        '//*[contains(@resource-id, "caption")]'
    ])

    persona_caption_selectors: List[str] = field(default_factory=lambda: [
        '//com.instagram.ui.widget.textview.IgTextLayoutView',
        '//*[@resource-id="com.instagram.android:id/media_viewer_caption_text_view"]',
    ])
    
    # === Likes count selectors (for opening likers list) ===
    _likes_count_click_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "like_count")]'
    ])

    @property
    def likes_count_click_selectors(self) -> List[str]:
        return self._likes_count_click_selectors_base + L("post.likes_count_click_selectors")
    
    # === Send/Post button selectors ===
    @property
    def send_post_button_selectors(self) -> List[str]:
        return L("post.send_post_button_selectors")

POST_SELECTORS = PostSelectors()
