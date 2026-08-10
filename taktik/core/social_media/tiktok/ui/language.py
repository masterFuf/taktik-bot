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

import re
from dataclasses import fields as dataclass_fields
from typing import List, Optional, Set
from loguru import logger

log = logger.bind(module="tiktok-language")

# ──────────────────────────────────────────────────────────────
# Vocabulary: words that appear in ONE language only.
# Distillé depuis ``tiktok/ui/selectors/*.py`` (collecté automatiquement).
# Used both for detection, against the dump, and for classifying the
# selectors when filtering.
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
    # Inbox / Messages (sections, demandes, follow-back)
    "Nouveaux followers", "Nouveaux abonnés", "Activité",
    "Notifications système", "Demandes de messages", "Comptes suggérés",
    "Suivre en retour", "Accepter", "Supprimer", "Tout voir", "Vu",
    "Ajouter des personnes", "Statut d'activité", "a commencé à te suivre",
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

# Regex extracting the text values of an xpath.
# Capture @text="...", @content-desc="...", @hint="...", contains(@text, "..."), etc.
# Two alternations, to cope with apostrophes inside the quoted values.
_XPATH_TEXT_RE = re.compile(
    r'''(?:@text|@content-desc|@hint|text\(\))\s*[,=]\s*(?:"([^"]+)"|'([^']+)')'''
)

# ──────────────────────────────────────────────────────────────
# Detection probes: content-desc values to look for in the dump
# ──────────────────────────────────────────────────────────────

_FR_PROBES = ["Accueil", "Profil", "Boîte de réception", "Créer", "Amis"]
_EN_PROBES = ["Home", "Profile", "Inbox", "Create", "Friends"]

# Only the VALUES of the visible-text attributes are scored. NEVER the raw XML: an Android
# dump always carries English identifiers (`:id/profile_tab`, `:id/inbox_tab`, `:id/home_tab`,
# `:id/friends_tab`…), so a raw substring test handed English one free point per probe,
# language-INDEPENDENTLY. Measured on a French dump whose only visible strings were
# "Abonnements" and "Abonnés": the old rule returned `en (FR=0.5, EN=2.5)` — and committing to
# the WRONG language is worse than 'unknown', because it strips the right selectors instead of
# keeping them all. Instagram was fixed this way on 2026-07-12; TikTok still had the bug.
_VISIBLE_ATTR_RE = re.compile(r'(?:text|content-desc)="([^"]*)"')

# Scored against the full vocabulary (101 FR / 118 EN words), not the five navigation probes:
# those words live on the bottom bar and nowhere else, so any content screen scored nothing at
# all. Higher floor plus a RATIO margin makes the rule stricter than the old one — "2 vs 1.5"
# was a coin flip that stripped a whole locale — while firing on far more screens.
_MIN_SCORE = 3.0
_MIN_RATIO = 2.0


def _visible_strings(xml: str) -> list:
    """The text/content-desc values of the dump (what the USER can read)."""
    return _VISIBLE_ATTR_RE.findall(xml or "")


def _word_pattern(word: str) -> "re.Pattern":
    return re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)


# Compiled once: detection scores ~220 words against every visible string of a dump.
_FR_PATTERNS = tuple((w, _word_pattern(w)) for w in sorted(_FR_WORDS))
_EN_PATTERNS = tuple((w, _word_pattern(w)) for w in sorted(_EN_WORDS))


def _score_patterns(patterns, values) -> tuple:
    """Return ``(score, matched_words)``: exact value = 1 point, whole-word match = 0.5.

    Whole-word matching matters in both directions: FR "Profil" must not score inside EN
    "Profile", and the substring test it replaces did exactly that.
    """
    score = 0.0
    matched = []
    lowered = [v.strip().lower() for v in values]
    for word, pattern in patterns:
        needle = word.strip().lower()
        if needle in lowered:
            score += 1.0
            matched.append(word)
            continue
        if any(pattern.search(v) for v in values):
            score += 0.5
            matched.append(word)
    return score, matched


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
    """
    Detect the TikTok language from a single UI dump.

    Looks for the known bottom-nav content-desc values to decide which
    language the app runs in.

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

        # Score ONLY the visible strings (see _VISIBLE_ATTR_RE): scoring the raw dump let the
        # always-English resource-ids inflate the English score on a French app.
        values = _visible_strings(xml)
        fr_score, fr_words = _score_patterns(_FR_PATTERNS, values)
        en_score, en_words = _score_patterns(_EN_PATTERNS, values)

        if fr_score >= _MIN_SCORE and fr_score >= en_score * _MIN_RATIO:
            _detected_lang = "fr"
        elif en_score >= _MIN_SCORE and en_score >= fr_score * _MIN_RATIO:
            _detected_lang = "en"
        else:
            # Not confident enough. 'unknown' keeps EVERY locale's selectors (overlay union),
            # so the bot still works; committing to the wrong language strips the right ones.
            _detected_lang = "unknown"

        log.info(f"🌐 TikTok language detected: {_detected_lang} (FR={fr_score}, EN={en_score})")
        if _detected_lang == "unknown":
            log.info(
                f"🌐 TikTok language undecided on this screen — keeping all locales "
                f"({len(values)} visible strings; FR matched {fr_words[:6] or 'nothing'}; "
                f"EN matched {en_words[:6] or 'nothing'})."
            )
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

    - no text value -> neutral (resource-id, class, position)
    - Valeur(s) FR exclusivement → ``fr``
    - Valeur(s) EN exclusivement → ``en``
    - mixed forms -> neutral, kept for safety

    Gère :
    - escaped apostrophes inside the xpath
    - substring collisions between languages: the longest match
      wins.
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
    Filter a selector list, dropping those targeting the wrong language.

    Args:
        selectors: the original list.
        lang: the detected language.

    Returns:
        The filtered list; an undecided language returns it unchanged.
    """
    if lang == "unknown" or not lang:
        return selectors

    exclude_lang = "fr" if lang == "en" else "en"

    return [s for s in selectors if _classify_selector(s) != exclude_lang]


# ──────────────────────────────────────────────────────────────
# In-place optimization of a selector dataclass
# ──────────────────────────────────────────────────────────────

def optimize_selector_dataclass(instance, lang: str) -> int:
    """
    Optimize a selector dataclass in place, removing the wrong-language
    selectors from every list field.

    Works with the dataclasses exposing concatenated selectors as properties:
    those are not fields, so only the internal per-language lists are
    filtered.
    

    Args:
        instance: Singleton de sélecteurs (ex. ``VIDEO_SELECTORS``).
        lang: the detected language.

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
