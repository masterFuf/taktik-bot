"""Engager les commentateurs d'une vidéo, atteinte par son lien.

Instagram engage les gens qui ont AIMÉ un post. TikTok n'affiche nulle part qui a aimé une vidéo,
donc l'audience lisible d'un post est celle qui a COMMENTÉ — même question, par la porte que
l'app laisse ouverte.

Ce que ce fichier verrouille est presque entièrement le **refus** et la **provenance**, parce que
tout ce qui vient après « qui sont ces gens ? » est le chemin de production hérité, et le
respeller ici en ferait une seconde vérité.

Le piège que ces tests auraient attrapé : j'avais appelé `read_commenter_handles` sur
`self.click`, l'agrégat que le workflow porte. Le lecteur vit sur `CommentActions`. Le premier run
réel aurait levé, après avoir ouvert la vidéo.
"""

import pytest

from taktik.core.social_media.tiktok.actions.business.workflows.post_url import (
    PostUrlConfig,
    PostUrlWorkflow,
)


class _Workflow(PostUrlWorkflow):
    """Le vrai `_resolve_targets`, sur un double d'appareil.

    Rien n'est réécrit : seules les deux dépendances externes — l'ouverture du lien et la lecture
    de la feuille — sont remplacées, parce qu'elles touchent un téléphone.
    """

    def __init__(self, config, *, opens=True, rows=None, raises=False):
        self.config = config
        self.opened = []
        self._opens = opens
        self._rows = rows or []
        self._raises = raises
        self.device = object()
        self.device_id = "SERIAL"

        class _Log:
            def __getattr__(self, _):
                return lambda *a, **k: None
        self.logger = _Log()


def _resolve(config, *, opens=True, rows=None, raises=False):
    """Rejoue `_resolve_targets` en remplaçant l'appareil, jamais la logique."""
    import taktik.core.social_media.tiktok.actions.business.workflows.post_url.workflow as module
    import taktik.core.social_media.tiktok.actions.atomic.interaction.comment_actions as comments

    wf = _Workflow(config, opens=opens, rows=rows, raises=raises)
    original_open = module.open_post_by_url
    original_cls = comments.CommentActions

    class _Comments:
        def __init__(self, _device):
            pass

        def read_commenter_handles(self, max_commenters=20, *, max_scrolls=8):
            if raises:
                raise RuntimeError("la feuille n'a pas voulu s'ouvrir")
            return (rows or [])[:max_commenters]

    module.open_post_by_url = lambda device, url, device_id="": bool(opens)
    comments.CommentActions = _Comments
    try:
        return PostUrlWorkflow._resolve_targets(wf)
    finally:
        module.open_post_by_url = original_open
        comments.CommentActions = original_cls


# --- ce qu'on refuse de faire ---------------------------------------------------------------


def test_no_link_means_no_run():
    assert _resolve(PostUrlConfig(post_url="")) == []


def test_a_link_that_does_not_open_yields_nobody():
    """Ce refus est le plus important du fichier. Si l'ouverture n'est pas prouvée, la feuille de
    commentaires lue est celle de l'écran où TikTok nous a laissés — et on classerait l'audience
    d'un inconnu sous ce post."""
    assert _resolve(PostUrlConfig(post_url="https://vm.tiktok.com/xyz/"), opens=False) == []


def test_a_comment_sheet_that_raises_does_not_take_the_run_down():
    resolved = _resolve(PostUrlConfig(post_url="https://vm.tiktok.com/xyz/"), raises=True)

    assert resolved == []


def test_a_video_with_no_comments_is_not_an_error():
    assert _resolve(PostUrlConfig(post_url="https://vm.tiktok.com/xyz/"), rows=[]) == []


def test_rows_without_a_handle_are_dropped():
    """Une ligne de commentaire ne porte qu'un nom d'affichage ; quand la résolution du pseudo
    échoue, le champ revient vide. Le garder ferait visiter « @ »."""
    rows = [{"username": "", "display_name": "Lau"},
            {"username": None, "display_name": "vic"},
            {"username": "  ", "display_name": "x"}]

    assert _resolve(PostUrlConfig(post_url="u"), rows=rows) == []


# --- la provenance des pseudos -----------------------------------------------------------------


def test_the_handles_come_from_the_comment_sheet():
    rows = [{"username": "secretdrxx"}, {"username": "@laurie_bouchardd"}]

    assert _resolve(PostUrlConfig(post_url="u"), rows=rows) == ["secretdrxx", "laurie_bouchardd"]


def test_the_same_person_commenting_twice_is_visited_once():
    """Quelqu'un qui commente trois fois est une personne, pas trois cibles — et le budget de
    profils se dépenserait trois fois sur elle."""
    rows = [{"username": "vic961226"}, {"username": "VIC961226"}, {"username": "@vic961226"}]

    assert _resolve(PostUrlConfig(post_url="u"), rows=rows) == ["vic961226"]


def test_the_resolved_list_is_handed_to_the_inherited_loop():
    """La boucle héritée lit `config.usernames` : sans cette écriture, le workflow ouvrirait la
    vidéo, lirait les pseudos, et ne visiterait personne."""
    config = PostUrlConfig(post_url="u")
    rows = [{"username": "a"}, {"username": "b"}]

    _resolve(config, rows=rows)

    assert config.usernames == ["a", "b"]


def test_the_commenter_budget_is_honoured():
    """Chaque pseudo coûte l'ouverture d'un profil (~13 s). Le plafond doit mordre AVANT la
    dépense, pas après."""
    config = PostUrlConfig(post_url="u", max_commenters=2)
    rows = [{"username": f"u{i}"} for i in range(9)]

    assert _resolve(config, rows=rows) == ["u0", "u1"]


# --- ce que la config promet --------------------------------------------------------------------


def test_the_config_keeps_the_inherited_budgets():
    """Elle hérite de la config des profils cibles, donc toutes les limites de session, les
    probabilités et les filtres continuent d'etre lus au meme endroit."""
    config = PostUrlConfig(post_url="u")

    assert hasattr(config, "max_followers")
    assert hasattr(config, "like_probability")
    assert config.usernames == []


@pytest.mark.parametrize("champ,attendu", [
    ("FILTER_SOURCE_TYPE", "post_commenters"),
    ("MODULE_NAME", "tiktok-post-url-workflow"),
])
def test_a_rejected_profile_is_filed_under_this_workflow(champ, attendu):
    """Trois workflows écrivent dans `filtered_profiles`. Les confondre rend les stats de rejet
    illisibles : un profil écarté ici ne venait ni des abonnés de quelqu'un ni d'une liste choisie."""
    assert getattr(PostUrlWorkflow, champ) == attendu
