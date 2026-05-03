"""Threads UI layer: package constants and selectors.

Selectors captured from real UI dumps (Threads Android, com.instagram.barcelona).
When a new screen needs to be automated, capture a fresh dump via the Electron
debug panel and extend this module instead of hard-coding selectors inside
workflows.
"""

THREADS_PACKAGE = "com.instagram.barcelona"
THREADS_MAIN_ACTIVITY = "com.instagram.barcelona.mainactivity.BarcelonaMainActivity"


# ──────────────────────────────────────────────────────────────────────────────
# Bottom navigation tabs (captured from ui_dump 2026-04-23 — 5 tabs, NO search)
# ──────────────────────────────────────────────────────────────────────────────
# Note: recent Threads builds do NOT expose a Search tab in the bottom bar.
# Search is accessed via a loupe icon at the TOP-RIGHT of the MainFeedScreen
# header (no resource-id, no content-desc — positional tap only).
TAB_MAIN_FEED = "barcelona_tab_main_feed"
TAB_MESSAGING = "barcelona_tab_messaging"  # 2nd tab (not Search!)
TAB_CREATE = "barcelona_tab_create"
TAB_ACTIVITY = "barcelona_tab_activity_feed"
TAB_PROFILE = "barcelona_tab_profile"
TABS_BOTTOM_BAR = "tabs_bottom_bar"
# DEPRECATED: kept for backwards compat with older builds. Always prefer the
# top-right loupe on the main feed (see workflows._open_search_screen).
TAB_SEARCH = "barcelona_tab_search"

# Top-right search loupe button on MainFeedScreen. No resource-id / no desc.
# Relative coordinates (fraction of screen width/height) of the button centre.
# Captured @ 576×1280: bounds=[498,49][570,121] → centre (534, 85).
FEED_SEARCH_LOUPE_FRACTION = (0.927, 0.066)


# ──────────────────────────────────────────────────────────────────────────────
# Main feed
# ──────────────────────────────────────────────────────────────────────────────
MAIN_FEED_SCREEN = "MainFeedScreen"
MAIN_FEED_MENU_BUTTON = "main_feed_menu_button"
FEED_POST_ROW = "FeedPostRow"
FEED_POST_HEADER = "feed_post_header"
FEED_POST_TEXT = "feed_post_text"
FEED_POST_LIKE = "feed_post_ufi_like_button"
FEED_POST_REPLY = "feed_post_ufi_reply_button"
FEED_POST_REPOST = "feed_post_ufi_repost_button"
FEED_POST_SHARE = "feed_post_ufi_share_button"


# ──────────────────────────────────────────────────────────────────────────────
# Search screen — TODO: capture via debug panel once opened
# ──────────────────────────────────────────────────────────────────────────────
# Fallbacks until we dump the search screen. Workflows must handle absence.
SEARCH_INPUT_HINT_TEXTS = ("Search", "Rechercher", "Cerca", "Buscar")


# ──────────────────────────────────────────────────────────────────────────────
# Profile screen — TODO: capture via debug panel
# ──────────────────────────────────────────────────────────────────────────────
# Follow button text varies by locale. Workflows fall back to text lookup when
# the resource-id is not yet known.
FOLLOW_BUTTON_TEXTS = (
    "Follow",
    "Suivre",
    "Seguir",
    "Segui",
    "Folgen",
)
FOLLOWING_BUTTON_TEXTS = (
    "Following",
    "Abonné",
    "Abonné(e)",
    "Siguiendo",
    "Segui già",
    "Abonniert",
)


# ──────────────────────────────────────────────────────────────────────────────
# Search screen (captured from ui_dump 2026-04-22 16:38)
# ──────────────────────────────────────────────────────────────────────────────
SEARCH_BAR = "BdsSearchBar"
SEARCH_TEXT_FIELD = "BasicTextField"
TYPEAHEAD_KEYWORD_ROW = "TypeaheadKeywordSearchRow"
PEOPLE_CELL = "BdsPeopleCell"
IG_TEXT = "ig_text"  # generic text container used inside cells


# ──────────────────────────────────────────────────────────────────────────────
# SERP — Search Engine Result Page (captured from ui_dump 2026-04-22 16:39)
# ──────────────────────────────────────────────────────────────────────────────
SERP_MENU_BUTTON = "serp_navigation_bar_menu_button"
SERP_TAB_HEADER = "TabHeaderItem"  # also reused on the profile screen
# Lazy list/row containers on the SERP.
# IgLazyColumn = vertical feed (posts + mixed sections).
# IgLazyRow    = horizontal profile carousel (Layout B section view).
SERP_LAZY_COLUMN = "IgLazyColumn"
SERP_LAZY_ROW = "IgLazyRow"
# Tab texts vary by locale; ordered by frequency observed in the wild.
TOP_POSTS_TAB_TEXTS = (
    "Top posts",
    "Meilleurs posts",
    "Publicaciones principales",
    "Post migliori",
    "Beste Beiträge",
)
RELATED_PROFILES_TAB_TEXTS = (
    "Related profiles",
    "Profils liés",
    "Perfiles relacionados",
    "Profili correlati",
    "Verwandte Profile",
)


# ──────────────────────────────────────────────────────────────────────────────
# Profile screen (captured from ui_dump 2026-04-22 16:40)
# ──────────────────────────────────────────────────────────────────────────────
PROFILE_SCREEN_ROOT = "ProfileScreen"
PROFILE_FULL_NAME = "profile_screen_full_name"
PROFILE_FOLLOW_BUTTON = "profile_screen_follow_button"
PROFILE_SETTINGS = "profile_screen_profile_settings"
PROFILE_APP_SWITCHER = "profile_screen_ig_app_switcher"
PROFILE_BIO_TEXT = "ProfileBioText"
PROFILE_BIO_FOLLOWER_COUNT = "ProfileBioFollowerCount"
PROFILE_PICTURE = "ProfilePicture"
PROFILE_USERNAME_TEXT = "Username"  # also visible in SERP profile cells
NAV_BAR_BACK_BUTTON = "navigation_bar_back_button"


# ──────────────────────────────────────────────────────────────────────────────
# Repost modal — TODO: capture dedicated dump when first seen
# ──────────────────────────────────────────────────────────────────────────────
REPOST_CONFIRM_TEXTS = (
    "Repost",
    "Republier",
    "Repostear",
    "Ripubblica",
    "Erneut posten",
)


__all__ = [
    "THREADS_PACKAGE",
    "THREADS_MAIN_ACTIVITY",
    "TAB_MAIN_FEED",
    "TAB_MESSAGING",
    "TAB_SEARCH",
    "TAB_CREATE",
    "TAB_ACTIVITY",
    "TAB_PROFILE",
    "TABS_BOTTOM_BAR",
    "FEED_SEARCH_LOUPE_FRACTION",
    "MAIN_FEED_SCREEN",
    "MAIN_FEED_MENU_BUTTON",
    "FEED_POST_ROW",
    "FEED_POST_HEADER",
    "FEED_POST_TEXT",
    "FEED_POST_LIKE",
    "FEED_POST_REPLY",
    "FEED_POST_REPOST",
    "FEED_POST_SHARE",
    "SEARCH_INPUT_HINT_TEXTS",
    "FOLLOW_BUTTON_TEXTS",
    "FOLLOWING_BUTTON_TEXTS",
    "SEARCH_BAR",
    "SEARCH_TEXT_FIELD",
    "TYPEAHEAD_KEYWORD_ROW",
    "PEOPLE_CELL",
    "IG_TEXT",
    "SERP_MENU_BUTTON",
    "SERP_TAB_HEADER",
    "SERP_LAZY_COLUMN",
    "SERP_LAZY_ROW",
    "TOP_POSTS_TAB_TEXTS",
    "RELATED_PROFILES_TAB_TEXTS",
    "PROFILE_SCREEN_ROOT",
    "PROFILE_FULL_NAME",
    "PROFILE_FOLLOW_BUTTON",
    "PROFILE_SETTINGS",
    "PROFILE_APP_SWITCHER",
    "PROFILE_BIO_TEXT",
    "PROFILE_BIO_FOLLOWER_COUNT",
    "PROFILE_PICTURE",
    "PROFILE_USERNAME_TEXT",
    "NAV_BAR_BACK_BUTTON",
    "REPOST_CONFIRM_TEXTS",
]
