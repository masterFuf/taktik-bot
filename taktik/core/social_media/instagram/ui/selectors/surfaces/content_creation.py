from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class ContentCreationSelectors:
    """Sélecteurs pour la création de contenu (posts, stories, reels)."""
    
    # === Tab de création ===
    creation_tab: str = 'com.instagram.android:id/creation_tab'

    # Bouton "+" creer : barre du bas (creation_tab) si presente, sinon l'ImageView
    # cliquable en haut a gauche de l'action bar (sans resource-id/content-desc sur
    # certaines versions). Cible structurelle = selector-only, aucune coordonnee.
    create_button_xpaths: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "creation_tab")]',
        '//*[contains(@resource-id, "action_bar_buttons_container_left")]//android.widget.ImageView[@clickable="true"]',
    ])
    create_button_texts: List[str] = field(default_factory=lambda: ["Create", "Créer"])
    
    # === Galerie ===
    gallery_grid_item: str = 'com.instagram.android:id/gallery_grid_item_thumbnail'
    gallery_grid_item_selection_circle: str = 'com.instagram.android:id/gallery_grid_item_selection_circle'
    # Etat de selection d'un thumbnail : expose dans le content-desc, PAS via le
    # selection_circle (qui existe pour chaque item du grid en mode multi-select).
    #   selectionne   -> "Selected media number N <type> thumbnail created on ..."
    #   non selectionne -> "Unselected <type> thumbnail created on ..."
    selected_media_content_desc: str = 'Selected media number'
    gallery_preview_button: str = 'com.instagram.android:id/gallery_preview_button'
    multi_select_slide_button_alt: str = 'com.instagram.android:id/multi_select_slide_button_alt'
    view_group_class_name: str = "android.view.ViewGroup"
    
    # === Boutons de popup ===
    primary_button: str = 'com.instagram.android:id/primary_button'
    auxiliary_button: str = 'com.instagram.android:id/auxiliary_button'
    bb_primary_action: str = 'com.instagram.android:id/bb_primary_action'
    # Bouton primaire des dialogues "igds headline" (ex: promo one-shot affichee APRES
    # la publication d'une story "Introducing story-to-story sharing" -> content-desc "OK").
    igds_headline_primary_action_button: str = 'com.instagram.android:id/igds_headline_primary_action_button'

    # === Feed reels tray (2e methode story : ajouter depuis le feed) ===
    # Le 1er bubble du tray = notre propre story ; quand le ring est vide le badge
    # `reel_empty_badge` porte content-desc "Add to story" et le label = "Your story".
    reels_tray_container: str = 'com.instagram.android:id/reels_tray_container'
    reel_empty_badge: str = 'com.instagram.android:id/reel_empty_badge'
    
    # === Navigation création ===
    next_button: str = 'com.instagram.android:id/next_button_textview'
    creation_next_button: str = 'com.instagram.android:id/creation_next_button'
    share_button: str = 'com.instagram.android:id/share_button'
    share_footer_button: str = 'com.instagram.android:id/share_footer_button'
    bb_primary_action_container: str = 'com.instagram.android:id/bb_primary_action_container'
    clips_right_action_button: str = 'com.instagram.android:id/clips_right_action_button'
    draft_headline: str = 'com.instagram.android:id/igds_headline_headline'
    draft_body: str = 'com.instagram.android:id/igds_headline_body'

    # Onglets de destination du create (camera) : POST / REEL / STORY.
    cam_dest_feed: str = 'com.instagram.android:id/cam_dest_feed'
    cam_dest_clips: str = 'com.instagram.android:id/cam_dest_clips'
    cam_dest_story: str = 'com.instagram.android:id/cam_dest_story'

    next_texts: List[str] = field(default_factory=lambda: [
        "Next",
        "Suivant",
    ])

    publish_texts: List[str] = field(default_factory=lambda: [
        "Share",
        "Partager",
        "Publier",
    ])

    story_publish_texts: List[str] = field(default_factory=lambda: [
        "Share",
        "Your story",
    ])

    popup_button_texts: List[str] = field(default_factory=lambda: [
        "OK",
        "Got it",
        "Continue",
        "Not now",
        "Skip",
    ])

    caption_placeholder_texts: List[str] = field(default_factory=lambda: [
        "Write a caption...",
    ])

    location_button_texts: List[str] = field(default_factory=lambda: [
        "Add location",
    ])
    edit_text_class_name: str = "android.widget.EditText"
    text_view_class_name: str = "android.widget.TextView"

    next_descriptions: List[str] = field(default_factory=lambda: [
        "Next",
        "Suivant",
    ])

    edit_video_indicators: List[str] = field(default_factory=lambda: [
        "Edit video",
        "Modifier la vidéo",
    ])
    
    edit_video_next_to_clips_pattern: str = r'content-desc="next".{0,400}clips_right_action_button'

    post_type_texts: List[str] = field(default_factory=lambda: [
        "POST",
    ])

    reel_type_texts: List[str] = field(default_factory=lambda: [
        "REEL",
        "Reels",
        "REELS",
    ])

    story_type_texts: List[str] = field(default_factory=lambda: [
        "STORY",
    ])

    reel_draft_headlines: List[str] = field(default_factory=lambda: [
        "Keep editing your draft?",
        "Continuer la modification de votre brouillon ?",
    ])

    reel_draft_bodies: List[str] = field(default_factory=lambda: [
        "If you start a new video, this draft will be saved.",
        "Si vous commencez une nouvelle vidÃ©o, ce brouillon sera enregistrÃ©.",
    ])

    reel_draft_start_new_texts: List[str] = field(default_factory=lambda: [
        "Start new video",
        "Commencer une nouvelle vidÃ©o",
    ])

    # === Champs de texte ===
    caption_text_view: str = 'com.instagram.android:id/caption_text_view'
    caption_input_text_view: str = 'com.instagram.android:id/caption_input_text_view'
    # Bouton "OK"/"Done" de l'editeur de caption plein ecran (action bar haut-droite) :
    # le composer ouvre un editeur dedie quand on tape le champ caption ; valider via OK
    # revient au composer (ou se trouve Share). Presser back ne ferme pas le clavier custom.
    caption_done_button: str = 'com.instagram.android:id/action_bar_button_text'
    soft_input_window_class_name: str = "android.inputmethodservice.SoftInputWindow"
    
    # === Feed interactions ===
    feed_like_button: str = 'com.instagram.android:id/row_feed_button_like'
    feed_profile_name: str = 'com.instagram.android:id/row_feed_photo_profile_name'

    @property
    def gallery_image_container_selector(self) -> Dict[str, Any]:
        return {"className": self.view_group_class_name, "clickable": True}

    @property
    def location_search_field_selector(self) -> Dict[str, str]:
        return {"className": self.edit_text_class_name}

    @property
    def location_first_result_selector(self) -> Dict[str, Any]:
        return {"className": self.text_view_class_name, "instance": 0}

    @property
    def keyboard_window_selector(self) -> Dict[str, str]:
        return {"className": self.soft_input_window_class_name}

    def hashtag_result_selectors(self, hashtag: str) -> List[str]:
        return [
            f'//*[contains(@text, "#{hashtag}")]',
            '//*[contains(@resource-id, "hashtag")]',
        ]

    # === XPath builders for the publish flow (selector-only, clone-agnostic) ===
    # The publish workflow consumes these named groups so no XPath string is ever
    # built inside the workflow code (selectors stay owned by this module).

    @staticmethod
    def _rid_xpath(resource_id: str) -> str:
        """XPath matching a resource-id by suffix (works across clone packages)."""
        return f'//*[contains(@resource-id, "{resource_id.split("/")[-1]}")]'

    @staticmethod
    def _indexed_rid_xpath(resource_id: str, index: int = 1) -> str:
        return f'(//*[contains(@resource-id, "{resource_id.split("/")[-1]}")])[{index}]'

    @staticmethod
    def _text_xpaths(texts: List[str]) -> List[str]:
        """XPath list matching any text or content-desc label."""
        out: List[str] = []
        for t in texts:
            out.append(f'//*[@text="{t}"]')
            out.append(f'//*[@content-desc="{t}"]')
        return out

    def create_button_flow_xpaths(self) -> List[str]:
        """Open-creation ("+") selectors: structural action-bar button or Create label."""
        return list(self.create_button_xpaths) + self._text_xpaths(self.create_button_texts)

    def draft_dismiss_xpaths(self) -> List[str]:
        """'Keep editing your draft?' -> Start new video (optional modal)."""
        return [self._rid_xpath(self.auxiliary_button)] + self._text_xpaths(self.reel_draft_start_new_texts)

    def first_gallery_item_xpath(self) -> str:
        """First (most recent) gallery thumbnail."""
        return self._indexed_rid_xpath(self.gallery_grid_item, 1)

    def gallery_item_xpath(self, index: int = 1) -> str:
        """The Nth gallery thumbnail (1-based)."""
        return self._indexed_rid_xpath(self.gallery_grid_item, index)

    def selected_media_xpath(self) -> str:
        """All gallery thumbnails currently selected (carousel multi-select).

        Selection is read from the thumbnail content-desc ("Selected media number N")
        which is the only reliable per-item signal: the selection_circle view exists
        for every thumbnail in multi-select mode, so it cannot be counted."""
        return f'//*[contains(@content-desc, "{self.selected_media_content_desc}")]'

    def gallery_item_selected_xpath(self, index: int = 1) -> str:
        """The Nth gallery thumbnail, matched ONLY when it is currently selected.

        Used to skip an already-selected thumbnail (re-tapping deselects it)."""
        base = self._indexed_rid_xpath(self.gallery_grid_item, index)
        return f'{base}[contains(@content-desc, "{self.selected_media_content_desc}")]'

    def gallery_grid_xpaths(self) -> List[str]:
        """Presence probe for the gallery grid (any thumbnail visible)."""
        return [self._rid_xpath(self.gallery_grid_item)]

    def multi_select_xpaths(self) -> List[str]:
        """Enable carousel multi-select in the gallery."""
        return [self._rid_xpath(self.multi_select_slide_button_alt)] + self._text_xpaths(
            ["Select multiple", "Select multiple button", "Sélectionner plusieurs"]
        )

    def post_tab_xpaths(self) -> List[str]:
        """POST destination tab (feed post / carousel)."""
        return [self._rid_xpath(self.cam_dest_feed)] + self._text_xpaths(self.post_type_texts)

    def reel_tab_xpaths(self) -> List[str]:
        """REEL destination tab."""
        return [self._rid_xpath(self.cam_dest_clips)] + self._text_xpaths(self.reel_type_texts)

    def story_mode_xpaths(self) -> List[str]:
        """STORY destination tab/mode in the create surface."""
        return [self._rid_xpath(self.cam_dest_story)] + self._text_xpaths(self.story_type_texts)

    def destination_tab_xpaths(self, post_type: str) -> List[str]:
        """Destination tab selectors for a given publish type (POST/REEL/STORY)."""
        if post_type == "reel":
            return self.reel_tab_xpaths()
        if post_type == "story":
            return self.story_mode_xpaths()
        # post + carousel both publish to the feed (POST tab)
        return self.post_tab_xpaths()

    def story_publish_xpaths(self) -> List[str]:
        """'Your story' / Share button to publish a story."""
        return self._text_xpaths(self.story_publish_texts)

    def story_share_promo_dismiss_xpaths(self) -> List[str]:
        """One-time 'story-to-story sharing' promo shown after publishing a story.

        Dismiss via the igds headline primary action (content-desc 'OK'). Called
        non-blocking after publish; the promo only appears the first time."""
        return [self._rid_xpath(self.igds_headline_primary_action_button)] + self._text_xpaths(["OK"])

    def feed_story_tray_add_xpaths(self) -> List[str]:
        """2nd story-entry method: add a story directly from the feed reels tray.

        The first tray bubble is our own story; tapping it opens story creation. We
        anchor on the empty-ring '+' badge (content-desc 'Add to story') and the
        'Your story' label, with the badge resource-id as fallback."""
        return self._text_xpaths(["Add to story", "Ajouter à la story", "Ajouter a la story"]) + [
            '//*[@text="Your story" or @text="Votre story"]',
            self._rid_xpath(self.reel_empty_badge),
        ]

    def gallery_open_xpaths(self) -> List[str]:
        """Open the gallery picker from the create camera (bottom-left preview button)."""
        return [self._rid_xpath(self.gallery_preview_button)] + self._text_xpaths(["Gallery", "Galerie"])

    def composer_xpaths(self) -> List[str]:
        """Caption composer field (presence => composer screen reached)."""
        return [self._rid_xpath(self.caption_input_text_view), self._rid_xpath(self.caption_text_view)]

    def caption_confirm_xpaths(self) -> List[str]:
        """'OK'/'Done' button of the full-screen caption editor (returns to the composer)."""
        return self._text_xpaths(["OK", "Done", "Terminé", "Termine"]) + [self._rid_xpath(self.caption_done_button)]

    def next_button_xpaths(self) -> List[str]:
        """Next button (gallery -> filters -> composer)."""
        return [
            self._rid_xpath(self.creation_next_button),
            self._rid_xpath(self.next_button),
        ] + self._text_xpaths(self.next_texts)

    def post_selection_ok_xpaths(self) -> List[str]:
        """Optional post-selection 'OK' modal."""
        return [self._rid_xpath(self.bb_primary_action_container)] + self._text_xpaths(["OK"])

    def share_button_xpaths(self) -> List[str]:
        """Final Share/Publish button.

        Text/content-desc come FIRST on purpose: the `share_button_container` spans the
        full footer width (Save draft + Share) and its center misses the actual button,
        while `content-desc="Share"` targets the real (right-half) button precisely. The
        resource-id selectors stay as fallbacks."""
        return self._text_xpaths(self.publish_texts) + [
            self._rid_xpath(self.share_footer_button),
            self._rid_xpath(self.share_button),
        ]

CONTENT_CREATION_SELECTORS = ContentCreationSelectors()
