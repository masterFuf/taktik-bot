"""UI selectors for TikTok user profiles."""

from typing import Any, Dict, List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class ProfileSelectors:
    """Selectors for TikTok user profiles.

    Based on a real dump of the profile page.
    Resource-IDs identifiés:
    - qf8: Display name
    - qh5: @username
    - qfw: Compteurs (following/followers/likes)
    - the counter labels
    - b5s: Profile photo
    - h9p: Profile views button
    - xvy: Profile views count
    """

    # === Profile header ===
    _profile_photo_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b5s")]',
    ])

    @property
    def profile_photo(self) -> List[str]:
        return self._profile_photo_base + L("profile.profile_photo")

    @property
    def create_story_button(self) -> List[str]:
        return L("profile.create_story_button")

    _profile_views_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/h9p")]',
    ])

    @property
    def profile_views_button(self) -> List[str]:
        return self._profile_views_button_base + L("profile.profile_views_button")

    profile_views_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xvy")]',
    ])

    @property
    def profile_menu_button(self) -> List[str]:
        return L("profile.profile_menu_button")

    # === Profile information ===
    _display_name_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qf8")]',
    ])

    @property
    def display_name(self) -> List[str]:
        return self._display_name_base + L("profile.display_name_anchors")

    _username_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qh5")]',
    ])

    @property
    def username(self) -> List[str]:
        return self._username_base + L("profile.username_anchors")

    username_content_description: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "@")]',
    ])

    @property
    def edit_profile_button(self) -> List[str]:
        return L("profile.edit_profile_button")

    # === Counters (one id for the values, another for the labels) ===
    _stat_value_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfw")]',
    ])

    @property
    def stat_value(self) -> List[str]:
        return self._stat_value_base + L("profile.stat_value_anchors")

    _stat_label_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfv")]',
    ])

    @property
    def stat_label(self) -> List[str]:
        return self._stat_label_base + L("profile.stat_label_anchors")

    @property
    def following_count(self) -> List[str]:
        return L("profile.following_count")

    @property
    def followers_count(self) -> List[str]:
        return L("profile.followers_count")

    @property
    def likes_count(self) -> List[str]:
        return L("profile.likes_count")

    # Bare LABELS of the three profile stats, used to tell which value you are holding
    # once the row has been paired by position. Read via `classify_profile_stat_label`.
    @property
    def stat_label_following(self) -> List[str]:
        return L("profile.stat_label_following")

    @property
    def stat_label_followers(self) -> List[str]:
        return L("profile.stat_label_followers")

    @property
    def stat_label_likes(self) -> List[str]:
        return L("profile.stat_label_likes")

    @property
    def friends_button_labels(self) -> List[str]:
        return L("profile.friends_button_labels")

    @property
    def following_button_labels(self) -> List[str]:
        """Labels a follow-state button carries when WE follow them, mutual excluded.

        Its own entry rather than a reuse of `stat_label_following`: a stat label and a button
        label happen to share a word today, and conflating them would silently spread any future
        difference across two screens.
        """
        return L("profile.following_button_labels")

    # === Bio ===
    bio: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "For ") or contains(@text, "http")]',
        '//*[contains(@text, "instagram.com") or contains(@text, "youtube.com")]',
    ])

    tiktok_studio_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/a_l")]',
        '//*[@text="TikTok Studio"]',
    ])

    # === Profile content tabs ===
    @property
    def videos_tab(self) -> List[str]:
        return L("profile.videos_tab")

    @property
    def private_videos_tab(self) -> List[str]:
        return L("profile.private_videos_tab")

    @property
    def favourites_tab(self) -> List[str]:
        return L("profile.favourites_tab")

    @property
    def liked_videos_tab(self) -> List[str]:
        return L("profile.liked_videos_tab")

    # === Grille de vidéos ===
    video_grid: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/gxd")]',
        '//android.widget.GridView',
    ])

    _video_item_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/e52")]',
    ])

    @property
    def video_item(self) -> List[str]:
        return self._video_item_base + L("profile.video_item_anchors")

    video_cover: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
    ])

    _video_view_count_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xxy")]',
    ])

    @property
    def video_view_count(self) -> List[str]:
        return self._video_view_count_base + L("profile.video_view_count_anchors")

    # === Profile action buttons, on someone else's profile ===
    #
    # Both of these resolved NOTHING on any captured profile, on either version: they asked for
    # `android.widget.Button`, and the control is a TextView carrying `:id/eme` (43.1.4) or
    # `:id/fij` (46.6.3). No production path used them -- the follow that runs goes through
    # `followers.profile_follow_button` -- but a dead catalogue entry is an invitation to use it
    # and get silence, which is how the next reader loses an afternoon.
    #
    # `normalize-space` is not decoration: the already-following control reads `"Suivis "`, with
    # a trailing space, so an equality on the bare word matches nothing. Measured on nine
    # captured profiles: follow fires on the four that offer it and on none of our own profiles
    # or the ones we already follow; following fires only on the account we do follow.
    _follow_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/eme") or contains(@resource-id, ":id/fij")]'
        '[normalize-space(@text)="Suivre" or normalize-space(@text)="Follow"]',
    ])

    @property
    def follow_button(self) -> List[str]:
        return self._follow_button_base + L("profile.follow_button")

    _following_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/eme") or contains(@resource-id, ":id/fij")]'
        '[normalize-space(@text)="Suivis" or normalize-space(@text)="Following"'
        ' or normalize-space(@text)="Abonné" or normalize-space(@text)="Ami(e)s"'
        ' or normalize-space(@text)="Friends"]',
    ])

    @property
    def following_button(self) -> List[str]:
        return self._following_button_base + L("profile.following_button")

    _message_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Message"]',
        '//android.widget.Button[@text="Message"]',
        '//*[contains(@resource-id, ":id/eme")][@text="Message"]',
        '//android.widget.TextView[@text="Message"]',
    ])

    @property
    def message_button(self) -> List[str]:
        return self._message_button_base + L("profile.message_button")

    # === Page detection: profile page ===
    #: OUR own avatar on our profile page, for cropping out of a screenshot.
    #:
    #: No readable id anywhere near it, measured on 46.6.3 on 2026-08-30: the picture is an
    #: `ImageView` with no id and no description, and every ancestor up to four levels is
    #: obfuscated (`bm2`, `bl1`, `ss_`, `st_`). So the anchor is the CONTAINER, and the caller
    #: takes the biggest match -- the container holds exactly two images, the 252x252 avatar and
    #: the 63x63 "add to story" badge sitting on top of it, and picking the larger drops the badge
    #: without needing to name it.
    #:
    #: The two builds put the avatar on opposite sides -- right on 46.6.3 (`ss_`), left on 43.1.4
    #: (`b5s`) -- so both containers are listed and the first that resolves wins.
    #:
    #: No language-free fallback, deliberately. `//Button//ImageView[no content-desc]` was tried
    #: and REFUSED: it answers 5 times on the profile and 7 times on the feed, so it cannot say
    #: no, and its biggest match on the feed is a video thumbnail that would be cropped and
    #: reported as somebody's face.
    #:
    #: Both halves measured on both builds: 2 nodes on our profile, 0 on the feed.
    own_avatar_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ss_")]//android.widget.ImageView',
        '//android.widget.Button[contains(@resource-id, ":id/bm2")]//android.widget.ImageView',
        '//android.widget.Button[contains(@resource-id, ":id/b5s")]//android.widget.ImageView',
    ])

    _profile_page_indicator_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qh5")]',
        '//*[contains(@resource-id, ":id/gxd")]',
        # A2. The two ids above are 43.1.4 only — on 46.6.3 the header is ss2/svt/fij and the
        # whole indicator read 0 while standing on charlidamelio's profile, so "am I on a
        # profile" answered no on every profile of the newer version.
        #
        # The handle itself is the anchor: TikTok renders it as a Button whose text starts with
        # "@", on both versions and in both languages. Measured 1 on a profile and 0 on the feed
        # on 43.1.4 AND 46.6.3 — the second half is what makes it an indicator rather than a
        # decoration.
        '//android.widget.Button[starts-with(@text, "@")]',
    ])

    @property
    def profile_page_indicator(self) -> List[str]:
        return self._profile_page_indicator_base + L("profile.profile_page_indicator")

    # Bio text (resource-id: qfx)
    _bio_text_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfx")]',
        # A2. `qfx` fires on NO captured profile, on either version, so everything below is what
        # actually reads a bio today.
        #
        # The bio is a Button with no resource-id, and the only thing that tells it apart from
        # the other Buttons on the header is `long-clickable`: bio text can be long-pressed to
        # be copied, an action button cannot. Measured on the eight captured profiles — it
        # returns the bio on the seven that have one, nothing on the account that has none, and
        # never the "Edit" button that the naive "first Button after the handle" grabbed on our
        # own profile.
        #
        # Scoped to what FOLLOWS the handle so it stays a profile-only anchor: unscoped, the
        # same expression fires on twelve feed and comment screens, where a comment body is also
        # a long-clickable Button.
        '//android.widget.Button[starts-with(@text, "@")]/following::android.widget.Button'
        '[@long-clickable="true"][string-length(@text) > 0][1]',
        # Last resort, kept from the locale files where it did not belong (a length rule carries
        # no language). On its own it was the WHOLE bio reader, and it silently dropped every bio
        # under 40 characters -- which on TikTok, where bios are capped at 80, is most of them.
        '//android.widget.Button[string-length(@text) > 40]',
    ])

    @property
    def bio_text(self) -> List[str]:
        return self._bio_text_base + L("profile.bio_text_anchors")

    # Verified badge
    #
    # Nothing on the screen SAYS "verified" — the sweep over a verified profile's whole
    # hierarchy returned zero nodes carrying the word in any attribute, in either language. The
    # English entry (`content-desc` contains "Verified") therefore matched nothing even in
    # English, and the French entry was empty, which on a French phone leaves the list empty:
    # `is_verified` was False for every TikTok profile ever saved.
    #
    # What the badge actually is: a small unlabelled ImageView rendered as the handle's
    # immediate sibling. Measured on eight profiles — it fires on the two verified accounts
    # (@charlidamelio, @yomidenzel) and on none of the six others. The half that makes it an
    # indicator: @marvin.ndiaye.extraits carries the SAME icon id (`ss1`) for the "Compte non
    # recommandé" marker, one row lower and under a different parent, and this anchor refuses
    # it — an icon id alone would have called that account verified.
    _verified_badge_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[starts-with(@text, "@")]'
        '/following-sibling::android.widget.ImageView[1]',
    ])

    @property
    def verified_badge(self) -> List[str]:
        return self._verified_badge_base + L("profile.verified_badge")

    # Private account indicator
    @property
    def private_indicator(self) -> List[str]:
        return L("profile.private_indicator")

    # === Story page detection ===
    story_timestamp: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xyx")]',
    ])

    @property
    def story_close_button(self) -> List[str]:
        return L("profile.story_close_button")

    story_follow_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdo")]',
    ])

    _story_message_input_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qwz")][@text="Message..."]',
    ])

    @property
    def story_message_input(self) -> List[str]:
        return self._story_message_input_base + L("profile.story_message_input")

    story_page_indicator: List[str] = field(default_factory=lambda: [
    ])

    # Story username (clickable, leads to profile)
    story_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/title")][@clickable="true"]',
        '//*[contains(@resource-id, ":id/s28")]//android.widget.Button[contains(@resource-id, ":id/title")]',
    ])

    # === Privacy blocked conversation indicators ===
    @property
    def unable_to_send_message(self) -> List[str]:
        return L("profile.unable_to_send_message")

    _privacy_blocked_message_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/uq5")]',
        '//*[contains(@text, "privacy settings")]',
    ])

    @property
    def privacy_blocked_message(self) -> List[str]:
        return self._privacy_blocked_message_base + L("profile.privacy_blocked_message")

    # Un lien s'ecrit pareil dans toutes les langues, donc cette sonde-la reste du texte brut.
    # Les deux voisines (`verified_description_probe` = "Verified", `private_text_probe` =
    # "private") sont parties avec leur dernier appelant : deux mots anglais, sur des telephones
    # francais, qui repondaient « non » pour chaque profil. Ces deux faits se lisent desormais par
    # `verified_badge` / `private_indicator`, des listes auxquelles l'overlay de locale s'applique.
    website_text_probe: str = "http"
    message_button_text_probe: str = "Message"

    @property
    def bio_button_fallback_selector(self) -> Dict[str, Any]:
        return {"className": "android.widget.Button", "clickable": True}

    @property
    def message_button_text_selector(self) -> Dict[str, Any]:
        return {"text": self.message_button_text_probe}


PROFILE_SELECTORS = ProfileSelectors()
