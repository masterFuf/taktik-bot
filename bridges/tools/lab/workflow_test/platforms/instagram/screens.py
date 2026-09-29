"""Instagram screen inference from logs for compat workflow diagnostics."""

_SCREEN_PATTERNS = [
    ("Recovered to followers list", "followers_list"),
    ("Followers list opened", "followers_list"),
    ("followers list", "followers_list"),
    ("Following list opened", "following_list"),
    ("following list", "following_list"),
    ("clickable followers found", "followers_list"),
    ("Detecting Followers list", "followers_list"),
    ("Post view detected", "post_view"),
    ("First post opened", "post_view"),
    ("post opened", "post_view"),
    ("Reel post", "post_view"),
    ("Post liked", "post_view"),
    ("Navigating to next post", "post_view"),
    ("Clicking Like button", "post_view"),
    ("Detecting Liked button", "post_view"),
    ("Detecting Post screen", "post_view"),
    ("Story viewer", "story_viewer"),
    ("story viewer", "story_viewer"),
    ("Profile screen detected", "target_profile"),
    ("Profile extracted", "target_profile"),
    ("Batch profile flags", "target_profile"),
    ("Batch text:", "target_profile"),
    ("Complete profile data", "target_profile"),
    ("Profile image extracted", "target_profile"),
    ("Clicking on @", "navigating_to_profile"),
    ("Confirmed: on own profile", "own_profile"),
    ("own profile", "own_profile"),
    ("Home screen", "home"),
    ("Search screen", "search"),
    ("Recovery - clicking back", "navigating_back"),
    ("Comment button clicked", "comment_input"),
    ("Comment field", "comment_input"),
    ("Attempting to comment", "post_view"),
]


def infer_instagram_screen_from_log(text: str) -> str | None:
    for pattern, screen in _SCREEN_PATTERNS:
        if pattern in text:
            return screen
    return None


__all__ = ["infer_instagram_screen_from_log"]
