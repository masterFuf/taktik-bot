"""«Est-ce que je suis déjà cet auteur ?» — répondu par une absence, et gardé.

Mesuré le 2026-08-29 sur l'onglet « Suivis » du fil (où chaque auteur est suivi par définition)
face au fil « Pour toi » : le bouton de suivi y lit **0** contre **1**. TikTok ne dit pas
« abonné », il retire l'affordance.

Le champ que ce détecteur lisait, `user_followed_indicator`, nomme un bouton « Following » /
« Friends » qui n'existe pas sur cette surface : vide en français, 0 partout en anglais. La
question répondait donc « non » pour tout le monde, et le bot re-suivait des comptes déjà suivis
en dépensant un follow de son budget de session.
"""

from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector


class _Screen:
    """Chaque famille de sélecteur répond indépendamment, comme sur un vrai écran."""

    def __init__(self, *, on_video=True, follow_button=False, followed_marker=False):
        self.on_video = on_video
        self.follow_button = follow_button
        self.followed_marker = followed_marker

    def _answer(self, selector: str) -> bool:
        if "long_press_layout" in selector or "Partager une vid" in selector or ":id/f57" in selector:
            return self.on_video
        if "Suivre" in selector or ":id/hi1" in selector:
            return self.follow_button
        if "Following" in selector or "Friends" in selector or "Unfollow" in selector:
            return self.followed_marker
        return False

    def xpath(self, selector):
        exists = self._answer(selector)

        class _Element:
            def __init__(self, value):
                self.exists = value

        return _Element(exists)


def _detector(screen) -> VideoDetector:
    detector = VideoDetector.__new__(VideoDetector)
    detector.device = screen
    from loguru import logger

    detector.logger = logger
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_SELECTORS

    detector.video_selectors = VIDEO_SELECTORS
    return detector


def test_an_author_we_follow_has_no_follow_button():
    """Le cas mesuré sur l'onglet « Suivis »."""
    assert _detector(_Screen(on_video=True, follow_button=False)).is_user_followed() is True


def test_an_author_we_do_not_follow_still_offers_to_follow():
    """Le cas mesuré sur « Pour toi », sur les deux versions."""
    assert _detector(_Screen(on_video=True, follow_button=True)).is_user_followed() is False


def test_not_being_on_a_video_is_not_a_follow():
    """Sans le garde-fou, « pas sur une vidéo » et « déjà suivi » donneraient la même réponse —
    la sorte de vrai la plus vide qui soit. Le détecteur serait alors juste sur l'inbox."""
    assert _detector(_Screen(on_video=False, follow_button=False)).is_user_followed() is False


def test_an_explicit_marker_still_wins_when_it_exists():
    """L'ancre positive reste en tête : si une version la rend un jour, elle décide sans qu'on
    ait besoin de raisonner sur une absence."""
    screen = _Screen(on_video=False, follow_button=True, followed_marker=True)
    assert _detector(screen).is_user_followed() is True
