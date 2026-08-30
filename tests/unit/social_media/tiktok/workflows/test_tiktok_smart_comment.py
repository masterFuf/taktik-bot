"""Commenter une vidéo TikTok — et surtout, ne pas commenter.

Deux trous refermés le 2026-08-30.

Le premier : la branche commentaire du workflow était `# TODO: Implement commenting` suivi d'un
`pass`. La probabilité et le plafond par session étaient tous deux lus et honorés — un run réglé
pour commenter 30 % du temps tirait le dé, décidait oui, ne faisait rien, et rapportait zéro
commentaire comme si le dé avait dit non. La config du bridge ne transmettait ni la probabilité
ni les textes, donc même une fois la branche écrite elle n'aurait rien eu à poster.

Le second : le smart comment n'existait pas côté TikTok, faute des actions d'écriture — livrées
depuis. Les trois décisions AUTOUR de la génération (quelle langue, est-ce un refus, qu'a dit ce
compte récemment) sont les décisions **partagées**, extraites du hook Instagram sans les modifier,
pour que les deux plateformes posent les mêmes questions.

Ce que ces tests gardent surtout, c'est le **silence** : `None` est une décision de ne rien dire,
jamais une raison de retomber sur un texte générique. Une ligne passe-partout sous la vidéo d'un
inconnu est la signature de bot la plus reconnaissable qui soit.
"""

import pytest

from taktik.core.social_media.tiktok.workflows.core.ai_hooks import generate_tiktok_comment


@pytest.fixture(autouse=True)
def _no_production_database(monkeypatch):
    """Aucun test de ce fichier ne touche la base de production. Les DEUX sens comptent.

    La lecture d'abord : le garde anti-tic lit `posted_comments` en best-effort, donc sans ceci
    chaque test ouvre la vraie base pour y lire douze lignes.

    L'écriture ensuite, et c'est celle qui a mordu : `_try_comment_video` enregistre ce qu'il
    publie, et la première version de cette fixture ne neutralisait que la lecture. Six lignes
    « Excellent ! » et « Le texte de l'opérateur » se sont retrouvées dans la base de Kevin,
    sous @keo2edit, à l'heure exacte des trois passages de la suite — supprimées depuis. Un test
    qui écrit dans la base de production ne salit pas seulement les données : il aurait aussi
    nourri le garde anti-tic avec des phrases que personne n'a jamais publiées.
    """
    monkeypatch.setattr(
        "taktik.core.database.instagram_posted_comments.InstagramPostedComments.recent_texts",
        staticmethod(lambda account_id=None, limit=12, platform="instagram": []),
    )
    monkeypatch.setattr(
        "taktik.core.database.instagram_posted_comments.InstagramPostedComments.record",
        staticmethod(lambda **kwargs: None),
    )


class _FakeImage:
    def save(self, path, format=None):  # noqa: A002 - PIL's own keyword
        return None

    def crop(self, box):
        return self


class _Screen:
    """Un device brut, avec une légende qu'on choisit."""

    def __init__(self, caption=None, capture=True):
        self.caption = caption
        self.capture = capture

    def screenshot(self, *args, **kwargs):
        if args or kwargs:
            raise TypeError("unsupported")
        return _FakeImage() if self.capture else None

    def xpath(self, selector):
        caption = self.caption
        found = [_Node(caption)] if (caption and "desc" in selector) else []

        class _Query:
            @staticmethod
            def all():
                return found

        return _Query()


class _Node:
    def __init__(self, text):
        self.text = text


class _FakeAI:
    def __init__(self, comment="Super montage, la transition à 0:12 est propre", **extra):
        self.payload = {"success": True, "comment": comment, **extra}
        self.calls = []

    def generate_smart_comment(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


PERSONA = {"niche": "Business en ligne pour créateurs", "language": "fr"}


# --- ce qui se publie ---------------------------------------------------------------------------


def test_a_comment_is_generated_from_the_caption_on_screen():
    ai = _FakeAI()
    comment = generate_tiktok_comment(
        ai, _Screen("Le secret de ma réussite en bio"), "keo2edit", account_persona=PERSONA
    )

    assert comment["comment"] == "Super montage, la transition à 0:12 est propre"
    assert comment["language"] == "fr", "l'enregistrement doit porter la langue du COMMENTAIRE"
    assert comment["post_caption"] == "Le secret de ma réussite en bio"
    assert ai.calls[0]["platform"] == "tiktok"
    assert ai.calls[0]["post_caption"] == "Le secret de ma réussite en bio"
    assert ai.calls[0]["language"] == "fr"


def test_the_anti_tic_guard_reads_tiktok_history_not_instagram():
    """Le garde anti-tic montre au modèle ce que CE compte vient de publier. Lire l'historique
    Instagram lui montrerait la voix d'une autre plateforme."""
    import taktik.core.database.instagram_posted_comments as module

    seen = {}
    original = module.InstagramPostedComments.recent_texts
    module.InstagramPostedComments.recent_texts = staticmethod(
        lambda account_id=None, limit=12, platform="instagram": seen.setdefault("platform", platform) or []
    )
    try:
        generate_tiktok_comment(_FakeAI(), _Screen("une légende"), "keo2edit", account_persona=PERSONA)
    finally:
        module.InstagramPostedComments.recent_texts = original

    assert seen["platform"] == "tiktok"


# --- ce qui ne se publie PAS --------------------------------------------------------------------


def test_nothing_to_react_to_means_no_comment():
    """Ni légende ni capture : il n'y a rien à commenter, et l'appel IA n'est pas payé."""
    ai = _FakeAI()

    assert generate_tiktok_comment(ai, _Screen(None, capture=False), "keo2edit") is None
    assert ai.calls == []


def test_an_english_caption_is_answered_in_english():
    """La regle partagee : {langue du compte, anglais}. L'anglais est toujours admis."""
    ai = _FakeAI()
    caption = "This is the secret of my success, the full video is on my profile"

    assert generate_tiktok_comment(ai, _Screen(caption), "someone", account_persona=PERSONA)
    assert ai.calls[0]["language"] == "en"


def test_an_undetected_caption_falls_back_to_the_account_language():
    """Et voila jusqu'ou va vraiment le garde. `detect_text_language` repond `fr`, `en` ou None —
    None pour TOUTE autre langue, par conception. Mesure le 2026-08-30 : une legende espagnole
    revient None, donc elle prend la branche « non detectee » et recoit un commentaire dans la
    langue du compte, ici en francais. La branche « langue etrangere -> on se tait » est ecrite
    pour un detecteur qui en connait davantage ; elle ne peut pas se declencher aujourd'hui.
    Ce test fige le comportement REEL pour que personne ne lise la regle comme une protection
    deja acquise — l'elargissement du detecteur est une decision, pas un rangement."""
    ai = _FakeAI()
    caption = "Este es el secreto de mi exito, mira el video completo en mi perfil ahora mismo"

    assert generate_tiktok_comment(ai, _Screen(caption), "alguien", account_persona=PERSONA)
    assert ai.calls[0]["language"] == "fr"


def test_an_apology_is_not_a_comment():
    """Un modele de vision qui n'a pas vu la video repond par une excuse. La publier annonce a
    voix haute qu'une machine ecrit."""
    ai = _FakeAI(comment="I can't see the image, but here is what I would say")

    assert generate_tiktok_comment(ai, _Screen("une légende"), "keo2edit", account_persona=PERSONA) is None


def test_a_paragraph_is_not_a_comment_either():
    """L'autre moitie du meme garde : le modele poli qui ne dit pas qu'il n'a pas vu, et ecrit
    un paragraphe sur ce qu'il dirait."""
    ai = _FakeAI(comment="Voici " + "un commentaire tres long " * 12)

    assert generate_tiktok_comment(ai, _Screen("une légende"), "keo2edit", account_persona=PERSONA) is None


def test_decision_mode_can_decline_a_video():
    ai = _FakeAI(should_comment=False, reasoning="vidéo promotionnelle")

    assert generate_tiktok_comment(
        ai, _Screen("une légende"), "keo2edit", account_persona=PERSONA, decision_mode=True
    ) is None


def test_a_provider_error_stays_silent_instead_of_raising_into_the_run():
    class _BoomAI:
        def generate_smart_comment(self, **kwargs):
            raise RuntimeError("provider 502")

    assert generate_tiktok_comment(_BoomAI(), _Screen("une légende"), "keo2edit") is None


# --- la couture du workflow ----------------------------------------------------------------------


class _Workflow:
    """Le minimum du mixin d'interaction pour interroger la couture."""

    def __init__(self, texts=(), sheet_opens=True, posts=True):
        from taktik.core.social_media.tiktok.actions.business.workflows.followers.interaction import (
            VideoInteractionMixin,
        )

        self.__class__ = type("_W", (VideoInteractionMixin,), {})
        self.config = type("C", (), {"comment_texts": list(texts)})()
        self.device = object()
        self._current_profile_username = "keo2edit"
        self.posted = []
        self.logger = type("L", (), {"info": lambda *a: None, "debug": lambda *a: None,
                                     "warning": lambda *a: None})()
        self._comment_actions_instance = _Sheet(self, sheet_opens, posts)


class _Sheet:
    def __init__(self, workflow, opens, posts):
        self.workflow, self.opens, self.posts = workflow, opens, posts
        self.closed = False

    def open_comments(self):
        return self.opens

    def post_comment(self, text):
        self.workflow.posted.append(text)
        return self.posts

    def close_comments(self):
        self.closed = True
        return True


def test_a_run_with_no_comment_texts_posts_nothing():
    """Pas de liste par defaut : un run qui n'a rien configure ne doit pas inventer un « Nice! »."""
    workflow = _Workflow(texts=())

    assert workflow._try_comment_video() is False
    assert workflow.posted == []


def test_a_configured_text_is_published_and_the_sheet_is_closed():
    workflow = _Workflow(texts=["Excellent !"])

    assert workflow._try_comment_video() is True
    assert workflow.posted == ["Excellent !"]
    assert workflow._comment_actions_instance.closed, (
        "une feuille laissee ouverte cache la video suivante, et le swipe ferait defiler les "
        "commentaires a la place"
    )


def test_a_sheet_that_never_opens_is_not_a_posted_comment():
    workflow = _Workflow(texts=["Excellent !"], sheet_opens=False)

    assert workflow._try_comment_video() is False
    assert workflow.posted == []


def test_the_sheet_is_closed_even_when_posting_fails():
    workflow = _Workflow(texts=["Excellent !"], posts=False)

    assert workflow._try_comment_video() is False
    assert workflow._comment_actions_instance.closed


@pytest.mark.parametrize("given", ["Le texte de l'opérateur"])
def test_an_explicit_text_is_published_verbatim(given):
    workflow = _Workflow(texts=["autre chose"])

    assert workflow._try_comment_video(given) is True
    assert workflow.posted == [given]
