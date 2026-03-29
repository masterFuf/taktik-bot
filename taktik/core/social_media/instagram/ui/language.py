"""
Language detection and selector optimization for Instagram UI.

Detects the app language (EN/FR/...) from a single UI dump, then filters out
selectors that belong to the wrong language so we don't waste time on XPath
lookups that will never match.

Usage (early in any workflow):
    from taktik.core.social_media.instagram.ui.language import detect_and_optimize

    lang = detect_and_optimize(device)   # 'en', 'fr', or 'unknown'
    # All selector dataclass instances are now filtered in-place.
"""

import re
from dataclasses import fields as dataclass_fields
from typing import List, Optional, Set, Tuple
from loguru import logger

log = logger.bind(module="instagram-language")

# ──────────────────────────────────────────────────────────────
# Vocabulary sets — words that ONLY appear in one language
# These are used both for detection (in UI dump) and for
# classifying selectors.
# ──────────────────────────────────────────────────────────────

# French-only words found in content-desc / text attributes
# Exhaustively collected from all selector files in ui/selectors/
_FR_WORDS: Set[str] = {
    # Navigation (navigation.py)
    "Accueil", "Rechercher", "Activité", "Retour", "Précédent",
    "Fermer", "Annuler", "Profil",
    # Profile (profile.py, detection.py)
    "Abonné", "Suivre", "Suivi(e)", "abonnés", "abonnements",
    "Abonnés", "Abonnements",
    "Publications", "Enregistré", "Photos de",
    "Modifier le profil", "Partager le profil",
    "Envoyer un message",
    "Suivre pour voir", "privé",
    "Ce compte est privé",
    "À propos de ce compte", "Date d'inscription", "Compte basé",
    "0 publications",
    "Vérifié", "Professionnel",
    # Interactions (navigation.py, post.py)
    "J'aime", "Commentaire", "Commenter",
    "Ajouter aux enregistrements", "Envoyer la publication",
    "Publier", "Aimé par",
    "Ne plus aimer", "J'aime déjà",
    "Enregistrer", "Partager",
    # Posts (post.py)
    "Reel de", "Audio original",
    "Voir les", "commentaire", "commentaires",
    "Commentaires",
    "nom d'utilisateur",
    "vidéo", "heure", "jour",
    "Couper le son", "Activer le son", "Musique",
    "aime",
    # Popups (popup.py, detection.py)
    "Ne plus suivre", "Suggestions pour vous",
    "Voir toutes les suggestions", "Nous limitons le nombre",
    "nombre de followers affiché",
    "En commun", "Pas maintenant",
    "Confirmer",
    "Mise à jour", "Note",
    "Aucun autre", "Fin de",
    "Et ",  # "Et X autres"
    " autres",
    # Auth (auth.py)
    "Se connecter", "Créer un compte", "Mot de passe",
    "Nom de profil", "Mot de passe oublié",
    "Nom de profil, e-mail ou numéro de mobile",
    "code de sécurité", "vérification",
    "Utiliser un autre profil",
    "incorrecte", "Incorrecte", "suspendu", "bloqué", "trop de", "Réessayer",
    "Connexion", "Français",
    # Scroll / load more (scroll.py, detection.py)
    "Voir plus", "voir plus",
    "Chargement", "Récents", "Récent", "Populaires",
    # Text input (text_input.py)
    "Ajouter un commentaire", "Écrivez une légende", "Biographie",
    "Envoyer", "Autoriser",
    # Unfollow (unfollow.py)
    "Vous suit", "vous suit",
    # Story (story.py)
    "Suivant",
    # Detection (detection.py)
    "Erreur", "Impossible", "Échec",
    "Trop de tentatives", "Veuillez patienter", "Action bloquée",
    "Désolé", "introuvable", "indisponible",
    # Hashtag (detection.py)
    "publications",
}

# English-only words found in content-desc / text attributes
# Exhaustively collected from all selector files in ui/selectors/
_EN_WORDS: Set[str] = {
    # Navigation (navigation.py)
    "Home", "Search", "Activity", "Back",
    "Close", "Cancel", "Profile",
    # Profile (profile.py, detection.py)
    "Following", "Follow", "followers", "following",
    "Followers",
    "Posts", "Saved", "Photos with",
    "Edit profile", "Share profile",
    "Follow to see", "Private", "private",
    "This account is private",
    "About this account", "Date joined", "Account based in",
    "0 posts",
    "Verified", "Professional",
    # Interactions (navigation.py, post.py)
    "Like", "Comment", "Save", "Share",
    "Unlike", "Liked",
    "Liked by", "likes",
    "Post",
    # Posts (post.py)
    "Reel by", "Original audio",
    "View all", "comment", "Comments",
    "Add a comment",
    "video",
    "Like this reel", "Share this reel",
    "Play", "Pause",
    "Turn sound on", "Turn sound off",
    "For you",
    # Popups (popup.py, detection.py)
    "Unfollow", "Suggestions for you", "Suggested for you",
    "See all suggestions",
    "We limit the number",
    "Mutual", "Not Now",
    "Confirm",
    "Update", "Rate",
    "Review this account", "before following",
    "Dismiss", "Suggested",
    "And ",  # "And X others"
    " others",
    # Auth (auth.py)
    "Log in", "Create new account", "Password",
    "Username", "Forgot password",
    "Username, email or mobile number",
    "security code", "verification",
    "Use another profile",
    "incorrect", "Incorrect", "suspended", "blocked", "too many", "Try again",
    "Login", "English",
    "Instagram from Meta",
    # Scroll / load more (scroll.py, detection.py)
    "See more", "see more", "Load more", "Show more",
    "caught up", "End of list", "No more", "That's all",
    "No more suggestions",
    "Loading", "Recent",
    # Text input (text_input.py)
    "Write a caption", "Bio",
    "Send", "Allow",
    # Unfollow (unfollow.py)
    "Follows you",
    "Sort by", "Default", "Date followed",
    # Story (story.py)
    "Next",
    # Detection (detection.py)
    "Error", "Failed", "Retry",
    "Too many requests", "Please wait", "Action blocked",
    "Sorry", "not found", "unavailable",
    # Hashtag (detection.py)
    "posts", "Top",
    # Grid (navigation.py)
    "Grid view",
    # What do you think (popup.py)
    "What do you think",
}

# Regex to extract quoted text values from XPath selectors
# Matches @text="...", @content-desc="...", @hint="...", contains(@text, "..."), etc.
# Two alternations to handle apostrophes inside double-quoted strings (e.g. "J'aime")
_XPATH_TEXT_RE = re.compile(
    r'''(?:@text|@content-desc|@hint|text\(\))\s*[,=]\s*(?:"([^"]+)"|'([^']+)')'''
)

# ──────────────────────────────────────────────────────────────
# Detection probes — content-desc values to look for in UI dump
# ──────────────────────────────────────────────────────────────

_FR_PROBES = ["Accueil", "Rechercher", "Activité", "Retour", "Profil"]
_EN_PROBES = ["Home", "Search", "Activity", "Back", "Profile"]


# ──────────────────────────────────────────────────────────────
# Singleton state
# ──────────────────────────────────────────────────────────────

_detected_lang: Optional[str] = None  # 'en', 'fr', 'unknown'


def get_detected_language() -> Optional[str]:
    """Return the currently detected language, or None if not yet detected."""
    return _detected_lang


# ──────────────────────────────────────────────────────────────
# Language detection from UI dump
# ──────────────────────────────────────────────────────────────

def detect_language(device) -> str:
    """
    Detect Instagram app language from a single UI dump.

    Probes known navigation-bar content-desc values to determine
    whether the app is in French or English.

    Args:
        device: DeviceFacade instance (must expose get_xml_dump() or dump_hierarchy())

    Returns:
        'en', 'fr', or 'unknown'
    """
    global _detected_lang

    try:
        # Get UI XML
        if hasattr(device, 'get_xml_dump'):
            xml = device.get_xml_dump()
        elif hasattr(device, 'dump_hierarchy'):
            xml = device.dump_hierarchy()
        elif hasattr(device, 'device') and hasattr(device.device, 'dump_hierarchy'):
            xml = device.device.dump_hierarchy()
        else:
            log.warning("Cannot get UI dump for language detection")
            _detected_lang = 'unknown'
            return _detected_lang

        if not xml:
            log.warning("Empty UI dump for language detection")
            _detected_lang = 'unknown'
            return _detected_lang

        fr_score = 0
        en_score = 0

        for probe in _FR_PROBES:
            if f'content-desc="{probe}"' in xml or f"content-desc='{probe}'" in xml:
                fr_score += 1
            # Also check as substring (contains)
            elif probe.lower() in xml.lower():
                fr_score += 0.5

        for probe in _EN_PROBES:
            if f'content-desc="{probe}"' in xml or f"content-desc='{probe}'" in xml:
                en_score += 1
            elif probe.lower() in xml.lower():
                en_score += 0.5

        if fr_score > en_score and fr_score >= 2:
            _detected_lang = 'fr'
        elif en_score > fr_score and en_score >= 2:
            _detected_lang = 'en'
        else:
            _detected_lang = 'unknown'

        log.info(f"🌐 Language detected: {_detected_lang} (FR={fr_score}, EN={en_score})")
        return _detected_lang

    except Exception as e:
        log.error(f"Language detection failed: {e}")
        _detected_lang = 'unknown'
        return _detected_lang


# ──────────────────────────────────────────────────────────────
# Selector classification
# ──────────────────────────────────────────────────────────────

def _classify_selector(xpath: str) -> str:
    """
    Classify a single XPath selector as 'fr', 'en', or 'neutral'.

    Rules:
    - If the selector only references resource-id / class / position → neutral
    - If it contains text values matching FR vocabulary → fr
    - If it contains text values matching EN vocabulary → en
    - If it contains both (OR combos) → neutral (keep for safety)

    Handles:
    - Escaped apostrophes in XPath (\\' → ')
    - Substring collisions (e.g. EN "Comment" vs FR "Commentaire"):
      longest match wins per text value.
    """
    # Extract all text values from the xpath
    # Regex returns tuples (double_quoted, single_quoted) — merge them
    raw_matches = _XPATH_TEXT_RE.findall(xpath)
    text_values = [m[0] or m[1] for m in raw_matches]

    if not text_values:
        # No text-based matching → language-neutral selector
        return 'neutral'

    has_fr = False
    has_en = False

    for val in text_values:
        # Normalize escaped apostrophes (XPath uses \' inside strings)
        val_stripped = val.strip().replace("\\'", "'")

        # Find best (longest) FR match
        best_fr_len = 0
        for fr_word in _FR_WORDS:
            if fr_word in val_stripped and len(fr_word) > best_fr_len:
                best_fr_len = len(fr_word)

        # Find best (longest) EN match
        best_en_len = 0
        for en_word in _EN_WORDS:
            if en_word in val_stripped and len(en_word) > best_en_len:
                best_en_len = len(en_word)

        # Longest match wins — avoids "Comment" (EN, 7) beating "Commentaire" (FR, 12)
        if best_fr_len > 0 and best_fr_len >= best_en_len:
            has_fr = True
        elif best_en_len > 0 and best_en_len > best_fr_len:
            has_en = True
        elif best_fr_len > 0 and best_en_len > 0:
            # Equal length matches from both → treat as mixed
            has_fr = True
            has_en = True

    if has_fr and has_en:
        # Mixed selector (e.g., `contains(@text, "Follow") or contains(@text, "Suivre")`)
        return 'neutral'
    elif has_fr:
        return 'fr'
    elif has_en:
        return 'en'
    else:
        # Text values not in our vocabulary → keep as neutral
        return 'neutral'


def filter_selectors(selectors: List[str], lang: str) -> List[str]:
    """
    Filter a list of selectors, removing those that belong to the wrong language.

    Args:
        selectors: Original selector list
        lang: Detected language ('en', 'fr', 'unknown')

    Returns:
        Filtered list (if lang is 'unknown', returns original list unchanged)
    """
    if lang == 'unknown' or not lang:
        return selectors

    # Opposite language to exclude
    exclude_lang = 'fr' if lang == 'en' else 'en'

    filtered = []
    for sel in selectors:
        classification = _classify_selector(sel)
        if classification == exclude_lang:
            continue  # Skip wrong-language selector
        filtered.append(sel)

    return filtered


# ──────────────────────────────────────────────────────────────
# In-place optimization of selector dataclass instances
# ──────────────────────────────────────────────────────────────

def optimize_selector_dataclass(instance, lang: str) -> int:
    """
    Optimize a selector dataclass instance in-place by removing
    wrong-language selectors from all List[str] fields.

    Args:
        instance: A selector dataclass instance (e.g., NAVIGATION_SELECTORS)
        lang: Detected language

    Returns:
        Number of selectors removed
    """
    if lang == 'unknown' or not lang:
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
# Main entry point
# ──────────────────────────────────────────────────────────────

def detect_and_optimize(device) -> str:
    """
    Detect app language and optimize ALL known selector dataclass instances.

    This should be called once, early in the workflow, after the device
    is connected and Instagram is open.

    Args:
        device: DeviceFacade instance

    Returns:
        Detected language string ('en', 'fr', 'unknown')
    """
    lang = detect_language(device)

    if lang == 'unknown':
        log.info("Language unknown — keeping all selectors (no optimization)")
        return lang

    # Import all selector singletons from the centralized selectors package
    from .selectors import (
        PROFILE_SELECTORS, NAVIGATION_SELECTORS, BUTTON_SELECTORS,
        AUTH_SELECTORS, DETECTION_SELECTORS, POST_SELECTORS,
        TEXT_INPUT_SELECTORS, UNFOLLOW_SELECTORS, POPUP_SELECTORS,
        FEED_SELECTORS, HASHTAG_SELECTORS, STORY_SELECTORS,
        FOLLOWERS_LIST_SELECTORS, DM_SELECTORS, SCROLL_SELECTORS,
        CONTENT_CREATION_SELECTORS, NOTIFICATION_SELECTORS,
        PROBLEMATIC_PAGE_SELECTORS, DEBUG_SELECTORS,
    )

    instances = [
        ("ProfileSelectors", PROFILE_SELECTORS),
        ("NavigationSelectors", NAVIGATION_SELECTORS),
        ("ButtonSelectors", BUTTON_SELECTORS),
        ("AuthSelectors", AUTH_SELECTORS),
        ("DetectionSelectors", DETECTION_SELECTORS),
        ("PostSelectors", POST_SELECTORS),
        ("TextInputSelectors", TEXT_INPUT_SELECTORS),
        ("UnfollowSelectors", UNFOLLOW_SELECTORS),
        ("PopupSelectors", POPUP_SELECTORS),
        ("FeedSelectors", FEED_SELECTORS),
        ("HashtagSelectors", HASHTAG_SELECTORS),
        ("StorySelectors", STORY_SELECTORS),
        ("FollowersListSelectors", FOLLOWERS_LIST_SELECTORS),
        ("DMSelectors", DM_SELECTORS),
        ("ScrollSelectors", SCROLL_SELECTORS),
        ("ContentCreationSelectors", CONTENT_CREATION_SELECTORS),
        ("NotificationSelectors", NOTIFICATION_SELECTORS),
        ("ProblematicPageSelectors", PROBLEMATIC_PAGE_SELECTORS),
        ("DebugSelectors", DEBUG_SELECTORS),
    ]

    total_removed = 0
    for name, inst in instances:
        try:
            removed = optimize_selector_dataclass(inst, lang)
            if removed > 0:
                log.debug(f"  {name}: {removed} selectors removed")
            total_removed += removed
        except Exception as e:
            log.warning(f"  {name}: optimization failed: {e}")

    log.info(f"🌐 Selector optimization complete: {total_removed} wrong-language selectors removed (lang={lang})")
    return lang
