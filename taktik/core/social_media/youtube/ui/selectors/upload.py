"""Sélecteurs UI pour YouTube — upload (Short & Video standard).

Basés sur des UI dumps réels :
  - Nokia 4.2, Android 11, YouTube app (UI classique)
  - Samsung Galaxy A80Pro, Android 12, YouTube app (Shorts camera view)

Toutes les listes sont ordonnées du plus spécifique (resource-id) au plus générique
(text/content-desc contains), pour minimiser les faux positifs.
"""

from typing import Dict, List
from dataclasses import dataclass, field

YOUTUBE_PACKAGE = "com.google.android.youtube"


@dataclass
class UploadSelectors:
    """Sélecteurs pour le workflow d'upload YouTube (Short & Video)."""

    # ── Navigation home ──────────────────────────────────────────────────────
    home_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Home"]',
        '//*[@content-desc="Accueil"]',
    ])

    # ── Notification permission cancel (in-app dialog YouTube) ──────────────
    notification_cancel: List[str] = field(default_factory=lambda: [
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/custom_confirm_dialog_cancel_button"]',
    ])

    # ── Bottom nav "Create" ("+") button ────────────────────────────────────
    create_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Create"]',
        '//*[contains(@content-desc, "Créer")]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/pivot_bar"]//android.widget.Button',
    ])

    # ── Upload type tabs (Short / Video) ────────────────────────────────────
    tab_short: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Short"]',
        '//android.widget.Button[@text="Short"]',
        '//*[contains(@content-desc, "Short")]',
    ])

    tab_video: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Video"]',
        '//android.widget.Button[@text="Video"]',
        '//android.widget.TextView[@text="Vidéo"]',
        '//android.widget.Button[@text="Vidéo"]',
        '//*[contains(@content-desc, "Video")]',
        '//*[contains(@content-desc, "Vidéo")]',
    ])

    # ── "Add from gallery" button ────────────────────────────────────────────
    # Nokia / older UI : text "Add from gallery"
    # Samsung / Shorts camera view : resource-id reel_camera_gallery_button_delegate
    #                                 content-desc "Import video from photo library"
    add_from_gallery: List[str] = field(default_factory=lambda: [
        # resource-id — device-agnostic, most reliable
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/reel_camera_gallery_button_delegate"]',
        # Samsung-specific Shorts camera resource IDs
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/shorts_gallery_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/gallery_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/creation_gallery_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/shorts_creation_thumbnail"]',
        # content-desc (EN) — exact
        '//*[@content-desc="Import video from photo library"]',
        '//*[@content-desc="Import video from gallery"]',
        '//*[@content-desc="Gallery"]',
        '//*[@content-desc="Open gallery"]',
        # content-desc (FR) — exact
        '//*[@content-desc="Importer une vidéo de la galerie"]',
        '//*[@content-desc="Importer une vidéo depuis la photothèque"]',
        '//*[@content-desc="Importer une vidéo"]',
        '//*[@content-desc="Galerie"]',
        '//*[@content-desc="Ouvrir la galerie"]',
        # content-desc — contains
        '//*[contains(@content-desc, "Import video")]',
        '//*[contains(@content-desc, "Importer")]',
        '//*[contains(@content-desc, "Gallery")]',
        '//*[contains(@content-desc, "Galerie")]',
        # Shorts camera "Photos" bottom tab (newer Samsung/YouTube)
        '//android.widget.Button[@text="Photos"]',
        '//android.widget.TextView[@text="Photos"]',
        # Classic upload screen text (older YouTube, Nokia-style)
        '//android.widget.Button[contains(@text, "Add from gallery")]',
        '//*[contains(@text, "Add from gallery")]',
        '//*[contains(@text, "Ajouter depuis la galerie")]',
        '//*[contains(@text, "Ajouter depuis")]',
        '//*[contains(@text, "Gallery")]',
        '//*[contains(@text, "Galerie")]',
        # Last resort: bottom-area clickable ImageView (gallery thumbnail, no text/desc)
        '(//android.widget.ImageView[@clickable="true"])[last()]',
    ])

    # ── Gallery first item (most recent = just pushed) ───────────────────────
    gallery_first_item: List[str] = field(default_factory=lambda: [
        # Samsung/YouTube internal gallery — clickable FrameLayout wrappers
        '(//android.widget.GridView//android.widget.FrameLayout[@clickable="true"])[1]',
        '(//android.widget.RecyclerView//android.widget.FrameLayout[@clickable="true"])[1]',
        # Fallback: ImageView inside GridView
        '(//android.widget.GridView//android.widget.ImageView)[1]',
        '(//android.widget.RecyclerView//android.widget.ImageView)[1]',
        # System photo picker (Android 13+)
        '(//android.widget.GridView//android.view.View[@clickable="true"])[1]',
        '(//android.widget.RecyclerView//android.view.View[@clickable="true"])[1]',
    ])

    # ── "Next" / "OK" / "Continue" buttons ──────────────────────────────────
    # Covers: gallery multi-select → trim → shorts editor → details screen.
    next_button: List[str] = field(default_factory=lambda: [
        # resource-id (most reliable)
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/multi_select_next_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/shorts_camera_next_button_delegate"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/shorts_trim_finish_trim_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/shorts_post_bottom_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/creation_next_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/next_button"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/action_next"]',
        # content-desc (EN + FR)
        '//*[@content-desc="Go to editor"]',
        '//*[@content-desc="Accéder à l\'éditeur"]',
        '//*[@content-desc="Add segment to project"]',
        '//*[@content-desc="Ajouter le segment au projet"]',
        # text (EN)
        '//android.widget.Button[@text="OK"]',
        '//android.widget.Button[@text="Done"]',
        '//android.widget.Button[@text="Next"]',
        '//android.widget.Button[contains(@text, "Next")]',
        '//android.widget.Button[contains(@text, "Continue")]',
        '//android.widget.TextView[@text="Next"]',
        # text (FR)
        '//android.widget.Button[@text="Suivant"]',
        '//android.widget.Button[contains(@text, "Suivant")]',
        '//android.widget.Button[contains(@text, "Continuer")]',
    ])

    # ── Title / caption input on the caption/details screen ──────────────────
    title_input: List[str] = field(default_factory=lambda: [
        # EN hints
        '//android.widget.EditText[contains(@hint, "Add a title")]',
        '//android.widget.EditText[contains(@hint, "Add a caption")]',
        '//android.widget.EditText[contains(@hint, "Title")]',
        '//android.widget.EditText[contains(@hint, "Caption")]',
        '//android.widget.EditText[contains(@hint, "Add a description")]',
        '//android.widget.EditText[contains(@hint, "description")]',
        # FR hints (A80Pro confirmed: "Donnez un titre à votre Short")
        '//android.widget.EditText[contains(@hint, "Donnez un titre")]',
        '//android.widget.EditText[contains(@hint, "Ajouter un titre")]',
        '//android.widget.EditText[contains(@hint, "Ajouter une légende")]',
        '//android.widget.EditText[contains(@hint, "Titre")]',
        '//android.widget.EditText[contains(@hint, "Légende")]',
        '//android.widget.EditText[contains(@hint, "Ajouter une description")]',
        # Last resort
        '(//android.widget.EditText[@clickable="true"])[1]',
    ])

    # ── Description row on the details screen (opens full-screen EditText) ───
    detail_row_description: List[str] = field(default_factory=lambda: [
        # Text-based: clickable row containing "Description"
        '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Description") or contains(@text, "description") or contains(@text, "Décrip")]]',
        # Direct clickable children of RecyclerView (row-level)
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[1]',
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[1]',
    ])

    # Full-screen description EditText (no hint, just focused)
    description_edittext: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@clickable="true"]',
    ])

    # ── Visibility row on the details screen (opens visibility sub-screen) ───
    detail_row_visibility: List[str] = field(default_factory=lambda: [
        # Text-based: most reliable
        '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Visibilit") or contains(@text, "Visibility")]]',
        '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Priv") and not(contains(@text, "Description"))]]',
        '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Non list") or contains(@text, "Unlisted")]]',
        '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Publique") or contains(@text, "Public")]]',
        # content-desc
        '//*[contains(@content-desc, "visibilit")]',
        '//*[contains(@content-desc, "Visibility")]',
        # Direct clickable rows of RecyclerView (description=[1], visibility=[2..])
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[2]',
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[3]',
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[4]',
        # Nested (higher indices to skip title-row inner sub-elements)
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[4]',
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[5]',
        '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[6]',
    ])

    # Indicator that we've landed on the visibility sub-screen
    visibility_screen_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.ScrollView//android.view.ViewGroup[@clickable="true"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/accessibility_layer_container"]',
    ])

    # Audience/kids sub-screen detector — if present we opened the WRONG row
    audience_screen_indicator: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="En savoir plus"]',
        '//*[contains(@content-desc, "savoir plus")]',
        '//*[contains(@content-desc, "Learn more")]',
        '//*[contains(@content-desc, "learn more")]',
    ])

    # Visibility options inside the visibility sub-screen.
    # YouTube standard order: Public (1st row shown), Unlisted (2nd), Private (3rd).
    # The rows have no accessible text — ordered XPath within the ScrollView.
    visibility_row: Dict[str, str] = field(default_factory=lambda: {
        "public":   '(//android.widget.ScrollView//android.view.ViewGroup[@clickable="true"])[2]',
        "unlisted": '(//android.widget.ScrollView//android.view.ViewGroup[@clickable="true"])[3]',
        "private":  '(//android.widget.ScrollView//android.view.ViewGroup[@clickable="true"])[4]',
    })

    # ── Final upload / post button ────────────────────────────────────────────
    upload_button: List[str] = field(default_factory=lambda: [
        # resource-id (confirmed A80Pro FR YouTube Shorts)
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/upload_bottom_button"]',
        # EN text
        '//android.widget.Button[@text="Upload video"]',
        '//android.widget.Button[@text="Upload Short"]',
        '//android.widget.Button[@text="Upload"]',
        '//android.widget.Button[contains(@text, "Upload")]',
        '//android.widget.Button[contains(@text, "UPLOAD")]',
        '//android.widget.Button[@text="Post"]',
        # FR text (A80Pro confirmed: "Mettre en ligne le Short")
        '//android.widget.Button[@text="Mettre en ligne la vidéo"]',
        '//android.widget.Button[@text="Mettre en ligne le Short"]',
        '//android.widget.Button[contains(@text, "Mettre en ligne")]',
        '//android.widget.Button[@text="Publier"]',
        '//android.widget.Button[contains(@text, "Publier")]',
    ])

    # ── Upload confirmation (post-upload snackbar / toast) ───────────────────
    upload_done: List[str] = field(default_factory=lambda: [
        # resource-id (A80Pro FR: "Importée sur votre chaîne")
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/message"]',
        f'//*[@resource-id="{YOUTUBE_PACKAGE}:id/action"]',  # "Voir la vidéo" link
        # FR text
        '//*[contains(@text, "Importée sur votre chaîne")]',
        '//*[contains(@text, "Importée")]',
        '//*[contains(@text, "Voir la vidéo")]',
        '//*[contains(@text, "Votre vidéo sera en ligne")]',
        # EN text
        '//*[contains(@text, "Your video will be live")]',
        '//*[contains(@text, "Your Short will be live")]',
        '//*[contains(@text, "Processing")]',
        '//*[contains(@text, "Uploading")]',
        '//*[contains(@text, "Uploaded")]',
        '//*[contains(@text, "published")]',
        '//*[contains(@text, "publié")]',
    ])


# Singleton instance — importez directement UPLOAD_SELECTORS dans les workflows
UPLOAD_SELECTORS = UploadSelectors()
