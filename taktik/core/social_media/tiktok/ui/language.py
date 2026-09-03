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


from taktik.core.shared.ui.language_detection import LanguageDetection


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


# ──────────────────────────────────────────────────────────────
# Cablage
# ──────────────────────────────────────────────────────────────
#
# L'orchestration vit dans `shared/ui/language_detection.py` : elle etait ici en double avec
# Instagram, dont quatre fonctions identiques caractere pour caractere. Ne reste que ce qui differe
# vraiment — le vocabulaire ci-dessus.
#
# L'etat est porte par l'INSTANCE, pas par le module : un meme telephone peut afficher TikTok en
# anglais et Instagram en francais, et un etat partage ferait passer la langue de l'une a l'autre.

_DETECTION = LanguageDetection("TikTok", _FR_WORDS, _EN_WORDS)


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
    from .selectors.locales import set_active_locale

    return _DETECTION.detect_and_optimize(
        device, override, barrel=_barrel, set_active_locale=set_active_locale,
    )
