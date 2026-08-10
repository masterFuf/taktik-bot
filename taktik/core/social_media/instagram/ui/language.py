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
from typing import List, Optional, Set
from loguru import logger

from taktik.core.shared.ui import language_engine as engine

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
    # Story (story.py, story_viewer.py)
    "Suivant",
    "non vue", "non vus", "à la une",
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
    # Story (story.py, story_viewer.py)
    "Next",
    "unseen", "highlight story",
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
_FR_PATTERNS = engine.compile_vocabulary(_FR_WORDS)
_EN_PATTERNS = engine.compile_vocabulary(_EN_WORDS)

# A wrong language is WORSE than no language: it strips the correct selectors, whereas
# 'unknown' keeps them all (overlay union). So we only commit when the winner is both
# solid and clearly ahead; otherwise we stay 'unknown' and keep every locale.
#
# The bar is expressed on the FULL vocabulary above, not on the navigation probes it
# replaced: those only exist on the navigation bar, so any content screen scored zero on
# both sides and detection gave up. A score floor plus a RATIO margin makes the rule
# stricter than a bare comparison while firing far more often.
_MIN_SCORE = 3.0
_MIN_RATIO = 2.0


# ──────────────────────────────────────────────────────────────
# Singleton state
# ──────────────────────────────────────────────────────────────

_detected_lang: Optional[str] = None  # 'en', 'fr', 'unknown'


def get_detected_language() -> Optional[str]:
    """Return the currently detected language, or None if not yet detected."""
    return _detected_lang


def redetect_if_unknown(device) -> Optional[str]:
    """Try detection again, but ONLY if the language is still undecided.

    Detection runs once at startup, on whatever screen the app happens to open on — a loading
    feed, sometimes an interstitial, sometimes something that scores nothing at all. A single
    undecided dump used to leave the whole session in union mode.

    This is that second chance. Call it once the bot stands on a screen it CHOSE: the account's
    own profile is the richest available, and the startup sequence goes there anyway. A language
    already decided is never re-opened — re-running detection later could only turn a good answer
    into a worse one.
    """
    if _detected_lang not in (None, 'unknown'):
        return _detected_lang
    log.info("🌐 Language still undecided — retrying detection on the current screen")
    return detect_and_optimize(device)


# ──────────────────────────────────────────────────────────────
# Language detection from UI dump
# ──────────────────────────────────────────────────────────────

def detect_language(device) -> str:
    """Detect the app language from a single UI dump.

    Returns ``'en'``, ``'fr'`` or ``'unknown'``.
    """
    global _detected_lang

    try:
        xml = engine.read_dump(device)
        if not xml:
            log.warning("No usable UI dump for language detection")
            _detected_lang = 'unknown'
            return _detected_lang

        outcome = engine.decide(
            xml, _FR_PATTERNS, _EN_PATTERNS,
            min_score=_MIN_SCORE, min_ratio=_MIN_RATIO,
        )
        _detected_lang = outcome.language

        log.info(
            f"🌐 Language detected: {_detected_lang} "
            f"(FR={outcome.fr_score}, EN={outcome.en_score})"
        )
        if _detected_lang == 'unknown':
            # Say WHAT was seen, not just the score: an undecided detection is only
            # actionable if the next reader can tell "empty screen" from "scores too
            # close".
            log.info(
                f"🌐 Language undecided on this screen — keeping all locales "
                f"({outcome.values_seen} visible strings; "
                f"FR matched {outcome.fr_matched[:6] or 'nothing'}; "
                f"EN matched {outcome.en_matched[:6] or 'nothing'}). "
                "Re-detected later on the account's own profile."
            )
        return _detected_lang

    except Exception as e:
        log.error(f"Language detection failed: {e}")
        _detected_lang = 'unknown'
        return _detected_lang


# ──────────────────────────────────────────────────────────────
# Selector classification
# ──────────────────────────────────────────────────────────────

def _classify_selector(xpath: str) -> str:
    """Classify one xpath against this platform's vocabulary."""
    return engine.classify_selector(xpath, _FR_WORDS, _EN_WORDS)


def filter_selectors(selectors: List[str], lang: str) -> List[str]:
    """Drop the selectors targeting another language. Undecided keeps them all."""
    return engine.filter_selectors(selectors, lang, _FR_WORDS, _EN_WORDS)


def optimize_selector_dataclass(instance, lang: str) -> int:
    """Filter every list field of a selector dataclass in place. Returns the count removed."""
    return engine.optimize_selector_dataclass(instance, lang, _FR_WORDS, _EN_WORDS)


# ──────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────

def detect_and_optimize(device, override: Optional[str] = None) -> str:
    """
    Detect app language (or honor ``override``) and activate the matching locale.

    Called once, early in the workflow, after the device is connected and
    Instagram is open. Sets the active locale so migrated selectors inject the
    right language via ``L()`` (see ``ui/selectors/locales/``), and additionally
    runs the legacy in-place filter as a fallback for selector dataclasses not
    yet migrated to the overlay.

    Args:
        device: DeviceFacade instance.
        override: Force a language code (e.g. from the Cartography Lab language
            picker) instead of auto-detecting. Unknown codes fall back to
            'unknown' (keep-all). When None, the language is auto-detected.

    Returns:
        Active language string ('en', 'fr', 'unknown').
    """
    global _detected_lang

    # Locale overlay: migrated selectors read their language fragments from the
    # active locale set here.
    from .selectors.locales import set_active_locale, available_locales

    if override:
        lang = override if override in available_locales() else 'unknown'
        _detected_lang = lang
        log.info(f"🌐 Language override: {override!r} -> {lang}")
    else:
        lang = detect_language(device)

    set_active_locale(lang if lang != 'unknown' else None)

    if lang == 'unknown':
        log.info("Language unknown — overlay union + no in-place filtering")
        return lang

    # Import all selector singletons from the centralized selectors package
    from .selectors import (
        PROFILE_SELECTORS, NAVIGATION_SELECTORS, BUTTON_SELECTORS,
        AUTH_SELECTORS, DETECTION_SELECTORS, POST_SELECTORS,
        POST_DETAIL_SELECTORS, POST_COMMENTS_SELECTORS, POST_LIKERS_SELECTORS,
        POST_SHARE_SHEET_SELECTORS, POST_GRID_SELECTORS, POST_REELS_SELECTORS,
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
        ("PostDetailSelectors", POST_DETAIL_SELECTORS),
        ("PostCommentsSelectors", POST_COMMENTS_SELECTORS),
        ("PostLikersSelectors", POST_LIKERS_SELECTORS),
        ("PostShareSheetSelectors", POST_SHARE_SHEET_SELECTORS),
        ("PostGridSelectors", POST_GRID_SELECTORS),
        ("PostReelsSelectors", POST_REELS_SELECTORS),
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
