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
_XPATH_TEXT_RE = re.compile(
    r'''(?:@text|@content-desc|@hint|text\(\))\s*[,=]\s*(?:"([^"]+)"|'([^']+)')'''
)

# ──────────────────────────────────────────────────────────────
# Detection probes — VISIBLE strings to look for in the UI dump
# ──────────────────────────────────────────────────────────────

_FR_PROBES = ["Accueil", "Rechercher", "Activité", "Retour", "Profil"]
_EN_PROBES = ["Home", "Search", "Activity", "Back", "Profile"]

# Only the VALUES of the visible-text attributes are scored, never the raw XML: an Android dump
# always carries English identifiers, so probing the whole dump gives English a free lead that is
# INDEPENDENT of the app language.
_VISIBLE_ATTR_RE = re.compile(r'(?:text|content-desc)="([^"]*)"')

# A wrong language is WORSE than no language: it strips the correct selectors, whereas 'unknown'
# keeps them all (overlay union). So we only commit when the winner is both solid and clearly
# ahead; otherwise we stay 'unknown' and keep every locale.
#
# The bar is expressed on the FULL vocabulary below, not on the navigation probes it replaced:
# those only exist on the navigation bar, so any content screen scored zero on both sides and
# detection gave up. A score floor plus a RATIO margin makes the rule stricter than a bare
# comparison while firing far more often — at low score levels a one-point lead is noise.
_MIN_SCORE = 3.0
_MIN_RATIO = 2.0


def _visible_strings(xml: str) -> list:
    """The text/content-desc values of the dump (what the USER can read)."""
    return _VISIBLE_ATTR_RE.findall(xml or '')


def _word_pattern(word: str) -> re.Pattern:
    return re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)


# Compiled once: detection scores ~230 words against every visible string of a dump.
_FR_PATTERNS = tuple((w, _word_pattern(w)) for w in sorted(_FR_WORDS))
_EN_PATTERNS = tuple((w, _word_pattern(w)) for w in sorted(_EN_WORDS))


def _score_probes(probes, values) -> float:
    """Score probes against visible strings: exact value = 1, whole-word match = 0.5.

    Whole-word matching matters: 'Profil' (FR) must not score on 'Profile' (EN).
    """
    return _score_patterns([(p, _word_pattern(p)) for p in probes], values)[0]


def _score_patterns(patterns, values) -> tuple:
    """Return ``(score, matched_words)``: exact value = 1 point, whole-word match = 0.5.

    Matched words are reported so an undecided detection can say WHY in one log line —
    the run that started this investigation printed only a score, and the line was cut.
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

        # Score ONLY the visible strings (see _VISIBLE_ATTR_RE): scoring the raw dump let the
        # always-English resource-ids inflate the English score on a French app.
        values = _visible_strings(xml)
        fr_score, fr_words = _score_patterns(_FR_PATTERNS, values)
        en_score, en_words = _score_patterns(_EN_PATTERNS, values)

        if fr_score >= _MIN_SCORE and fr_score >= en_score * _MIN_RATIO:
            _detected_lang = 'fr'
        elif en_score >= _MIN_SCORE and en_score >= fr_score * _MIN_RATIO:
            _detected_lang = 'en'
        else:
            # Not confident enough. 'unknown' keeps EVERY locale's selectors (overlay union), so
            # the bot still works; committing to the wrong language would strip the right ones.
            _detected_lang = 'unknown'

        log.info(f"🌐 Language detected: {_detected_lang} (FR={fr_score}, EN={en_score})")
        if _detected_lang == 'unknown':
            # Say WHAT was seen, not just the score: an undecided detection is only actionable
            # if the next reader can tell "empty screen" from "scores too close".
            log.info(
                f"🌐 Language undecided on this screen — keeping all locales "
                f"({len(values)} visible strings; FR matched {fr_words[:6] or 'nothing'}; "
                f"EN matched {en_words[:6] or 'nothing'}). "
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
