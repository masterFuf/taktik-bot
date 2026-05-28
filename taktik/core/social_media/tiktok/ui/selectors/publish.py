"""Sélecteurs UI pour la publication TikTok (workflow upload).

Organisation
------------
Les sélecteurs sont groupés en 3 listes par champ :

  *_rids   → resource-id (insensibles à la langue, dépendent de la version d'app)
  *_en     → text / content-desc en anglais
  *_fr     → text / content-desc en français

La concaténation finale est exposée comme une seule liste prête à l'emploi
(`PUBLISH_SELECTORS.create_btn`, etc.) pour rester rétro-compatible avec
`_tap(selectors=...)`. Une fois le module `tiktok/ui/language.py` en place,
on pourra filtrer dynamiquement la portion de la mauvaise langue.

Historique des resource-ids (collecté depuis des dumps réels) :

  Bouton "+"  (Create) :
    nc_   → toutes versions récentes (≥ v43.x)
    mkn   → variante observée (paquet trill)

  Bouton "Upload / Galerie" (vue caméra) :
    ymg   → v43.x+  (FrameLayout galerie, bas-gauche, toutes versions connues)
    cl2   → v44.9+   (Samsung, variante alt)
    NOTE: r3r = bouton shutter/obturateur (centre écran), PAS le bouton galerie

  Galerie — premier thumbnail :
    mub   → v43.x    (ImageView, GridView=i8o)
    nm8   → v44.9+   (ImageView, GridView=ir_)

  Bouton "Next / Suivant" :
    uyb   → v43.x    galerie picker
    ooo   → v44.9+   trim/preview
    w51   → v44.9+   barre multi-sélection
    next_btn → ancien fallback générique
"""

from typing import List
from dataclasses import dataclass, field

# Packages TikTok connus — les resource-ids sont identiques entre tous
_PKG = [
    "com.zhiliaoapp.musically",
    "com.ss.android.ugc.trill",
    "com.ss.android.ugc.aweme",
]


def _rids(*ids: str) -> List[str]:
    """Génère les XPath resource-id pour tous les packages TikTok connus.

    On utilise `contains(@resource-id, ":id/xxx")` plutôt qu'égalité stricte
    pour rester insensible au prefix package — un seul XPath par id couvre
    les 3 variantes.
    """
    return [f'//*[contains(@resource-id, ":id/{rid}")]' for rid in ids]


@dataclass
class PublishSelectors:
    """Sélecteurs pour le workflow de publication TikTok (upload caméra → post).

    Tous les sélecteurs sont des `List[str]` ordonnées du plus spécifique au
    plus générique. `_tap()` les essaie dans l'ordre.
    """

    # ── 1. Bouton "+" (Create) — bottom nav ─────────────────────────────────
    # resource-id robustes (toutes langues)
    _create_btn_rids: List[str] = field(default_factory=lambda: _rids("nc_", "mkn"))
    _create_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Create"]',
        '//android.widget.FrameLayout[@content-desc="Create"]',
        '//android.widget.ImageView[@content-desc="Create"]',
        '//android.widget.Button[contains(@content-desc, "Create")]',
    ])
    _create_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Créer")]',
    ])
    _home_ready_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nc_")]',
        '//*[contains(@resource-id, ":id/mkn")]',
        '//android.widget.Button[@content-desc="Create"]',
        '//android.widget.Button[contains(@content-desc, "Créer")]',
        '//android.widget.Button[contains(@content-desc, "Create")]',
        '//android.widget.FrameLayout[@content-desc="Create"]',
    ])

    # ── 2. Bouton "Upload / Galerie" (panneau création, vue caméra) ─────────
    # ymg = FrameLayout clickable bas-gauche — Pixel 4 (layout grand écran)
    # ce9 = FrameLayout clickable directement (sans wrapper ymg) — C57S (576x1280)
    # cl2 = variante Samsung v44.9+
    # NE PAS utiliser r3r : c'est le bouton shutter (obturateur caméra, centre écran)
    _upload_btn_rids: List[str] = field(default_factory=lambda: [
        # Two real camera layouts observed on identical Samsung A10e devices:
        #   ymg clickable => gallery at bottom-left
        #   ce9 clickable => gallery thumbnail at lower-right
        # Keep clickable variants first so non-clickable child nodes do not win.
        '//*[contains(@resource-id, ":id/ymg") and @clickable="true"]',
        '//*[contains(@resource-id, ":id/ce9") and @clickable="true"]',
        '//*[contains(@resource-id, ":id/cl2") and @clickable="true"]',
        *_rids("ymg", "ce9", "cl2"),
    ])
    _upload_btn_en: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Upload"]',
        '//*[contains(@content-desc, "Upload")]',
        '//*[@text="Upload"]',
        '//*[contains(@text, "Upload")]',
        '//*[contains(@text, "Gallery")]',
    ])
    _upload_btn_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Importer")]',
        '//*[contains(@text, "Galerie")]',
    ])
    _upload_dump_resource_ids: List[str] = field(default_factory=lambda: [
        "ymg",
        "ce9",
        "cl2",
    ])

    # ── 3. Galerie — premier élément (fichier le plus récent) ───────────────
    # `mub`/`nm8` sont clickable=false mais uiautomator2 tape leurs bounds,
    # ce qui déclenche le FrameLayout parent clickable. Pas de fallback coord
    # nécessaire (résolution-indépendant).
    _gallery_first_item_rids: List[str] = field(default_factory=lambda: [
        '(//android.widget.ImageView[contains(@resource-id, ":id/mub")])[1]',
        '(//android.widget.GridView[contains(@resource-id, ":id/i8o")]//android.widget.ImageView)[1]',
        '(//android.widget.ImageView[contains(@resource-id, ":id/nm8")])[1]',
        '(//android.widget.GridView[contains(@resource-id, ":id/ir_")]//android.widget.ImageView)[1]',
        '//*[contains(@resource-id, ":id/ir_")]//*[@class="android.widget.ImageView"][1]',
    ])
    _gallery_picker_xml_markers: List[str] = field(default_factory=lambda: [
        ":id/i8o",
        ":id/ir_",
        ":id/mub",
        ":id/nm8",
    ])
    _camera_creation_copy_markers: List[str] = field(default_factory=lambda: [
        "ajouter un son",
        "add sound",
        'text="photo"',
        'text="texte"',
        'text="publier"',
        'text="créer"',
        'text="create"',
    ])
    _camera_creation_control_markers: List[str] = field(default_factory=lambda: [
        ":id/ce9",
        ":id/r3r",
        ":id/d8a",
        ":id/v5w",
    ])

    # ── 4. Bouton "Next / Suivant" (galerie picker, trim, multi-sélect) ─────
    _next_btn_rids: List[str] = field(default_factory=lambda: _rids("uyb", "ooo", "w51", "next_btn"))
    _next_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Next"]',
        '//android.widget.Button[contains(@text, "Next")]',
        '//android.widget.TextView[contains(@text, "Next")]',
    ])
    _next_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Suivant")]',
        '//android.widget.TextView[contains(@text, "Suivant")]',
    ])

    # ── 5. Zone de description / caption (EditText) ─────────────────────────
    _caption_input_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/g19")]',
        # pas de resource-id stable connu — fallback générique via EditText
        '//android.widget.EditText[@clickable="true"][1]',
        '(//android.widget.EditText)[1]',
    ])
    _caption_input_en: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "Add a description")]',
        '//android.widget.EditText[contains(@text, "Add a description")]',
        '//android.widget.EditText[contains(@content-desc, "Add a description")]',
        '//android.widget.EditText[contains(@hint, "description")]',
        '//android.widget.EditText[contains(@hint, "Description")]',
        '//android.widget.EditText[contains(@content-desc, "Description")]',
        '//android.widget.EditText[contains(@hint, "caption")]',
    ])
    _caption_input_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "Ajouter une description")]',
        '//android.widget.EditText[contains(@text, "Ajouter une description")]',
        '//android.widget.EditText[contains(@content-desc, "Ajouter une description")]',
    ])

    # ── 6. Bouton "Post / Publier" ─────────────────────────────────────────
    _post_btn_rids: List[str] = field(default_factory=lambda: _rids("qrb", "post_btn"))
    _post_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Post"]',
        '//android.widget.Button[contains(@content-desc, "Post")]',
        '//android.widget.Button[@text="Post"]',
        '//android.widget.Button[contains(@text, "Post")]',
        '//android.widget.TextView[contains(@text, "Post")]',
    ])
    _post_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Publier")]',
        '//android.widget.TextView[contains(@text, "Publier")]',
    ])

    # ── 6b. Confirmation optionnelle avant publication réelle ─────────────────
    _publish_confirm_dialog_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/w4m")][contains(@text, "Publier la vidéo publiquement")]',
        '//*[contains(@text, "Publier la vidéo publiquement")]',
    ])
    _publish_confirm_dialog_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Publish video publicly")]',
    ])
    _publish_confirm_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Publier maintenant"]',
        '//android.widget.Button[contains(@text, "Publier")]',
    ])
    _publish_confirm_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Publish now")]',
    ])

    # ── 6c. Overlay clavier Taktik / ADB Keyboard ─────────────────────────────
    _keyboard_overlay_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "com.alexal1.adbkeyboard:id/switchButton")]',
        '//*[contains(@resource-id, "com.alexal1.adbkeyboard:id/subtitle")]',
        '//*[contains(@resource-id, "com.alexal1.adbkeyboard:id/typingNoProgress")]',
        '//*[contains(@text, "Waiting for a job")]',
        '//*[contains(@text, "Auto-typing keyboard")]',
    ])
    _popup_cancel_buttons: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="CANCEL"]',
        '//android.widget.Button[contains(@text, "Cancel")]',
        '//android.widget.Button[contains(@text, "Annuler")]',
        '//android.widget.Button[contains(@text, "Not now")]',
        '//android.widget.Button[contains(@text, "Non merci")]',
    ])
    _video_edit_xml_markers: List[str] = field(default_factory=lambda: [
        'text="annuler"',
        'text="enregistrer"',
        'text="aperçu"',
        'text="importer"',
        'id/xay',
    ])
    _video_edit_cancel_btn: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xay")]',
        '//android.widget.Button[@text="Annuler"]',
        '//android.widget.TextView[@text="Annuler"]',
        '//android.widget.Button[contains(@text, "Cancel")]',
    ])
    _hashtag_suggestion_nodes: List[str] = field(default_factory=lambda: [
        '//*[@class="android.widget.TextView" and starts-with(@text, "#")]',
    ])
    _hashtag_suggestion_rows: List[str] = field(default_factory=lambda: [
        '(//android.view.ViewGroup[@clickable="true"][.//android.widget.TextView[starts-with(@text,"#")]])[1]',
        '(//android.widget.LinearLayout[@clickable="true"][.//android.widget.TextView[starts-with(@text,"#")]])[1]',
        '(//android.widget.TextView[@clickable="true"][starts-with(@text,"#")])[1]',
        '(//androidx.recyclerview.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[1]',
        '(//androidx.recyclerview.widget.RecyclerView/android.widget.LinearLayout[@clickable="true"])[1]',
    ])
    _publish_progress_rids: List[str] = field(default_factory=lambda: _rids("x44"))
    _publish_progress_text_nodes: List[str] = field(default_factory=lambda: [
        '//*[@text and @bounds]',
    ])
    _post_screen_xml_markers_rids: List[str] = field(default_factory=lambda: [
        ":id/g19",
        ":id/qrb",
    ])
    _post_screen_xml_markers_en: List[str] = field(default_factory=lambda: [
        "add a description",
    ])
    _post_screen_xml_markers_fr: List[str] = field(default_factory=lambda: [
        "ajouter une description",
    ])

    # ── 7. Indicateur de succès post-publication ───────────────────────────
    _success_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "successfully")]',
        '//*[contains(@text, "published")]',
        '//*[contains(@content-desc, "Posted")]',
    ])
    _success_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "publié")]',
        '//*[contains(@text, "succès")]',
    ])

    # ── Listes concaténées prêtes à l'emploi ───────────────────────────────
    # Ordre : resource-id → EN → FR (les rids sont les plus fiables)

    @property
    def create_btn(self) -> List[str]:
        return self._create_btn_rids + self._create_btn_en + self._create_btn_fr

    @property
    def home_ready_indicators(self) -> List[str]:
        return self._home_ready_indicators

    @property
    def upload_btn(self) -> List[str]:
        return self._upload_btn_rids + self._upload_btn_en + self._upload_btn_fr

    @property
    def upload_dump_resource_ids(self) -> List[str]:
        return self._upload_dump_resource_ids

    @property
    def upload_dump_selectors(self) -> List[tuple[str, str]]:
        return [
            (rid, f'//*[contains(@resource-id, ":id/{rid}")]')
            for rid in self._upload_dump_resource_ids
        ]

    @property
    def gallery_first_item(self) -> List[str]:
        return self._gallery_first_item_rids

    def has_gallery_picker_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        return any(marker.lower() in lowered_xml for marker in self._gallery_picker_xml_markers)

    def has_camera_creation_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        has_camera_copy = any(marker.lower() in lowered_xml for marker in self._camera_creation_copy_markers)
        has_camera_controls = any(marker.lower() in lowered_xml for marker in self._camera_creation_control_markers)
        return has_camera_copy and has_camera_controls

    @property
    def next_btn(self) -> List[str]:
        return self._next_btn_rids + self._next_btn_en + self._next_btn_fr

    @property
    def caption_input(self) -> List[str]:
        return self._caption_input_en + self._caption_input_fr + self._caption_input_rids

    @property
    def post_btn(self) -> List[str]:
        return self._post_btn_rids + self._post_btn_en + self._post_btn_fr

    @property
    def post_screen_indicators(self) -> List[str]:
        return self.post_btn + self.caption_input

    @property
    def post_screen_xml_markers(self) -> List[str]:
        return (
            self._post_screen_xml_markers_rids
            + self._post_screen_xml_markers_en
            + self._post_screen_xml_markers_fr
        )

    def has_post_screen_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        return any(marker.lower() in lowered_xml for marker in self.post_screen_xml_markers)

    @property
    def popup_cancel_buttons(self) -> List[str]:
        return self._popup_cancel_buttons

    @property
    def video_edit_cancel_btn(self) -> List[str]:
        return self._video_edit_cancel_btn

    @property
    def hashtag_suggestion_nodes(self) -> List[str]:
        return self._hashtag_suggestion_nodes

    @property
    def hashtag_suggestion_rows(self) -> List[str]:
        return self._hashtag_suggestion_rows

    def has_video_edit_screen_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        return (
            self._video_edit_xml_markers[0] in lowered_xml
            and self._video_edit_xml_markers[1] in lowered_xml
            and any(marker in lowered_xml for marker in self._video_edit_xml_markers[2:])
        )

    @property
    def publish_confirm_dialog(self) -> List[str]:
        return self._publish_confirm_dialog_en + self._publish_confirm_dialog_fr

    @property
    def publish_confirm_btn(self) -> List[str]:
        return self._publish_confirm_btn_en + self._publish_confirm_btn_fr

    @property
    def keyboard_overlay_indicators(self) -> List[str]:
        return self._keyboard_overlay_indicators

    @property
    def publish_progress_indicator(self) -> List[str]:
        return self._publish_progress_rids

    @property
    def publish_progress_text_nodes(self) -> List[str]:
        return self._publish_progress_text_nodes

    @property
    def success_indicator(self) -> List[str]:
        return self._success_en + self._success_fr


PUBLISH_SELECTORS = PublishSelectors()
