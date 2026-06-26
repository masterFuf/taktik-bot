from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class DetectionSelectors:
    """Sélecteurs pour la détection d'écrans, d'états et d'erreurs.

    Multi-langue (modele overlay) : les selecteurs langue-neutres (resource-id /
    classe / position) vivent ici comme champs ``_*_base`` ; les fragments
    dependants de la langue (@text / @content-desc / libelles) vivent dans
    ``ui/selectors/locales/<lang>.py`` et sont injectes via ``L("detection.<champ>")``
    selon la locale active (cf. ``ui/language.detect_and_optimize``). Les champs
    langue-dependants sont exposes en ``@property`` = base neutre + fragments de
    la locale active (base neutre d'abord, puis les fragments localises).
    """

    # === Détection d'écrans ===
    _home_screen_indicators_base: List[str] = field(default_factory=lambda: [
        # Neutral and resilient across mixed-language dumps (observed on IG 410:
        # FR app can still expose the bottom feed tab as content-desc="Home").
        '//*[@resource-id="com.instagram.android:id/feed_tab" and @selected="true"]',
        '//*[contains(@resource-id, "feed_timeline")]'
    ])

    @property
    def home_screen_indicators(self) -> List[str]:
        return self._home_screen_indicators_base + L("detection.home_screen_indicators")

    _search_screen_indicators_base: List[str] = field(default_factory=lambda: [
        # Search bar (when active)
        '//*[contains(@resource-id, "search_edit_text")]',
        # Explore page specific indicators
        '//*[@resource-id="com.instagram.android:id/clips_tab" and @selected="true"]',
        '//*[@resource-id="com.instagram.android:id/search_tab" and @selected="true"]',
    ])

    @property
    def search_screen_indicators(self) -> List[str]:
        return self._search_screen_indicators_base + L("detection.search_screen_indicators")

    _profile_screen_indicators_base: List[str] = field(default_factory=lambda: [
        # Keep profile detection scoped to the profile surface. Broad selectors
        # like row_feed_profile_header/action_bar_title/Follow also match feed posts.
        '//*[@resource-id="com.instagram.android:id/profile_header_container"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header"]',
        '//*[contains(@resource-id, "profile_header_full_name")]',
    ])

    @property
    def profile_screen_indicators(self) -> List[str]:
        return self._profile_screen_indicators_base + L("detection.profile_screen_indicators")

    profile_surface_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_container"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header"]',
        '//*[contains(@resource-id, "profile_header_full_name")]'
    ])

    @property
    def own_profile_indicators(self) -> List[str]:
        return L("detection.own_profile_indicators")

    story_viewer_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "reel_viewer_root")]',
        '//*[contains(@resource-id, "reel_viewer_text_container")]',
        '//*[contains(@resource-id, "reel_viewer")]',
        '//*[contains(@resource-id, "story_viewer")]'
    ])

    _post_screen_indicators_base: List[str] = field(default_factory=lambda: [
        # PRIORITY 2: Reel-specific selectors (if generic fails)
        '//*[@resource-id="com.instagram.android:id/like_button"]',  # Reel like button

        # PRIORITY 3: Regular post selectors (fallback for posts only)
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_share"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]'
        # clips_single_media_component supprimé 2026-03-07 (0/30 sur v417)
    ])

    @property
    def post_screen_indicators(self) -> List[str]:
        # PRIORITY 1: Generic content-desc selectors (Like / Comment) are
        # language-dependent and injected first via the overlay; the neutral
        # resource-id fallbacks follow.
        return L("detection.post_screen_indicators") + self._post_screen_indicators_base

    @property
    def reel_indicators(self) -> List[str]:
        # clips_* resource-ids supprimés 2026-03-07 (0/30 trouvés sur v417, voir SELECTOR_CLEANUP_BACKUP_2026-03-07.md)
        return L("detection.reel_indicators")

    # === Messages d'erreur ===
    @property
    def error_message_indicators(self) -> List[str]:
        return L("detection.error_message_indicators")

    @property
    def rate_limit_indicators(self) -> List[str]:
        return L("detection.rate_limit_indicators")

    @property
    def login_required_indicators(self) -> List[str]:
        return L("detection.login_required_indicators")

    # === Détection de popups ===
    popup_types: Dict[str, str] = field(default_factory=lambda: {
        "En commun": '//*[contains(@text, "En commun")]',
        "Mutual": '//*[contains(@text, "Mutual")]',
        "Notification": '//*[contains(@text, "Notification")]',
        "Permission": '//*[contains(@text, "Permission")]',
        "Update": '//*[contains(@text, "Mise à jour")]'
    })

    # === État du post (liked) ===
    # Quand un post est déjà liké, plusieurs indicateurs possibles selon version/langue:
    # - FR: content-desc = "J'aime déjà" ou "Ne plus aimer"
    # - EN: content-desc = "Unlike" ou "Liked"
    # - Universel: selected = "true" sur le bouton like
    _liked_button_indicators_base: List[str] = field(default_factory=lambda: [
        # === MÉTHODE 1: Attribut selected (le plus fiable, indépendant de la langue) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and @selected="true"]',
        # Reel / clips player: the like button keeps content-desc "J'aime" (U+2019)
        # whether liked or not — only @selected flips (dump real-device IG 410, 2026-06-11:
        # not-liked selected=false, liked selected=true). Without this the liked-state
        # detection (is_post_liked) never matched on a Reel, so the double-tap could not
        # be verified and the already-liked check was blind.
        '//*[@resource-id="com.instagram.android:id/like_button" and @selected="true"]',

        # Variants supprimés 2026-03-07 (redondants, voir SELECTOR_CLEANUP_BACKUP_2026-03-07.md)
    ])

    @property
    def liked_button_indicators(self) -> List[str]:
        # === MÉTHODE 2: Fallback content-desc multi-langue (overlay locales/) ===
        return self._liked_button_indicators_base + L("detection.liked_button_indicators")

    # === Navigation - Search bars ===
    _search_bar_selectors_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
        '//android.widget.EditText[@clickable="true"]'
    ])

    @property
    def search_bar_selectors(self) -> List[str]:
        return self._search_bar_selectors_base + L("detection.search_bar_selectors")

    _hashtag_search_bar_selectors_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
        '//android.widget.EditText[@clickable="true"]'
    ])

    @property
    def hashtag_search_bar_selectors(self) -> List[str]:
        return self._hashtag_search_bar_selectors_base + L("detection.hashtag_search_bar_selectors")

    @property
    def hashtag_page_indicators(self) -> List[str]:
        return L("detection.hashtag_page_indicators")

    # === Post errors (unavailable, private, not found) ===
    @property
    def post_error_indicators(self) -> List[str]:
        # Optimized: Most common error patterns first (faster detection).
        # Fragments langue-dependants (overlay locales/).
        #
        # Old approach (8 separate checks = 16s timeout if no error):
        # '//*[contains(@text, "Sorry")]',
        # '//*[contains(@text, "Désolé")]',
        # '//*[contains(@text, "not found")]',
        # '//*[contains(@text, "introuvable")]',
        # '//*[contains(@text, "unavailable")]',
        # '//*[contains(@text, "indisponible")]',
        # '//*[contains(@text, "private")]',
        # '//*[contains(@text, "privé")]'
        return L("detection.post_error_indicators")
    
    # === Followers/Following list ===
    # Sélecteurs SPÉCIFIQUES à la liste des followers/following
    # IMPORTANT: Les éléments comme follow_list_container existent AUSSI sur les profils privés
    # avec des suggestions. On doit utiliser des éléments VRAIMENT uniques.
    followers_list_indicators: List[str] = field(default_factory=lambda: [
        # PRIORITÉ 1: Tab layout avec onglets - N'EXISTE QUE sur la liste des followers, MAIS
        # défile hors écran dès qu'on scrolle → insuffisant seul pour une liste déjà scrollée.
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        # PRIORITÉ 2: lignes de followers — présentes même scrollé (fix du retour-back qui ratait
        # la liste scrollée et déclenchait une fausse "LOOP DETECTED", device 2026-06-26).
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        # Supprimés 2026-03-07: view_pager (0/15), mutual (0/15), followers (0/12) — voir SELECTOR_CLEANUP_BACKUP_2026-03-07.md
    ])
    
    follow_list_username_selectors: List[str] = field(default_factory=lambda: [
        # UNIQUEMENT les vrais followers, PAS les suggestions (row_recommended_user_username)
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        # Pour la popup des likers (bottom sheet)
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]'
    ])
    
    # Sélecteurs pour détecter la section suggestions (à éviter)
    _suggestions_section_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_recommended_user_username"]',
        '//*[@resource-id="com.instagram.android:id/row_recommended_user_follow_button"]',
    ])

    @property
    def suggestions_section_indicators(self) -> List[str]:
        # "Suggested for you" header in followers list (indicates end of real
        # followers) lives in the overlay alongside the other localized labels.
        return self._suggestions_section_indicators_base + L("detection.suggestions_section_indicators")

    # === Limited followers list detection (Meta Verified / Business accounts) ===
    # Instagram limits the number of followers shown for certain accounts
    @property
    def limited_followers_indicators(self) -> List[str]:
        return L("detection.limited_followers_indicators")

    # === End of followers list indicators ===
    # "And X others" message indicates there are more followers but they're hidden
    @property
    def followers_list_end_indicators(self) -> List[str]:
        return L("detection.followers_list_end_indicators")

    # Sélecteurs pour détecter le spinner de chargement Instagram
    _loading_spinner_indicators_base: List[str] = field(default_factory=lambda: [
        # Instagram's "Load more" button with loading animation
        '//*[@resource-id="com.instagram.android:id/row_load_more_button"]',
        # Generic progress indicators
        '//android.widget.ProgressBar',
        '//*[@class="android.widget.ProgressBar"]',
        '//*[contains(@resource-id, "progress")]'
    ])

    @property
    def loading_spinner_indicators(self) -> List[str]:
        # Loading indicator with content-desc (overlay locales/).
        return self._loading_spinner_indicators_base + L("detection.loading_spinner_indicators")
    
    # === Post grid visibility ===
    post_grid_visibility_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]',
        '//*[contains(@resource-id, "recycler_view")]'
    ])
    
    post_thumbnail_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/image_button"]',
        '//android.widget.ImageView[contains(@resource-id, "image")]'
    ])

    def post_grid_cell_by_position(self, row: int, col: int) -> str:
        """XPath for a SPECIFIC profile-grid thumbnail by absolute position.

        Grid cells carry their position in content-desc (real dumps IG v410,
        2026-06-09): e.g. "Reel par <author> à la ligne 2, colonne 2" or
        "7 photos de <author>, à la ligne 1, colonne 3". Matches the image_button
        bearing that position (FR or EN wording), so a caller can open post #N
        deterministically: row = (N-1)//3 + 1, col = (N-1)%3 + 1 (3-column grid)."""
        return (
            '//*[@resource-id="com.instagram.android:id/image_button" and '
            f'(contains(@content-desc, "ligne {row}, colonne {col}") or '
            f'contains(@content-desc, "row {row}, column {col}"))]'
        )
    
    # === Private account detection ===
    _private_account_indicators_base: List[str] = field(default_factory=lambda: [
        # New Instagram UI (2024+): private_profile_empty_state container
        '//*[@resource-id="com.instagram.android:id/private_profile_empty_state"]',
    ])

    @property
    def private_account_indicators(self) -> List[str]:
        # Localized variants (emphasized headline, legacy notice title, generic
        # text/content-desc fallbacks) live in the overlay (locales/).
        return self._private_account_indicators_base + L("detection.private_account_indicators")

    # === Verified account detection (Meta Verified / Blue badge) ===
    _verified_account_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/verified_badge"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title_verified_badge"]'
    ])

    @property
    def verified_account_indicators(self) -> List[str]:
        return self._verified_account_indicators_base + L("detection.verified_account_indicators")

    # === Business account detection ===
    _business_account_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_header_business_category")]',
    ])

    @property
    def business_account_indicators(self) -> List[str]:
        return self._business_account_indicators_base + L("detection.business_account_indicators")

    # === Load more / End of list ===
    @property
    def load_more_selectors(self) -> List[str]:
        # Consolidé 2026-03-07: 12 → 5 sélecteurs (//* couvre tous les types
        # d'éléments). Fragments langue-dependants (overlay locales/).
        return L("detection.load_more_selectors")

    # Consolidé 2026-03-07: 7 → 4 sélecteurs
    _end_of_list_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',
    ])

    @property
    def end_of_list_indicators(self) -> List[str]:
        return self._end_of_list_indicators_base + L("detection.end_of_list_indicators")

    # === Hashtag & Grid Navigation ===
    post_grid_selector: str = '//*[@resource-id="com.instagram.android:id/image_button"]'

    @property
    def recent_tab_selectors(self) -> List[str]:
        return L("detection.recent_tab_selectors")

    # === Likes count (to open likers list) ===
    _likes_count_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_like_count_facepile"]',
    ])

    @property
    def likes_count_selectors(self) -> List[str]:
        return self._likes_count_selectors_base + L("detection.likes_count_selectors")

    # === Post grid selectors (for clicking specific posts) ===
    post_grid_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@clickable="true"]',
        '//android.widget.FrameLayout//android.widget.ImageView',
        '//android.view.ViewGroup[@clickable="true"]//android.widget.ImageView',
        '//android.widget.ImageButton[@resource-id="com.instagram.android:id/image_button"]'
    ])

    # === Carousel selectors (for atomic extraction) ===
    _carousel_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "carousel_video_media_group")]',
        '//*[contains(@resource-id, "carousel_media_group")]',
    ])

    @property
    def carousel_selectors(self) -> List[str]:
        return self._carousel_selectors_base + L("detection.carousel_selectors")
    
    # === Reel like/comment count selectors ===
    reel_like_count_selector: str = '//*[@resource-id="com.instagram.android:id/like_count"]'
    reel_comment_count_selector: str = '//*[@resource-id="com.instagram.android:id/comment_count"]'
    
    # === Likers list username selectors ===
    likers_list_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/row_user_username"]',
        '//android.widget.TextView[contains(@text, "@")]'
    ])

DETECTION_SELECTORS = DetectionSelectors()
