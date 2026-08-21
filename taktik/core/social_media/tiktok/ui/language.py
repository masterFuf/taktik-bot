"""
TikTok language detection and selector optimization.

Detects the app language from a single UI dump, then filters out the selectors
that target another language, so no time is spent on xpaths that will never
match.

Adapté depuis ``social_media/instagram/ui/language.py`` (même API).

Usage, early in a workflow:
    from taktik.core.social_media.tiktok.ui.language import detect_and_optimize

    lang = detect_and_optimize(device)   # 'en', 'fr', or 'unknown'
    # Every selector singleton is now filtered in place.
"""

from typing import List, Optional, Set

from loguru import logger

from taktik.core.shared.ui import language_engine as engine

log = logger.bind(module="tiktok-language")

# ──────────────────────────────────────────────────────────────
# Vocabulary: words that appear in ONE language only.
# Distilled from the platform's own selector catalog.
# Used both for detection, against the dump, and for classifying the
# selectors when filtering.
# ──────────────────────────────────────────────────────────────

# French-only words and phrases
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
    "J'aime", "Attribuer un", "Partager une vidéo",
    "Lire ou ajouter des commentaires", "commentaires", "Son :",
    # Inbox / Messages (sections, demandes, follow-back)
    "Nouveaux followers", "Nouveaux abonnés", "Activité",
    "Notifications système", "Demandes de messages", "Comptes suggérés",
    "Suivre en retour", "Accepter", "Supprimer", "Tout voir", "Vu",
    "Ajouter des personnes", "Statut d'activité", "a commencé à te suivre",
    # Errors / states
    "erreur", "réseau", "trop de", "fonctionnalités",
}

# English-only words and phrases
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
    # Inbox / Messages (sections, requests, follow-back)
    "New followers", "Activity", "System notifications",
    "Message requests", "Suggested accounts",
    "Accept", "Delete", "Decline", "View all", "Seen",
    "Add people", "Activity status", "started following you",
    # Errors / states
    "error", "network", "too many", "Something went wrong",
    "Try again later", "No internet", "Cannot send message",
    "Unable to send", "Unable to send message",
    "private", "following",
}

_FR_PATTERNS = engine.compile_vocabulary(_FR_WORDS)
_EN_PATTERNS = engine.compile_vocabulary(_EN_WORDS)

# A wrong language is WORSE than no language: it strips the correct selectors, whereas
# 'unknown' keeps them all. The bar is a score floor plus a RATIO margin, so a one-point
# lead at low score levels is not enough to commit.
_MIN_SCORE = 3.0
_MIN_RATIO = 2.0


def redetect_if_unknown(device) -> Optional[str]:
    """Try detection again, but ONLY if the language is still undecided.

    Detection runs once, on whatever screen TikTok happens to show. A language already
    decided is never re-opened: a later screen could only turn a good answer into a worse one.
    """
    if _detected_lang not in (None, "unknown"):
        return _detected_lang
    log.info("🌐 TikTok language still undecided — retrying detection on the current screen")
    return detect_and_optimize(device)


# ──────────────────────────────────────────────────────────────
# État singleton
# ──────────────────────────────────────────────────────────────

_detected_lang: Optional[str] = None  # 'en', 'fr', 'unknown'


def get_detected_language() -> Optional[str]:
    """The detected language, or None when detection has not run yet."""
    return _detected_lang


def reset_detected_language():
    """Reset the state, which matters between two accounts on the same device."""
    global _detected_lang
    _detected_lang = None


# ──────────────────────────────────────────────────────────────
# Language detection from a UI dump
# ──────────────────────────────────────────────────────────────

def detect_language(device) -> str:
    """Detect the app language from a single UI dump.

    Returns ``'en'``, ``'fr'`` or ``'unknown'``.
    """
    global _detected_lang

    try:
        xml = engine.read_dump(device)
        if not xml:
            log.warning("No usable UI dump for TikTok language detection")
            _detected_lang = "unknown"
            return _detected_lang

        outcome = engine.decide(
            xml, _FR_PATTERNS, _EN_PATTERNS,
            min_score=_MIN_SCORE, min_ratio=_MIN_RATIO,
        )
        _detected_lang = outcome.language

        log.info(
            f"🌐 TikTok language detected: {_detected_lang} "
            f"(FR={outcome.fr_score}, EN={outcome.en_score})"
        )
        if _detected_lang == "unknown":
            log.info(
                f"🌐 TikTok language undecided on this screen — keeping all locales "
                f"({outcome.values_seen} visible strings; "
                f"FR matched {outcome.fr_matched[:6] or 'nothing'}; "
                f"EN matched {outcome.en_matched[:6] or 'nothing'})."
            )
        return _detected_lang

    except Exception as exc:
        log.error(f"TikTok language detection failed: {exc}")
        _detected_lang = "unknown"
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
    Detect the app language, or force it through ``override``, AND optimize every
    known selector singleton.

    Call once, early in a workflow, after connecting to the device and opening the
    app; any screen exposing the bottom navigation is enough.

    Args:
        device: DeviceFacade.
        override: force a language instead of detecting it; an unknown value
            falls back on undecided.

    Returns:
        The active language.
    """
    if override:
        lang = override if override in ("en", "fr") else "unknown"
        log.info(f"🌐 Language override: {override!r} -> {lang}")
    else:
        lang = detect_language(device)

    # Overlay: the migrated selectors read from the active locale.
    from .selectors.locales import set_active_locale
    set_active_locale(lang if lang != "unknown" else None)

    if lang == "unknown":
        log.info("Language unknown — overlay union + no in-place filtering")
        return lang

    # Import every singleton from the selectors barrel
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
