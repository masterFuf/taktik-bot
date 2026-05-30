"""
Détection de langue et optimisation des sélecteurs TikTok.

Détecte la langue de l'app TikTok (EN/FR) depuis un dump UI, puis filtre
les sélecteurs qui ciblent l'autre langue afin de ne pas perdre de temps
sur des XPath qui ne matcheront jamais.

Adapté depuis ``social_media/instagram/ui/language.py`` (même API).

Usage (tôt dans un workflow) :
    from taktik.core.social_media.tiktok.ui.language import detect_and_optimize

    lang = detect_and_optimize(device)   # 'en', 'fr', or 'unknown'
    # Tous les sélecteurs ``*_SELECTORS`` sont maintenant filtrés in-place.
"""

import re
from dataclasses import fields as dataclass_fields
from typing import List, Optional, Set
from loguru import logger

log = logger.bind(module="tiktok-language")

# ──────────────────────────────────────────────────────────────
# Vocabulaire — mots qui n'apparaissent QUE dans une langue
# Distillé depuis ``tiktok/ui/selectors/*.py`` (collecté automatiquement).
# Utilisé à la fois pour la détection (dans le dump XML) et pour la
# classification des sélecteurs (lors du filtrage).
# ──────────────────────────────────────────────────────────────

# Mots/expressions exclusivement FR
_FR_WORDS: Set[str] = {
    # Navigation / bottom bar
    "Accueil", "Amis", "Boîte de réception", "Profil", "Créer",
    "Explorer", "Rechercher", "Retour", "Fermer", "Ignorer",
    "Retour à l'écran précédent", "Menu du profil",
    # Profile
    "Abonné", "Abonnements", "Suivre", "Suivez vos amis",
    "Photo de profil", "Modifier", "Déconnexion", "Se déconnecter",
    "Vidéos privées", "Vidéos aimées", "Favoris", "Retirer des favoris",
    # Auth / signup
    "Se connecter", "Inscription", "Continuer",
    "E-mail", "E-mail ou nom d'utilisateur", "Mot de passe",
    "Créer un mot de passe", "Créer un surnom", "Ajoute ton surnom",
    "Numéro de téléphone", "Téléphone", "Adresse e-mail",
    "Saisis le mot de passe", "Saisir le code",
    "Entrez le code", "Renvoyer", "Renvoyer un code",
    "Code de vérification", "code de vérification",
    "Sélecteur de l'année", "Sélecteur du jour", "Sélecteur du mois",
    "Consulte tes e-mails", "Utiliser un numéro de téléphone",
    "Utilise le lien ou code", "date de naissance",
    "anniversaire", "naissance", "âge", "surnom", "mot de passe",
    # Content / publish
    "Importer", "Galerie", "Publier", "Publié", "publié",
    "Ajouter une description",
    "succès", "Suivant", "Modifier le profil",
    "Vidéos", "Sons",
    # Interactions
    "Répondre", "Ajouter un commentaire", "Pas maintenant",
    "Refuser", "REFUSER", "Ne pas autoriser", "Autoriser",
    "Non", "Plus de", "Sponsorise", "Publicite",
    "J'aime", "Attribuer un", "Partager une vidÃ©o",
    "Lire ou ajouter des commentaires", "commentaires", "Son :",
    # Errors / states
    "erreur", "réseau", "trop de", "fonctionnalités",
}

# Mots/expressions exclusivement EN
_EN_WORDS: Set[str] = {
    # Navigation / bottom bar
    "Home", "Friends", "Inbox", "Profile", "Create",
    "Explore", "Search", "Back", "Close", "Skip",
    "Go back", "Navigate up", "Profile menu",
    # Profile
    "Followers", "Following", "Follow", "Follow back", "Unfollow",
    "Profile photo", "Edit", "Edit profile",
    "Log out", "Log in", "Sign up",
    "Private videos", "Liked videos", "Reposted videos",
    "Favorites", "Favourites", "Remove from Favourites",
    "Subscribe", "Verified",
    # Auth / signup
    "Sign up for TikTok", "Continue",
    "Email", "Email address", "Email or username", "Password",
    "Create a password", "Create a username", "Add your username",
    "Phone number", "Phone",
    "Enter password", "Enter the code", "Enter code",
    "Resend", "Resend code",
    "Verification code", "verification code",
    "Year picker", "Day picker", "Month picker",
    "Check your email", "Use phone or email",
    "Use the link or code", "date of birth",
    "Date of birth", "Birthday", "birthday",
    # Content / publish
    "Upload", "Gallery", "Post", "Posted", "Published",
    "Add a description",
    "successfully", "published", "Next", "Edit profile",
    "Videos", "Sounds", "Sound:",
    # Interactions
    "Reply", "Add a comment", "Add comment", "Comment...",
    "Not now", "Not interested",
    "Deny", "DENY", "Don't allow", "Allow",
    "No", "More fun", "Shop", "Shop now",
    "Like video", "Like this", "Liked", "Unlike",
    "Like", "Share video", "Read or add comments",
    "Add or remove this video from Favour",
    # Errors / states
    "error", "network", "too many", "Something went wrong",
    "Try again later", "No internet", "Cannot send message",
    "Unable to send", "Unable to send message",
    "private", "following",
}

# Regex pour extraire les valeurs texte d'un XPath.
# Capture @text="...", @content-desc="...", @hint="...", contains(@text, "..."), etc.
# Deux alternances pour gérer les apostrophes (ex. "E-mail ou nom d'utilisateur").
_XPATH_TEXT_RE = re.compile(
    r'''(?:@text|@content-desc|@hint|text\(\))\s*[,=]\s*(?:"([^"]+)"|'([^']+)')'''
)

# ──────────────────────────────────────────────────────────────
# Probes de détection — content-desc à chercher dans le dump XML
# ──────────────────────────────────────────────────────────────

_FR_PROBES = ["Accueil", "Profil", "Boîte de réception", "Créer", "Amis"]
_EN_PROBES = ["Home", "Profile", "Inbox", "Create", "Friends"]


# ──────────────────────────────────────────────────────────────
# État singleton
# ──────────────────────────────────────────────────────────────

_detected_lang: Optional[str] = None  # 'en', 'fr', 'unknown'


def get_detected_language() -> Optional[str]:
    """Retourne la langue détectée, ou None si pas encore détectée."""
    return _detected_lang


def reset_detected_language():
    """Réinitialise l'état (utile entre deux comptes sur un même device)."""
    global _detected_lang
    _detected_lang = None


# ──────────────────────────────────────────────────────────────
# Détection de langue depuis un dump UI
# ──────────────────────────────────────────────────────────────

def detect_language(device) -> str:
    """
    Détecte la langue de TikTok depuis un seul dump UI.

    Cherche les content-desc connus du bottom nav pour déterminer si
    l'app est en français ou anglais.

    Args:
        device: DeviceFacade (doit exposer ``get_xml_dump()`` ou ``dump_hierarchy()``).

    Returns:
        'en', 'fr', ou 'unknown'.
    """
    global _detected_lang

    try:
        if hasattr(device, "get_xml_dump"):
            xml = device.get_xml_dump()
        elif hasattr(device, "dump_hierarchy"):
            xml = device.dump_hierarchy()
        elif hasattr(device, "device") and hasattr(device.device, "dump_hierarchy"):
            xml = device.device.dump_hierarchy()
        else:
            log.warning("Cannot get UI dump for language detection")
            _detected_lang = "unknown"
            return _detected_lang

        if not xml:
            log.warning("Empty UI dump for language detection")
            _detected_lang = "unknown"
            return _detected_lang

        fr_score = 0.0
        en_score = 0.0

        for probe in _FR_PROBES:
            if f'content-desc="{probe}"' in xml or f"content-desc='{probe}'" in xml:
                fr_score += 1
            elif probe.lower() in xml.lower():
                fr_score += 0.5

        for probe in _EN_PROBES:
            if f'content-desc="{probe}"' in xml or f"content-desc='{probe}'" in xml:
                en_score += 1
            elif probe.lower() in xml.lower():
                en_score += 0.5

        if fr_score > en_score and fr_score >= 2:
            _detected_lang = "fr"
        elif en_score > fr_score and en_score >= 2:
            _detected_lang = "en"
        else:
            _detected_lang = "unknown"

        log.info(f"🌐 TikTok language detected: {_detected_lang} (FR={fr_score}, EN={en_score})")
        return _detected_lang

    except Exception as e:
        log.error(f"TikTok language detection failed: {e}")
        _detected_lang = "unknown"
        return _detected_lang


# ──────────────────────────────────────────────────────────────
# Classification d'un sélecteur
# ──────────────────────────────────────────────────────────────

def _classify_selector(xpath: str) -> str:
    """
    Classe un XPath comme 'fr', 'en', ou 'neutral'.

    - Pas de valeur texte → ``neutral`` (resource-id, class, position)
    - Valeur(s) FR exclusivement → ``fr``
    - Valeur(s) EN exclusivement → ``en``
    - Mixte (OR combos) → ``neutral`` (à conserver par sécurité)

    Gère :
    - Apostrophes échappées dans XPath (``\\'`` → ``'``)
    - Collisions de substring (ex. EN "Post" vs FR "Posté") : le match le
      plus long gagne.
    """
    raw_matches = _XPATH_TEXT_RE.findall(xpath)
    text_values = [m[0] or m[1] for m in raw_matches]

    if not text_values:
        return "neutral"

    has_fr = False
    has_en = False

    for val in text_values:
        val_stripped = val.strip().replace("\\'", "'")

        best_fr_len = 0
        for fr_word in _FR_WORDS:
            if fr_word in val_stripped and len(fr_word) > best_fr_len:
                best_fr_len = len(fr_word)

        best_en_len = 0
        for en_word in _EN_WORDS:
            if en_word in val_stripped and len(en_word) > best_en_len:
                best_en_len = len(en_word)

        if best_fr_len > 0 and best_fr_len >= best_en_len:
            has_fr = True
        elif best_en_len > 0 and best_en_len > best_fr_len:
            has_en = True
        elif best_fr_len > 0 and best_en_len > 0:
            has_fr = True
            has_en = True

    if has_fr and has_en:
        return "neutral"
    elif has_fr:
        return "fr"
    elif has_en:
        return "en"
    else:
        return "neutral"


def filter_selectors(selectors: List[str], lang: str) -> List[str]:
    """
    Filtre une liste de sélecteurs en retirant ceux qui ciblent la mauvaise langue.

    Args:
        selectors: Liste originale.
        lang: Langue détectée ('en', 'fr', 'unknown').

    Returns:
        Liste filtrée (si lang == 'unknown', retourne la liste inchangée).
    """
    if lang == "unknown" or not lang:
        return selectors

    exclude_lang = "fr" if lang == "en" else "en"

    return [s for s in selectors if _classify_selector(s) != exclude_lang]


# ──────────────────────────────────────────────────────────────
# Optimisation in-place d'une dataclass de sélecteurs
# ──────────────────────────────────────────────────────────────

def optimize_selector_dataclass(instance, lang: str) -> int:
    """
    Optimise une dataclass de sélecteurs in-place en retirant les
    sélecteurs de la mauvaise langue de tous les champs ``List[str]``.

    Compatible avec les dataclasses qui exposent des sélecteurs concaténés
    via ``@property`` (ex. ``PublishSelectors``) : ces propriétés ne sont
    pas des fields, donc seules les listes internes ``_xxx_en`` / ``_xxx_fr``
    sont filtrées.

    Args:
        instance: Singleton de sélecteurs (ex. ``VIDEO_SELECTORS``).
        lang: Langue détectée.

    Returns:
        Nombre de sélecteurs retirés.
    """
    if lang == "unknown" or not lang:
        return 0

    removed = 0
    for f in dataclass_fields(instance):
        val = getattr(instance, f.name)
        if isinstance(val, list) and val and isinstance(val[0], str):
            filtered = filter_selectors(val, lang)
            removed += len(val) - len(filtered)
            if len(filtered) < len(val):
                setattr(instance, f.name, filtered)

    return removed


# ──────────────────────────────────────────────────────────────
# Point d'entrée principal
# ──────────────────────────────────────────────────────────────

def detect_and_optimize(device) -> str:
    """
    Détecte la langue de l'app TikTok ET optimise tous les singletons
    de sélecteurs connus.

    À appeler une fois, tôt dans un workflow, après connexion au device
    et ouverture de TikTok (n'importe quel écran exposant le bottom nav suffit).

    Args:
        device: DeviceFacade.

    Returns:
        Langue détectée ('en', 'fr', 'unknown').
    """
    lang = detect_language(device)

    if lang == "unknown":
        log.info("Language unknown — keeping all selectors (no optimization)")
        return lang

    # Import tous les singletons depuis le barrel selectors/
    from .selectors import (
        AUTH_SELECTORS, SIGNUP_SELECTORS, LOGOUT_SELECTORS,
        COUNTRY_PICKER_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS,
        VIDEO_CREATOR_SELECTORS, VIDEO_ENGAGEMENT_SELECTORS,
        VIDEO_MEDIA_SELECTORS, VIDEO_STATE_SELECTORS,
        COMMENT_SELECTORS, SEARCH_SELECTORS,
        INBOX_SELECTORS, CONVERSATION_SELECTORS, POPUP_SELECTORS,
        SCROLL_SELECTORS, DETECTION_SELECTORS, FOLLOWERS_SELECTORS,
        PUBLISH_COMPOSER_SELECTORS,
        PUBLISH_CREATION_ENTRY_SELECTORS,
        PUBLISH_EDITOR_SELECTORS,
        PUBLISH_MEDIA_PICKER_SELECTORS,
        PUBLISH_PROGRESS_SELECTORS,
    )

    instances = [
        ("AuthSelectors", AUTH_SELECTORS),
        ("SignupSelectors", SIGNUP_SELECTORS),
        ("LogoutSelectors", LOGOUT_SELECTORS),
        ("CountryPickerSelectors", COUNTRY_PICKER_SELECTORS),
        ("NavigationSelectors", NAVIGATION_SELECTORS),
        ("ProfileSelectors", PROFILE_SELECTORS),
        ("VideoCreatorSelectors", VIDEO_CREATOR_SELECTORS),
        ("VideoEngagementSelectors", VIDEO_ENGAGEMENT_SELECTORS),
        ("VideoMediaSelectors", VIDEO_MEDIA_SELECTORS),
        ("VideoStateSelectors", VIDEO_STATE_SELECTORS),
        ("CommentSelectors", COMMENT_SELECTORS),
        ("SearchSelectors", SEARCH_SELECTORS),
        ("InboxSelectors", INBOX_SELECTORS),
        ("ConversationSelectors", CONVERSATION_SELECTORS),
        ("PopupSelectors", POPUP_SELECTORS),
        ("ScrollSelectors", SCROLL_SELECTORS),
        ("DetectionSelectors", DETECTION_SELECTORS),
        ("FollowersSelectors", FOLLOWERS_SELECTORS),
        ("PublishCreationEntrySelectors", PUBLISH_CREATION_ENTRY_SELECTORS),
        ("PublishMediaPickerSelectors", PUBLISH_MEDIA_PICKER_SELECTORS),
        ("PublishEditorSelectors", PUBLISH_EDITOR_SELECTORS),
        ("PublishComposerSelectors", PUBLISH_COMPOSER_SELECTORS),
        ("PublishProgressSelectors", PUBLISH_PROGRESS_SELECTORS),
    ]

    total_removed = 0
    for name, inst in instances:
        try:
            n = optimize_selector_dataclass(inst, lang)
            if n > 0:
                log.debug(f"  • {name}: removed {n} wrong-language selector(s)")
            total_removed += n
        except Exception as e:
            log.warning(f"  • {name}: optimization failed ({e})")

    log.info(f"✅ TikTok selectors optimized for '{lang}' "
             f"({total_removed} wrong-language selector(s) removed)")
    return lang
