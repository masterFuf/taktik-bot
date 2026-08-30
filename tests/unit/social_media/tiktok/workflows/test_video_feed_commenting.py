"""Commenter depuis le fil vidéo — la For You Page et la recherche par hashtag.

La capacité de commentaire est arrivée le 2026-08-30 par la route Followers/Target. Elle y est
restée : `ForYouWorkflow` hérite de `FeedInterruptionsMixin, BaseVideoWorkflow` et **pas** du mixin
d'interaction qui l'avait reçue. La FYP pouvait donc liker, suivre et mettre en favori une vidéo,
mais pas la commenter — alors que Target le faisait, avec un texte écrit par l'IA depuis la légende
à l'écran.

Elle vit maintenant dans `VideoCommentMixin`, dont les DEUX routes héritent. Ce fichier garde les
trois choses que ce déplacement doit préserver :

1. le fil vidéo commente, et respecte sa probabilité et son plafond ;
2. un run qui n'a rien demandé ne commente pas — la probabilité par défaut est zéro, donc un
   payload écrit avant l'existence du bouton se comporte exactement comme avant ;
3. le commentaire est enregistré sous l'AUTEUR de la vidéo. Le mixin lit par défaut
   `_current_profile_username`, que la boucle Followers porte et qu'un fil n'a pas : sans
   redéfinition, le commentaire serait classé sous personne — ou sous le dernier profil qu'un
   autre bout de code a touché.
"""

import pytest

from taktik.core.social_media.tiktok.actions.business.workflows._internal.base_video_workflow import (
    BaseVideoWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_comment import (
    VideoCommentMixin,
)
from taktik.core.social_media.tiktok.actions.business.workflows.followers.interaction import (
    VideoInteractionMixin,
)


class _Config:
    like_probability = 0.0
    follow_probability = 0.0
    favorite_probability = 0.0
    max_likes_per_session = 50
    max_follows_per_session = 20

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Stats:
    videos_liked = 0
    users_followed = 0
    videos_favorited = 0
    videos_commented = 0


class _Feed(BaseVideoWorkflow):
    """Le minimum d'un workflow de fil vidéo, sans device."""

    def __init__(self, **config):
        self.config = _Config(**config)
        self.stats = _Stats()
        self._actions_since_pause = 0
        self.commented = []
        self.logger = type("L", (), {m: (lambda *a, **k: None)
                                     for m in ("info", "debug", "warning", "success", "error")})()

    def _try_comment_video(self, comment_text=None, ai_metadata=None):
        self.commented.append(comment_text)
        return True


def _video(author="keo2edit"):
    return {"author": author, "is_liked": False, "is_favorited": False}


# --- le fil commente ---------------------------------------------------------------------------


def test_the_feed_comments_when_the_run_asked_for_it():
    feed = _Feed(comment_probability=1.0, max_comments_per_session=5)

    feed._decide_and_execute_actions(_video())

    assert feed.stats.videos_commented == 1
    assert feed.commented == [None], "le texte est choisi plus bas, pas ici"


def test_a_run_that_asked_for_nothing_comments_nothing():
    """Le versant qui compte : la probabilité par défaut est zéro, donc un payload écrit avant
    l'existence de ce bouton se comporte exactement comme avant."""
    feed = _Feed()

    feed._decide_and_execute_actions(_video())

    assert feed.stats.videos_commented == 0
    assert feed.commented == []


def test_the_per_session_cap_is_honoured():
    feed = _Feed(comment_probability=1.0, max_comments_per_session=2)

    for _ in range(5):
        feed._decide_and_execute_actions(_video())

    assert feed.stats.videos_commented == 2


def test_a_config_that_never_heard_of_commenting_does_not_raise():
    """Les deux configs de fil ont gagné ces champs après coup. Un objet de config plus ancien —
    sans `comment_probability` ni `max_comments_per_session` — doit traverser la décision sans
    exploser, et sans commenter. C'est pourquoi la branche les lit par `getattr`."""
    feed = _Feed()
    feed.config = type("ConfigDAvant", (), {
        "like_probability": 0.0,
        "follow_probability": 0.0,
        "favorite_probability": 0.0,
        "max_likes_per_session": 1,
        "max_follows_per_session": 1,
    })()

    feed._decide_and_execute_actions(_video())

    assert feed.stats.videos_commented == 0
    assert feed.commented == []


# --- à qui le commentaire est adressé ------------------------------------------------------------


def test_on_a_feed_the_addressee_is_the_video_author():
    feed = _Feed(comment_probability=1.0, max_comments_per_session=1)

    feed._decide_and_execute_actions(_video(author="@charlidamelio"))

    assert feed._comment_target_username() == "charlidamelio"


def test_the_followers_road_keeps_addressing_the_profile_it_walks():
    walker = VideoInteractionMixin()
    walker._current_profile_username = "keo2edit"

    assert walker._comment_target_username() == "keo2edit"


# --- une seule implémentation --------------------------------------------------------------------


def test_both_roads_share_one_implementation():
    """C'est ce qui permet au hook smart-comment de patcher une seule classe et de couvrir les
    deux. Patcher `VideoInteractionMixin` lierait l'attribut sur la sous-classe et laisserait le
    fil exécuter l'original — le hook dirait « installé » sans jamais se déclencher là-bas."""
    assert BaseVideoWorkflow._try_comment_video is VideoCommentMixin._try_comment_video
    assert VideoInteractionMixin._try_comment_video is VideoCommentMixin._try_comment_video


@pytest.mark.parametrize("host", [BaseVideoWorkflow, VideoInteractionMixin])
def test_every_road_carries_the_whole_capability(host):
    for method in ("_try_comment_video", "_comment_actions",
                   "_pick_configured_comment", "_record_posted_comment"):
        assert hasattr(host, method), f"{host.__name__} n'a pas {method}"
