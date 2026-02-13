from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class DetectionSelectors:
    """Sélecteurs pour la détection d'écrans, d'états et d'erreurs."""
    
    # === Détection d'écrans ===
    home_screen_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Accueil") and @selected="true"]',
        '//*[contains(@content-desc, "Home") and @selected="true"]',
        '//*[contains(@resource-id, "feed_timeline")]'
    ])
    
    search_screen_indicators: List[str] = field(default_factory=lambda: [
        # Tab selected indicators
        '//*[contains(@content-desc, "Rechercher") and @selected="true"]',
        '//*[contains(@content-desc, "Search") and @selected="true"]',
        # Search bar (when active)
        '//*[contains(@resource-id, "search_edit_text")]',
        # Explore page specific indicators
        '//*[contains(@resource-id, "com.instagram.android:id/clips_tab")]',
        '//*[contains(@resource-id, "com.instagram.android:id/search_tab")]',
        # Search bar on Explore page (clickable text "Search" or "Rechercher")
        '//android.widget.TextView[@package="com.instagram.android" and (contains(@text, "Search") or contains(@text, "Rechercher"))]'
    ])
    
    profile_screen_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_header")]',
        '//*[contains(@resource-id, "coordinator_root_layout")]',
        '//*[contains(@resource-id, "action_bar_title")]',
        '//*[contains(@resource-id, "profile_header_full_name")]',
        '//*[@content-desc="Modifier le profil"]',
        '//*[contains(@text, "Modifier le profil")]',
        '//*[@content-desc="Edit profile"]',
        '//*[contains(@text, "Edit profile")]',
        '//*[contains(@text, "Follow")]',
        '//*[contains(@text, "Suivre")]',
        '//*[contains(@text, "Following")]',
        '//*[contains(@text, "Abonné")]'
    ])
    
    own_profile_indicators: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Modifier le profil"]',
        '//*[contains(@text, "Modifier le profil")]',
        '//*[@content-desc="Edit profile"]',
        '//*[contains(@text, "Edit profile")]',
        '//*[contains(@text, "Partager le profil")]',
        '//*[contains(@text, "Share profile")]',
        '//*[@resource-id="com.instagram.android:id/button_container" and @content-desc="Modifier le profil"]'
    ])
    
    story_viewer_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "reel_viewer")]',
        '//*[contains(@resource-id, "story_viewer")]'
    ])
    
    post_screen_indicators: List[str] = field(default_factory=lambda: [
        # PRIORITY 1: Generic selectors (work for BOTH Reels and Posts) - CHECK FIRST
        '//*[contains(@content-desc, "Like")]',  # Works for both! Fast detection
        '//*[contains(@content-desc, "Comment")]',  # Works for both! Fast detection
        
        # PRIORITY 2: Reel-specific selectors (if generic fails)
        '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]',
        '//*[@resource-id="com.instagram.android:id/like_button"]',  # Reel like button
        
        # PRIORITY 3: Regular post selectors (fallback for posts only)
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_share"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]'
    ])
    
    reel_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reel de")]',
        '//*[contains(@content-desc, "Reel by")]',
        '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]',
        '//*[@resource-id="com.instagram.android:id/clips_viewer_video_layout"]',
        '//*[@resource-id="com.instagram.android:id/clips_video_container"]',
        '//*[@resource-id="com.instagram.android:id/clips_video_player"]'
    ])
    
    # === Détection de contenu ===
    story_ring_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "story_ring")]',
        '//*[contains(@content-desc, "Story")]',
        '//*[contains(@resource-id, "reel_ring")]'
    ])
    
    # === Messages d'erreur ===
    error_message_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Erreur")]',
        '//*[contains(@text, "Error")]',
        '//*[contains(@text, "Impossible")]',
        '//*[contains(@text, "Failed")]',
        '//*[contains(@text, "Échec")]',
        '//*[contains(@text, "Retry")]',
        '//*[contains(@text, "Réessayer")]'
    ])
    
    rate_limit_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Trop de tentatives")]',
        '//*[contains(@text, "Too many requests")]',
        '//*[contains(@text, "Veuillez patienter")]',
        '//*[contains(@text, "Please wait")]',
        '//*[contains(@text, "Action bloquée")]',
        '//*[contains(@text, "Action blocked")]'
    ])
    
    login_required_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Se connecter")]',
        '//*[contains(@text, "Log in")]',
        '//*[contains(@text, "Connexion")]',
        '//*[contains(@text, "Login")]'
    ])
    
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
    liked_button_indicators: List[str] = field(default_factory=lambda: [
        # === MÉTHODE 1: Attribut selected (le plus fiable, indépendant de la langue) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and @selected="true"]',
        
        # === MÉTHODE 2: Français (FR) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "déjà")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Ne plus aimer")]',
        '//*[contains(@content-desc, "J\'aime déjà")]',
        '//*[contains(@content-desc, "Ne plus aimer")]',
        
        # === MÉTHODE 3: Anglais (EN) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Unlike")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Liked")]',
        '//*[contains(@content-desc, "Unlike")]',
        
        # === MÉTHODE 4: Fallback générique (anciennes versions) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"][@selected="true"]'
    ])
    
    # === Navigation - Search bars ===
    search_bar_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
        '//android.widget.EditText[contains(@text, "Rechercher")]',
        '//android.widget.EditText[contains(@text, "Search")]',
        '//android.widget.EditText[@clickable="true"]'
    ])
    
    hashtag_search_bar_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
        '//android.widget.EditText[contains(@text, "Rechercher")]',
        '//android.widget.EditText[contains(@text, "Search")]',
        '//android.widget.EditText[@clickable="true"]'
    ])
    
    hashtag_page_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "publications")]',
        '//*[contains(@text, "posts")]',
        '//*[contains(@text, "Recent")]',
        '//*[contains(@text, "Top")]'
    ])
    
    # === Post errors (unavailable, private, not found) ===
    post_error_indicators: List[str] = field(default_factory=lambda: [
        # Optimized: Most common error patterns first (faster detection)
        '//*[contains(@text, "Sorry") or contains(@text, "Désolé")]',
        '//*[contains(@text, "not found") or contains(@text, "introuvable")]',
        '//*[contains(@text, "unavailable") or contains(@text, "indisponible")]',
        '//*[contains(@text, "private") or contains(@text, "privé")]'
        
        # Old approach (8 separate checks = 16s timeout if no error):
        # '//*[contains(@text, "Sorry")]',
        # '//*[contains(@text, "Désolé")]',
        # '//*[contains(@text, "not found")]',
        # '//*[contains(@text, "introuvable")]',
        # '//*[contains(@text, "unavailable")]',
        # '//*[contains(@text, "indisponible")]',
        # '//*[contains(@text, "private")]',
        # '//*[contains(@text, "privé")]'
    ])
    
    # === Followers/Following list ===
    # Sélecteurs SPÉCIFIQUES à la liste des followers/following
    # IMPORTANT: Les éléments comme follow_list_container existent AUSSI sur les profils privés
    # avec des suggestions. On doit utiliser des éléments VRAIMENT uniques.
    followers_list_indicators: List[str] = field(default_factory=lambda: [
        # PRIORITÉ 1: Tab layout avec onglets - N'EXISTE QUE sur la liste des followers
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        # PRIORITÉ 2: View pager de la liste - N'EXISTE QUE sur la liste des followers
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_view_pager"]',
        # PRIORITÉ 3: Onglet "mutual" - N'EXISTE QUE sur la liste des followers
        '//android.widget.Button[contains(@text, "mutual")]',
        # PRIORITÉ 4: Onglet avec nombre + "followers" (ex: "52.5K followers")
        '//android.widget.Button[contains(@text, "followers")]',
    ])
    
    follow_list_username_selectors: List[str] = field(default_factory=lambda: [
        # UNIQUEMENT les vrais followers, PAS les suggestions (row_recommended_user_username)
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        # Pour la popup des likers (bottom sheet)
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]'
    ])
    
    # Sélecteurs pour détecter la section suggestions (à éviter)
    suggestions_section_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_recommended_user_username"]',
        '//*[contains(@text, "Voir toutes les suggestions")]',
        '//*[contains(@text, "See all suggestions")]',
        '//*[contains(@text, "Suggestions pour vous")]',
        '//*[contains(@text, "Suggestions for you")]',
        '//*[@resource-id="com.instagram.android:id/row_recommended_user_follow_button"]',
        # "Suggested for you" header in followers list (indicates end of real followers)
        '//*[@resource-id="com.instagram.android:id/row_header_textview" and contains(@text, "Suggested for you")]',
        '//*[@resource-id="com.instagram.android:id/row_header_textview" and contains(@text, "Suggestions pour vous")]'
    ])
    
    # === Limited followers list detection (Meta Verified / Business accounts) ===
    # Instagram limits the number of followers shown for certain accounts
    limited_followers_indicators: List[str] = field(default_factory=lambda: [
        # English message
        '//*[@resource-id="com.instagram.android:id/row_text_textview" and contains(@text, "We limit the number of followers")]',
        '//*[contains(@text, "We limit the number of followers shown")]',
        # French message
        '//*[contains(@text, "Nous limitons le nombre")]',
        '//*[contains(@text, "nombre de followers affiché")]'
    ])
    
    # === End of followers list indicators ===
    # "And X others" message indicates there are more followers but they're hidden
    followers_list_end_indicators: List[str] = field(default_factory=lambda: [
        # "And 12.1K others" pattern (English)
        '//*[@resource-id="com.instagram.android:id/row_text_textview" and contains(@text, "And ") and contains(@text, " others")]',
        # "Et X autres" pattern (French)
        '//*[@resource-id="com.instagram.android:id/row_text_textview" and contains(@text, "Et ") and contains(@text, " autres")]',
        # Generic pattern
        '//*[contains(@text, " others") and @resource-id="com.instagram.android:id/row_text_textview"]'
    ])
    
    # Sélecteurs pour détecter le spinner de chargement Instagram
    loading_spinner_indicators: List[str] = field(default_factory=lambda: [
        # Instagram's "Load more" button with loading animation
        '//*[@resource-id="com.instagram.android:id/row_load_more_button"]',
        # Loading indicator with content-desc
        '//*[contains(@content-desc, "Loading")]',
        '//*[contains(@content-desc, "Chargement")]',
        # Generic progress indicators
        '//android.widget.ProgressBar',
        '//*[@class="android.widget.ProgressBar"]',
        '//*[contains(@resource-id, "progress")]'
    ])
    
    # === Post grid visibility ===
    post_grid_visibility_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]',
        '//*[contains(@resource-id, "recycler_view")]'
    ])
    
    post_thumbnail_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/image_button"]',
        '//android.widget.ImageView[contains(@resource-id, "image")]'
    ])
    
    # === Private account detection ===
    private_account_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_profile_header_empty_profile_notice_title" and @text="This account is private"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_empty_profile_notice_title" and @text="Ce compte est privé"]',
        '//*[contains(@text, "This account is private")]',
        '//*[contains(@text, "Ce compte est privé")]',
        '//*[contains(@content-desc, "This account is private")]',
        '//*[contains(@content-desc, "Ce compte est privé")]'
    ])
    
    # === Verified account detection (Meta Verified / Blue badge) ===
    verified_account_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Verified")]',
        '//*[contains(@content-desc, "Vérifié")]',
        '//*[@resource-id="com.instagram.android:id/verified_badge"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title_verified_badge"]'
    ])
    
    # === Business account detection ===
    business_account_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_header_business_category")]',
        '//*[contains(@text, "Professional")]',
        '//*[contains(@text, "Professionnel")]'
    ])
    
    # === Load more / End of list ===
    load_more_selectors: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[contains(@text, 'Voir plus')]",
        "//android.widget.Button[contains(@text, 'Voir plus')]",
        "//*[contains(@content-desc, 'Voir plus')]",
        "//android.widget.TextView[contains(@text, 'voir plus')]",
        "//android.widget.TextView[contains(@text, 'See more')]",
        "//android.widget.Button[contains(@text, 'See more')]",
        "//*[contains(@content-desc, 'See more')]",
        "//android.widget.TextView[contains(@text, 'see more')]",
        '//*[@text="Load more" or @text="Show more" or @text="See more"]',
        '//*[contains(@text, "Load") and contains(@text, "more")]',
        '//*[@content-desc="Load more" or @content-desc="Show more"]',
        '//android.widget.Button[contains(@text, "more")]'
    ])
    
    end_of_list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',  # Bouton "See all suggestions" = fin de liste followers
        '//*[@text="See all suggestions"]',
        '//*[contains(@text, "See all suggestions")]',
        '//*[@text="You\'re all caught up" or @text="No more suggestions"]',
        '//*[contains(@text, "caught up") or contains(@text, "End of list")]',
        '//*[contains(@text, "No more") or contains(@text, "That\'s all")]',
        '//*[contains(@text, "Aucun autre") or contains(@text, "Fin de")]'
    ])
    
    # === Hashtag & Grid Navigation ===
    post_grid_selector: str = '//*[@resource-id="com.instagram.android:id/image_button"]'
    
    recent_tab_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Recent"]',
        '//android.widget.TextView[@text="Récent"]',
        '//*[contains(@text, "Recent")]',
        '//*[contains(@text, "Récent")]',
        '//android.widget.TextView[contains(@content-desc, "Recent")]'
    ])
    
    # === Likes count (to open likers list) ===
    likes_count_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        '//*[contains(@content-desc, "Nombre de J\'aime")]',
        '//*[contains(@content-desc, "likes")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_like_count_facepile"]',
        '//android.widget.TextView[contains(@text, "J\'aime")]',
        '//android.widget.TextView[contains(@text, "likes")]'
    ])
    
    # === Post grid selectors (for clicking specific posts) ===
    post_grid_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@clickable="true"]',
        '//android.widget.FrameLayout//android.widget.ImageView',
        '//android.view.ViewGroup[@clickable="true"]//android.widget.ImageView',
        '//android.widget.ImageButton[@resource-id="com.instagram.android:id/image_button"]'
    ])
    
    # === Carousel selectors (for atomic extraction) ===
    carousel_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "carousel_video_media_group")]',
        '//*[contains(@resource-id, "carousel_media_group")]',
        '//*[contains(@content-desc, "likes") and contains(@content-desc, "comment")]'
    ])
    
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
