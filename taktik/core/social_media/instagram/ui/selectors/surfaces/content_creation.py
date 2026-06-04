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
    gallery_preview_button: str = 'com.instagram.android:id/gallery_preview_button'
    multi_select_slide_button_alt: str = 'com.instagram.android:id/multi_select_slide_button_alt'
    view_group_class_name: str = "android.view.ViewGroup"
    
    # === Boutons de popup ===
    primary_button: str = 'com.instagram.android:id/primary_button'
    auxiliary_button: str = 'com.instagram.android:id/auxiliary_button'
    bb_primary_action: str = 'com.instagram.android:id/bb_primary_action'
    
    # === Navigation création ===
    next_button: str = 'com.instagram.android:id/next_button_textview'
    creation_next_button: str = 'com.instagram.android:id/creation_next_button'
    share_button: str = 'com.instagram.android:id/share_button'
    share_footer_button: str = 'com.instagram.android:id/share_footer_button'
    bb_primary_action_container: str = 'com.instagram.android:id/bb_primary_action_container'
    clips_right_action_button: str = 'com.instagram.android:id/clips_right_action_button'
    draft_headline: str = 'com.instagram.android:id/igds_headline_headline'
    draft_body: str = 'com.instagram.android:id/igds_headline_body'

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
        """Final Share/Publish button."""
        return [
            self._rid_xpath(self.share_footer_button),
            self._rid_xpath(self.share_button),
        ] + self._text_xpaths(self.publish_texts)

CONTENT_CREATION_SELECTORS = ContentCreationSelectors()
