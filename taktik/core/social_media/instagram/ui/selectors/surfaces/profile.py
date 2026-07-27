from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L, L_all

@dataclass
class ProfileSelectors:
    """Selecteurs pour les profils utilisateurs.

    Multi-langue (modele overlay) : les selecteurs langue-neutres (resource-id /
    classe / position) vivent ici comme champs ; les fragments dependants de la
    langue (@text / @content-desc / libelles) vivent dans
    ``ui/selectors/locales/<lang>.py`` et sont injectes via ``L("profile.<champ>")``
    selon la locale active (cf. ``ui/language.detect_and_optimize``). Les champs
    langue-dependants sont donc exposes en ``@property`` = base neutre + fragments
    de la locale active. Composition : base neutre d'abord (resource-id, les plus
    specifiques), puis les fragments localises.
    """

    # === Informations de base (listes pour fallbacks) ===
    username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_large_title_auto_size"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[contains(@resource-id, "action_bar_title")]',
        '//*[contains(@resource-id, "action_bar_large_title_auto_size")]',
        '//*[contains(@resource-id, "row_profile_header_username")]',
        '//android.widget.TextView[contains(@text, "@")]'
    ])
    action_bar_title_resource_id: str = "com.instagram.android:id/action_bar_title"

    # === Username from content-desc ===
    username_content_desc: str = '//*[contains(@content-desc, "@")]'
    profile_header_container: str = '//*[@resource-id="com.instagram.android:id/profile_header_container"]'

    bio: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//*[@class="android.widget.TextView"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_bio_text"]',
        '//*[contains(@resource-id, "profile_header_bio_text")]'
    ])

    posts_count: List[str] = field(default_factory=lambda: [
        # NEW IG UI (v410.0.0.53.71, real dump 2026-06-09): the clickable count
        # container is "*_front_familiar", not the legacy "*_container".
        '//*[@resource-id="com.instagram.android:id/profile_header_post_count_front_familiar"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_posts_container"]',
        '//*[contains(@resource-id, "posts_container")]'
    ])
    posts_count_value_resource_id: str = 'profile_header_familiar_post_count_value'
    posts_count_legacy_resource_id: str = 'row_profile_header_textview_post_count'
    posts_count_text_label: str = 'posts'

    followers_count: List[str] = field(default_factory=lambda: [
        # NEW IG UI (v410.0.0.53.71, real dump 2026-06-09): clickable "*_stacked_familiar"
        # container (content-desc "1 568followers"); legacy "*_container" no longer exists.
        '//*[@resource-id="com.instagram.android:id/profile_header_followers_stacked_familiar"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_followers_container"]',
        '//*[contains(@resource-id, "followers_container")]'
    ])
    followers_count_value_resource_id: str = 'profile_header_familiar_followers_value'
    followers_count_legacy_resource_id: str = 'row_profile_header_textview_followers_count'
    followers_count_text_label: str = 'followers'
    followers_count_description_label: str = 'followers'

    following_count: List[str] = field(default_factory=lambda: [
        # NEW IG UI (v410.0.0.53.71, real dump 2026-06-09): clickable "*_stacked_familiar"
        # container (content-desc "695suivi(e)s"); legacy "*_container" no longer exists.
        '//*[@resource-id="com.instagram.android:id/profile_header_following_stacked_familiar"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_following_container"]',
        '//*[contains(@resource-id, "following_container")]'
    ])
    following_count_value_resource_id: str = 'profile_header_familiar_following_value'
    following_count_legacy_resource_id: str = 'row_profile_header_textview_following_count'
    following_count_text_label: str = 'following'

    def profile_count_resource_selector(self, app_id: str, resource_id: str) -> str:
        return f'//*[@resource-id="{app_id}:id/{resource_id}"]'

    def profile_count_text_selector(self, text: str) -> str:
        return f'//*[contains(@text, "{text}")]'

    def profile_count_description_selector(self, description: str) -> str:
        return f'//*[contains(@content-desc, "{description}")]'

    # === Boutons d'action — langue-dependants (overlay locales/) ===
    _follow_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_follow_button"]',
        '//*[@resource-id="com.instagram.android:id/follow_button"]',
    ])

    # Bouton d'action de CHAQUE LIGNE d'une liste de followers/following (resource-id neutre langue).
    # Porte la meme relation (Suivre / Suivi(e) / Suivre en retour) que le header, mais lisible SANS
    # ouvrir le profil -> permet un skip au niveau liste. Le texte est classe par `classify_follow_state`.
    follow_list_row_buttons: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_row_large_follow_button"]',
    ])

    @property
    def follow_button(self) -> List[str]:
        return self._follow_button_base + L("profile.follow_button")

    @property
    def follow_button_anchors(self) -> List[str]:
        """Les xpath resource-id PURS du bouton d'action du header (aucun texte -> neutres langue).

        Point d'ancrage de la LECTURE D'ETAT : on cible le bouton par son id, puis on lit son texte
        et on le compare aux libelles `follow_state_labels_*`. Ne jamais utiliser une forme texte
        ici : elle attraperait `profile_header_follow_context_text` ("Suivi(e) par X, Y").
        """
        return list(self._follow_button_base)

    @property
    def following_button(self) -> List[str]:
        # Les formes sont SCOPEES au bouton cote locales : un match texte nu sur "Suivi(e)" /
        # "Following" attrape aussi `profile_header_follow_context_text` ("Suivi(e) par X, Y" =
        # les amis en commun), un TextView NON cliquable place au-dessus du bouton — de quoi faire
        # taper le mauvais noeud. On ne peut pas prefixer par `_follow_button_base` (resource-id
        # nu) : il matcherait le bouton dans N'IMPORTE quel etat et casserait la detection d'etat.
        return L("profile.following_button")

    @property
    def follow_button_text_labels(self) -> List[str]:
        return L("profile.follow_button_text_labels")

    # === Libelles d'ETAT du bouton d'action (overlay locales/) ===
    # Utilises par get_follow_button_state() : un seul acces device sur le bouton, puis comparaison
    # de son texte a ces libelles. L'ordre de test est porteur (cf. commentaire dans les locales).
    @property
    def follow_state_labels_following(self) -> List[str]:
        return L("profile.follow_state_labels_following")

    @property
    def follow_state_labels_requested(self) -> List[str]:
        return L("profile.follow_state_labels_requested")

    @property
    def follow_state_labels_unfollow(self) -> List[str]:
        return L("profile.follow_state_labels_unfollow")

    @property
    def follow_state_labels_follow_back(self) -> List[str]:
        return L("profile.follow_state_labels_follow_back")

    @property
    def follow_state_labels_follow(self) -> List[str]:
        return L("profile.follow_state_labels_follow")

    _message_button_base: List[str] = field(default_factory=lambda: [
        # "Message" est identique en EN/FR -> neutre.
        '//*[contains(@text, "Message")]',
        '//*[@resource-id="com.instagram.android:id/profile_header_message_button"]'
    ])

    @property
    def message_button(self) -> List[str]:
        return self._message_button_base + L("profile.message_button")

    message_button_resource_id: str = "com.instagram.android:id/profile_header_message_button"

    _message_button_text_labels_base: List[str] = field(default_factory=lambda: [
        'Message',
    ])

    @property
    def message_button_text_labels(self) -> List[str]:
        return self._message_button_text_labels_base + L("profile.message_button_text_labels")

    # === Onglets du profil ===
    # OR-combo bilingue inline (scalaire str, jamais filtre par langue aujourd'hui)
    # -> migration overlay ulterieure ; laisse tel quel, aucun changement de comportement.
    posts_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "Publications") or contains(@content-desc, "Posts")]'

    # The POSTS grid sub-tab, addressed by POSITION rather than by label.
    #
    # Instagram remembers the last sub-tab a profile was left on, so arriving on a profile does NOT
    # mean the grid is showing. A device dump caught "Reposted" active: every thumbnail selector then
    # matches nothing, however far the page is scrolled, and the flow reports "no posts" on a profile
    # that has them. The grid is always the FIRST tab of the row, which is why this keys on position
    # inside `profile_tab_layout` instead of the label — that same dump calls it "Grid view" where
    # `posts_tab` above looks for "Posts"/"Publications", so a label match would have missed it too,
    # and being language-independent it needs no locale overlay.
    profile_grid_tab_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]'
        '//*[@resource-id="com.instagram.android:id/profile_tab_icon_view"][1]',
        '(//*[contains(@resource-id, "profile_tab_icon_view")])[1]',
    ])
    igtv_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "IGTV")]'
    saved_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "Enregistré") or contains(@content-desc, "Saved")]'
    tagged_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "Photos de") or contains(@content-desc, "Photos with")]'

    # === Liens followers/following (overlay locales/) ===
    _followers_link_base: List[str] = field(default_factory=lambda: [
        # NEW Instagram UI (2024+) - clickable container with stacked layout
        '//*[@resource-id="com.instagram.android:id/profile_header_followers_stacked_familiar"]',
        # Resource ID selectors (various Instagram versions)
        '//*[@resource-id="com.instagram.android:id/row_profile_header_followers_container"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_textview_followers_count"]',
    ])

    @property
    def followers_link(self) -> List[str]:
        # Base neutre (resource-id) puis fragments localises (content-desc / text).
        return self._followers_link_base + L("profile.followers_link")

    _following_link_base: List[str] = field(default_factory=lambda: [
        # NEW Instagram UI (2024+) - clickable container with stacked layout
        '//*[@resource-id="com.instagram.android:id/profile_header_following_stacked_familiar"]',
        # Resource ID selectors
        '//*[@resource-id="com.instagram.android:id/row_profile_header_following_container"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_textview_following_count"]',
    ])

    @property
    def following_link(self) -> List[str]:
        return self._following_link_base + L("profile.following_link")

    # === Full name ===
    full_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_full_name"]',
        '//*[contains(@resource-id, "full_name")]'
    ])

    # === Profile picture (for screenshot + crop extraction) ===
    profile_picture_imageview: List[str] = field(default_factory=lambda: [
        # OLD layout: the header avatar ImageView.
        '//*[@resource-id="com.instagram.android:id/row_profile_header_imageview"]',
        # NEW v410 layout (server-gated): row_profile_header_imageview is gone; the header
        # avatar image is `profilePic` (ImageView) nested in the clickable
        # `avatar_on_profile_header_view` button. Scope profilePic to that button so it cannot
        # match a suggestions-carousel avatar; fall back to the button bounds. The old
        # `profile_header_avatar`/`profile_header_avatar_image`/`profile_pic` ids matched NO
        # real dump (removed). Validated on real device dumps (both layouts → square avatar).
        '//*[@resource-id="com.instagram.android:id/avatar_on_profile_header_view"]//*[contains(@resource-id, "profilePic")]',
        '//*[@resource-id="com.instagram.android:id/avatar_on_profile_header_view"]',
    ])

    # Bottom navigation bar avatar (the logged-in user's own picture, last tab).
    # Overlay-free — unlike the profile header avatar it carries no story ring nor
    # "Ajouter à la story" (+) badge — so it is the clean source for OUR connected
    # account picture. Always present on the bottom bar (feed, profile, …).
    # Real dump 2026-06-08 (IG v410): profile_tab > container > tab_avatar (ImageView).
    tab_profile_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_tab")]//*[contains(@resource-id, "tab_avatar")]',
        '//*[contains(@resource-id, "tab_avatar")]',
    ])

    # === Enrichment selectors (XML-based profile extraction) ===
    enrichment_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_username_container"]//android.widget.TextView',
    ])

    enrichment_full_name_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_full_name_above_vanity"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_full_name"]',
    ])

    enrichment_category_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_business_category"]',
    ])

    enrichment_bio_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//android.widget.TextView',
        '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//*[@class="android.widget.TextView"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_bio_text"]',
    ])

    enrichment_website_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_links_view"]//*[@resource-id="com.instagram.android:id/text_view"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_website"]',
    ])

    enrichment_banner_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/banner_row"]//*[@resource-id="com.instagram.android:id/profile_header_banner_item_layout"]',
    ])

    enrichment_banner_title_selector: str = './/*[@resource-id="com.instagram.android:id/profile_header_banner_item_title"]'

    enrichment_bio_more_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//*[contains(@text, "more")]',
        '//*[contains(@text, "… more")]',
        '//*[contains(@text, "...more")]',
    ])

    # Inline bio truncation-expander WORDS ("… more" / "… plus"). A ClickableSpan with no
    # node, so it is located by OCR on the bio crop (not an xpath) and tapped to reveal the
    # full biography. Union FR+EN so the on-screen word matches whatever the device renders.
    @property
    def bio_more_words(self) -> List[str]:
        return L_all("profile.bio_more_words")

    # === Détection de profils privés ===
    _zero_posts_indicators_base: List[str] = field(default_factory=lambda: [
        # "0" est neutre (resource-id + @text="0").
        '//*[@resource-id="com.instagram.android:id/profile_header_familiar_post_count_value" and @text="0"]',
    ])

    @property
    def zero_posts_indicators(self) -> List[str]:
        return self._zero_posts_indicators_base + L("profile.zero_posts_indicators")

    @property
    def private_indicators(self) -> List[str]:
        return L("profile.private_indicators")

    private_empty_state_resource_id: str = "com.instagram.android:id/private_profile_empty_state"

    @property
    def private_text_contains(self) -> List[str]:
        return L("profile.private_text_contains")

    # === Boutons multiples (écrans de suggestions) ===
    # Scalaires str mono-langue (jamais filtres aujourd'hui) -> laisses tels quels.
    follow_buttons: str = '//android.widget.Button[contains(@text, "Follow")]'
    suivre_buttons: str = '//android.widget.Button[contains(@text, "Suivre")]'

    # === About this account (accessible via username click in action bar) ===
    about_account_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_username_container"]',
    ])

    @property
    def about_account_page_indicators(self) -> List[str]:
        return L("profile.about_account_page_indicators")

    @property
    def about_account_date_joined_value(self) -> List[str]:
        return L("profile.about_account_date_joined_value")

    @property
    def about_account_based_in_value(self) -> List[str]:
        return L("profile.about_account_based_in_value")

    # === Sélecteurs avancés pour follow (éviter followers/following) ===
    _advanced_follow_selectors_base: List[str] = field(default_factory=lambda: [
        # Bouton Follow principal dans le header du profil
        '//android.widget.Button[@resource-id="com.instagram.android:id/profile_header_follow_button"]',
        # Bouton Follow dans la barre d'action (apparaît après scroll dans la grille)
        '//android.widget.Button[@resource-id="com.instagram.android:id/follow_button"]',
    ])

    @property
    def advanced_follow_selectors(self) -> List[str]:
        return self._advanced_follow_selectors_base + L("profile.advanced_follow_selectors")

PROFILE_SELECTORS = ProfileSelectors()
