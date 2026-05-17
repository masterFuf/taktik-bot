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

    # ── 2. Bouton "Upload / Galerie" (panneau création, vue caméra) ─────────
    # ymg = FrameLayout clickable bas-gauche — Pixel 4 (layout grand écran)
    # ce9 = FrameLayout clickable directement (sans wrapper ymg) — C57S (576x1280)
    # cl2 = variante Samsung v44.9+
    # NE PAS utiliser r3r : c'est le bouton shutter (obturateur caméra, centre écran)
    _upload_btn_rids: List[str] = field(default_factory=lambda: _rids("ymg", "ce9", "cl2"))
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
        # pas de resource-id stable connu — fallback générique via EditText
        '//android.widget.EditText[@clickable="true"][1]',
        '(//android.widget.EditText)[1]',
    ])
    _caption_input_en: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "description")]',
        '//android.widget.EditText[contains(@hint, "Description")]',
        '//android.widget.EditText[contains(@content-desc, "Description")]',
        '//android.widget.EditText[contains(@hint, "caption")]',
    ])
    _caption_input_fr: List[str] = field(default_factory=lambda: [
        # à compléter quand un dump FR sera disponible
    ])

    # ── 6. Bouton "Post / Publier" ─────────────────────────────────────────
    _post_btn_rids: List[str] = field(default_factory=lambda: _rids("post_btn"))
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
    def upload_btn(self) -> List[str]:
        return self._upload_btn_rids + self._upload_btn_en + self._upload_btn_fr

    @property
    def gallery_first_item(self) -> List[str]:
        return self._gallery_first_item_rids

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
    def success_indicator(self) -> List[str]:
        return self._success_en + self._success_fr


PUBLISH_SELECTORS = PublishSelectors()
