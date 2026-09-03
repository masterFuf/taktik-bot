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

from taktik.core.shared.ui.language_detection import LanguageDetection


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


# ──────────────────────────────────────────────────────────────
# Cablage
# ──────────────────────────────────────────────────────────────
#
# L'orchestration vit dans `shared/ui/language_detection.py` : elle etait ici en double avec
# Instagram, dont quatre fonctions identiques caractere pour caractere. Ne reste que ce qui differe
# vraiment — le vocabulaire ci-dessus.
#
# L'etat est porte par l'INSTANCE, pas par le module : un meme telephone peut afficher Instagram en
# francais et TikTok en anglais, et un etat partage ferait passer la langue de l'une a l'autre.

_DETECTION = LanguageDetection("Instagram", _FR_WORDS, _EN_WORDS)


def get_detected_language() -> Optional[str]:
    """The detected language, or None when detection has not run yet."""
    return _DETECTION.get_detected_language()


def reset_detected_language() -> None:
    """Reset the state, which matters between two accounts on the same device."""
    _DETECTION.reset()


def detect_language(device) -> str:
    """Detect the app language from a single UI dump. Returns 'en', 'fr' or 'unknown'."""
    return _DETECTION.detect_language(device)


def redetect_if_unknown(device) -> Optional[str]:
    """Try detection again, but ONLY if the language is still undecided."""
    return _DETECTION.redetect_if_unknown(device, detect_and_optimize)


def _classify_selector(xpath: str) -> str:
    """Classify one xpath against this platform's vocabulary."""
    return _DETECTION.classify_selector(xpath)


def filter_selectors(selectors: List[str], lang: str) -> List[str]:
    """Drop the selectors targeting another language. Undecided keeps them all."""
    return _DETECTION.filter_selectors(selectors, lang)


def optimize_selector_dataclass(instance, lang: str) -> int:
    """Filter every list field of a selector dataclass in place. Returns the count removed."""
    return _DETECTION.optimize_selector_dataclass(instance, lang)


def detect_and_optimize(device, override: Optional[str] = None) -> str:
    """Detect (or force) the app language AND optimize every known selector singleton."""
    from . import selectors as _barrel
    from .selectors.locales import available_locales, set_active_locale

    return _DETECTION.detect_and_optimize(
        device, override, barrel=_barrel, set_active_locale=set_active_locale,
        available_locales=available_locales,
    )
