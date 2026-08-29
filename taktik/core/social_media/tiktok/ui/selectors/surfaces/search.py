"""UI selectors for TikTok search and discovery."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class SearchSelectors:
    """Selectors for TikTok search and discovery.
    
    Based on real UI dumps:
    - ui_dump_20260111_121059.xml (For You page with search icon)
    - ui_dump_20260111_121110.xml (Search input page)
    - ui_dump_20260111_121127.xml (Search results page)
    
    Resource-IDs identifiés:
    - giv: Search input field (EditText)
    - y61: Search button (to submit search)
    - b9c: Back button (in search page)
    - c87: Clear search field button
    - ksc: Search icon in input field
    - spd: More button (3 dots)
    """
    
    # === Search icon on For You page (header) — langue-dependant (overlay locales/) ===
    @property
    def search_icon(self) -> List[str]:
        return L("search.search_icon")

    # === Search input field — base neutre (resource-id) + overlay locales/ ===
    _search_input_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/giv")]',
        '//android.widget.EditText[contains(@resource-id, ":id/giv")]',
    ])

    @property
    def search_input(self) -> List[str]:
        """The search field. `giv` is 43.1.4 only; 46.6.3 names it `ho3` and gives it no hint,
        its placeholder being a trending topic in @text -- so both catalogue entries missed it
        and every Followers run stopped on "Failed to submit search"."""
        return (self._search_input_base
                + L("search.search_input")
                + L("search.search_input_anchors"))

    # === Search submit button — base neutre (resource-id) + overlay locales/ ===
    _search_submit_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y61")]',
    ])

    @property
    def search_submit_button(self) -> List[str]:
        return self._search_submit_button_base + L("search.search_submit_button")

    # === Back button in search page ===
    search_back_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b9c")]',
        '//android.widget.ImageView[contains(@resource-id, ":id/b9c")]',
    ])
    
    # === Clear search field button ===
    clear_search_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c87")]',
        '//android.widget.ImageView[@content-desc="Clear search field"]',
    ])
    
    # === More button (3 dots) ===
    more_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/spd")]',
        '//android.widget.ImageView[@content-desc="More"]',
    ])
    
    # Legacy selectors for compatibility — base neutre (resource-id) + overlay locales/
    _search_bar_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/giv")]',
    ])

    @property
    def search_bar(self) -> List[str]:
        return self._search_bar_base + L("search.search_bar")

    _search_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y61")]',
    ])

    @property
    def search_button(self) -> List[str]:
        return self._search_button_base + L("search.search_button")

    # === Filtres de recherche (tabs on results page) ===
    top_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Top"]',
    ])
    
    users_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Users"]',
        '//android.widget.TextView[@text="Utilisateurs"]',
    ])
    
    @property
    def videos_tab(self) -> List[str]:
        return L("search.videos_tab")

    photos_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Photos"]',
    ])

    _shop_tab_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Boutique"]',
    ])

    @property
    def shop_tab(self) -> List[str]:
        return self._shop_tab_base + L("search.shop_tab")

    @property
    def sounds_tab(self) -> List[str]:
        return L("search.sounds_tab")

    hashtags_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Hashtags"]',
    ])
    
    # === Search suggestions (trending) ===
    suggestion_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Trending")]',
        '//android.widget.TextView[contains(@text, "Trending")]',
    ])
    
    # === Search results ===
    # User result item container
    user_result_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/sh2")]',
        '//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")]',
        # A2, same screen.
        '//*[contains(@resource-id, ":id/tv_username")]/../..',
    ])
    
    # Username in search results
    user_result_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ye2")]',
        '//android.widget.TextView[contains(@resource-id, ":id/ye2")]',
        # A2, measured on a real Users tab (46.6.3). NOTE the app's own naming: `tv_username` holds
        # the @handle and `tv_aweme_id` the display name -- the reverse of what the names suggest.
        '//*[contains(@resource-id, ":id/tv_username")]',
    ])
    
    # User bio in search results
    user_result_bio: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/x8i")]',
    ])
    
    # User followers count in search results
    user_result_followers: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xf0")]',
        # A2: the row's stats line ("159,3 M followers · ..."), not a bio.
        '//*[contains(@resource-id, ":id/tv_desc")]',
    ])
    
    # Follow button in search results — base neutre (resource-id) + overlay locales/
    _user_result_follow_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdh")]',
    ])

    @property
    def user_result_follow_button(self) -> List[str]:
        return self._user_result_follow_button_base + L("search.user_result_follow_button")

    # Video thumbnail in search results
    video_thumbnail: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
        '//android.widget.ImageView[contains(@resource-id, ":id/cover")]',
    ])
    
    # Video container in search results (clickable)
    video_result_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/sq1")]',
        '//android.widget.FrameLayout[contains(@resource-id, ":id/sq1")]',
    ])
    
    # View-all button — language-dependent (locales overlay)
    @property
    def view_all_button(self) -> List[str]:
        return L("search.view_all_button")

    # First search result (generic fallback)
    first_search_result: List[str] = field(default_factory=lambda: [
        '(//androidx.recyclerview.widget.RecyclerView//android.view.ViewGroup)[1]',
    ])

    def user_result_selectors_for_username(self, username: str) -> List[str]:
        """The row of ONE named user on the search Users tab — the exact handle, nobody else.

        The bidi marks were half the story, and scoping the containment to `tv_username` did not
        finish it. Measured again on 2026-08-30 on BOTH versions, asking for `@lena_situations`:

        - the `tv_username`-scoped containment returned **five** rows on 46.6.3
          (`lena_situations1`, `lena_situations`, `lena_situationss`, `lena_situations_fane`,
          `lena_situations__`) and the tap takes the first, so the run opened a 12-follower fan
          account instead of the target — every time, deterministically;
        - on 43.1.4 it returned **nothing at all**: that version names the row `ye2`, not
          `tv_username`, so the whole list fell through to the blind "first row of the list".

        What survives both is not an id but the TEXT SHAPE. TikTok wraps every handle in
        directional isolates — `U+200E U+2068 <handle> U+2069` — identically on 43.1.4 and
        46.6.3, and those isolates DELIMIT the handle. Containing `⁨handle⁩` therefore means
        "this row's handle is exactly this", because anything longer puts a character where the
        closing isolate has to be. Measured: exactly one row, the right one, on both versions,
        for three different queries.

        The loose forms are gone rather than kept as a net. `_landed_on_profile_of` refuses to
        INTERACT with the wrong profile, but it cannot un-open it: opening a stranger's profile
        is already a view on their account. Finding nothing is the better failure.

        TikTok handles are `[a-zA-Z0-9._]` (`ActionUtils.is_valid_username`), so no quote can
        reach the expression below.
        """
        # U+2068 FIRST STRONG ISOLATE / U+2069 POP DIRECTIONAL ISOLATE, written by name because
        # they are invisible in an editor and a stripped copy-paste would silently loosen this
        # back into a prefix match.
        isolated = f"⁨{username}⁩"
        return [
            f'//android.widget.TextView[contains(@text, "{isolated}")]'
            '/ancestor::*[@clickable="true"][1]',
            # Should a version ever drop the isolates, the handle stands alone in its own node.
            f'//android.widget.TextView[@text="{username}"]/ancestor::*[@clickable="true"][1]',
            f'//android.widget.TextView[@text="@{username}"]/ancestor::*[@clickable="true"][1]',
        ]


SEARCH_SELECTORS = SearchSelectors()
