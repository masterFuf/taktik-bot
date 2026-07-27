"""Boucle de follow de masse depuis l'ecran Discover people.

Le parsing est verrouille ailleurs (`test_feed_suggestions_parsing`). Ici on
verrouille le GESTE : sur quelles bounds le doigt part-il vraiment, et quelle
comptabilite est ecrite. La regle metier de Kevin — ni follow-back, ni demande
de suivi depuis ce mode — doit tenir au niveau du tap, pas seulement du filtre.

Le mixin est monte sur un harnais minimal : un faux device qui sert des dumps
canned et enregistre les taps, plus les quelques primitives que le mixin attend
de `BaseBusinessAction`.
"""

import logging

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions import (
    FeedSuggestionsMixin,
)


IG = "com.instagram.android:id"


def _row(top, name, button_text):
    bottom = top + 220
    return f"""
      <node resource-id="{IG}/recommended_user_row_content_identifier" bounds="[0,{top}][1080,{bottom}]">
        <node resource-id="{IG}/row_recommended_user_username" text="{name}"
              bounds="[231,{top + 52}][620,{top + 102}]"/>
        <node resource-id="{IG}/row_recommended_social_context" text="1 mutual"
              bounds="[297,{top + 119}][425,{top + 161}]"/>
        <node resource-id="{IG}/row_recommended_user_follow_button" text="{button_text}"
              content-desc="{button_text}" bounds="[653,{top + 66}][959,{top + 154}]"/>
      </node>"""


def _screen(rows):
    body = "".join(_row(top, name, state) for top, name, state in rows)
    return f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>{body}</hierarchy>"


# Ecran 1 : un follow-back, un follow, un deja-suivi.
SCREEN_MIXED = _screen([
    (400, "Known Follower", "Follow back"),
    (620, "Fresh Account", "Follow"),
    (840, "Already Followed", "Following"),
])
# Ecran 2 : le meme, une fois "Fresh Account" suivi (bascule du bouton).
SCREEN_AFTER_FOLLOW = _screen([
    (400, "Known Follower", "Follow back"),
    (620, "Fresh Account", "Following"),
    (840, "Already Followed", "Following"),
])
EMPTY_SCREEN = "<?xml version='1.0' encoding='UTF-8'?><hierarchy></hierarchy>"


class _FakeDevice:
    """Device minimal : sert les dumps dans l'ordre, enregistre taps et scrolls."""

    def __init__(self, dumps):
        self._dumps = list(dumps)
        self.taps = []
        self.scrolls = 0

    def dump_hierarchy(self, compressed=False):
        return self._dumps.pop(0) if len(self._dumps) > 1 else self._dumps[0]

    def human_tap(self, bounds):
        self.taps.append(tuple(bounds))
        return (bounds[0], bounds[1])

    def human_scroll(self, direction="down", distance_ratio=None):
        self.scrolls += 1
        return True


class _Harness(FeedSuggestionsMixin):
    """Le mixin de production + les primitives que lui fournit BaseBusinessAction."""

    def __init__(self, device):
        self.device = device
        self.logger = logging.getLogger("test-suggestions")
        self.session_manager = None
        self.recorded = []
        self.live_counts = []

    def _human_like_delay(self, action_type="general"):
        return None

    def _human_tap_element(self, element):
        """Comme en prod : False quand les bounds sont illisibles, l'appelant
        retombe alors sur un `click()` au centre."""
        try:
            element.get(timeout=0.5)
        except Exception:
            return False
        return True

    def _count_live(self, stat_name, value=1):
        self.live_counts.append((stat_name, value))

    def _record_action(self, username, action_type, count=1, timestamps=None, content=None):
        self.recorded.append({"username": username, "action": action_type, "content": content})
        return True


@pytest.fixture
def no_pacing(monkeypatch):
    """Neutralise la cadence humaine pour que le test reste instantane."""
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions.time.sleep",
        lambda _s: None,
    )


def test_only_the_plain_follow_row_is_tapped(no_pacing):
    device = _FakeDevice([SCREEN_MIXED, SCREEN_AFTER_FOLLOW])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=1)

    # Un seul tap, sur les bounds du bouton de "Fresh Account" (top=620 -> 620+66/620+154).
    assert device.taps == [(653, 686, 959, 774)]
    assert result["follows"] == 1
    # Le follow-back a ete vu et compte, jamais tape.
    assert result["skipped_follow_back"] == 1


def test_a_follow_is_booked_like_the_interaction_engine(no_pacing):
    device = _FakeDevice([SCREEN_MIXED, SCREEN_AFTER_FOLLOW])
    harness = _Harness(device)

    harness.follow_discover_suggestions(max_follows=1, delay_range=(0, 0), max_scrolls=1)

    assert harness.live_counts == [("follows", 1)]
    assert len(harness.recorded) == 1
    entry = harness.recorded[0]
    assert entry["username"] == "Fresh Account"
    assert entry["action"] == "FOLLOW"
    # La provenance est ecrite : sans elle la ligne DB se lit comme un follow anonyme.
    assert "Suggestion" in (entry["content"] or "")


def test_an_unchanged_button_is_not_counted_as_a_follow(no_pacing):
    """Le tap n'a pas pris : la ligne est toujours proposable, donc rien n'est comptabilise."""
    device = _FakeDevice([SCREEN_MIXED, SCREEN_MIXED])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=1, delay_range=(0, 0), max_scrolls=0)

    assert device.taps, "le bouton a bien ete tape"
    assert result["follows"] == 0
    assert harness.recorded == []
    assert harness.live_counts == []


def test_an_empty_list_stops_instead_of_scrolling_forever(no_pacing):
    device = _FakeDevice([EMPTY_SCREEN])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=30)

    assert result["follows"] == 0
    assert result["stop_reason"] == "list_exhausted"
    # On s'arrete sur la fin de liste, pas sur le plafond de scrolls.
    assert device.scrolls < 30


def test_a_screen_full_of_follow_backs_keeps_scrolling(no_pacing):
    """Une liste aligne des ecrans entiers de 'Follow back' avant la section suivante :
    l'absence de candidat ne doit pas se lire comme une fin de liste."""
    only_follow_backs = _screen([(400, "A", "Follow back"), (620, "B", "Follow back")])
    device = _FakeDevice([only_follow_backs])
    harness = _Harness(device)

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=4)

    assert result["stop_reason"] == "max_scrolls"
    assert device.scrolls == 4
    assert device.taps == []


FEED_WITH_CAROUSEL = (
    f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
    f"<node resource-id='{IG}/netego_carousel_container_view' bounds='[0,1150][1080,1967]'>"
    f"<node resource-id='{IG}/netego_carousel_cta' text='See all' bounds='[880,1172][1036,1222]'/>"
    f"</node></hierarchy>"
)
FEED_PLAIN = (
    f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
    f"<node resource-id='{IG}/row_feed_button_like' bounds='[33,875][99,1002]'/>"
    f"</hierarchy>"
)


class _XPathDevice(_FakeDevice):
    """Ajoute le `xpath(...).exists` que la sonde legere du carousel utilise.

    Chaque scroll fait avancer l'ecran courant, comme sur un vrai feed : la sonde
    ne voit donc le carousel qu'apres le bon nombre de gestes.
    """

    def human_scroll(self, direction="down", distance_ratio=None):
        if len(self._dumps) > 1:
            self._dumps.pop(0)
        return super().human_scroll(direction, distance_ratio)

    def xpath(self, selector):
        current = self._dumps[0] if self._dumps else ""
        present = "netego_carousel_cta" in selector and "netego_carousel_cta" in current
        return type("_El", (), {"exists": present})()


def test_the_carousel_search_scrolls_without_engaging(no_pacing):
    """Mode suggestions seules : on scrolle pour ATTEINDRE le bloc, sans rien liker."""
    device = _XPathDevice([FEED_PLAIN, FEED_PLAIN, FEED_WITH_CAROUSEL])
    harness = _Harness(device)

    res = harness.find_feed_suggestions_carousel(max_scrolls=6)

    assert res["found"] is True
    assert res["scrolls"] == 2
    # Aucun tap : chercher le carousel n'engage rien.
    assert device.taps == []


def test_the_carousel_search_gives_up_on_its_scroll_budget(no_pacing):
    device = _XPathDevice([FEED_PLAIN])
    harness = _Harness(device)

    res = harness.find_feed_suggestions_carousel(max_scrolls=4)

    assert res["found"] is False
    assert res["scrolls"] == 4
    assert device.scrolls == 4


def test_suggestions_only_stops_when_no_carousel_shows_up(no_pacing):
    device = _XPathDevice([FEED_PLAIN])
    harness = _Harness(device)

    res = harness.run_suggestions_only({"max_suggestion_passes": 1, "max_carousel_scrolls": 3})

    assert res["follows"] == 0
    assert res["passes"] == 0
    assert res["stop_reason"] == "carousel_not_found"
    assert device.taps == []


DISCOVER_WITH_BACK_ARROW = (
    f"<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
    f"<node resource-id='{IG}/action_bar_button_back' content-desc='Back' clickable='true'"
    f" bounds='[0,77][154,231]'/>"
    f"{_row(400, 'Someone', 'Follow back')}"
    f"</hierarchy>"
)


class _BackDevice(_FakeDevice):
    """Ecran Discover people qui IGNORE la touche back, comme le vrai (QA 2026-07-26).

    L'ecran courant ne change que sur une action reelle : le dump ne le consomme
    pas, seul un tap sur la fleche fait avancer.
    """

    def __init__(self, screens, arrow_works=True):
        super().__init__(screens)
        self.arrow_works = arrow_works
        self.back_keys = 0
        self.arrow_taps = 0

    @property
    def screen(self):
        return self._dumps[0]

    def dump_hierarchy(self, compressed=False):
        return self.screen

    def press(self, key):
        self.back_keys += 1  # sans effet : l'ecran ne bouge pas
        return True

    def xpath(self, selector):
        device = self

        class _El:
            exists = ("action_bar_button_back" in selector
                      and "action_bar_button_back" in device.screen)

            @staticmethod
            def get(timeout=0.5):
                raise RuntimeError("bounds unreadable")  # force le repli click()

            @staticmethod
            def click():
                device.arrow_taps += 1
                if device.arrow_works and len(device._dumps) > 1:
                    device._dumps.pop(0)

        return _El()


class _NavActions:
    def __init__(self):
        self.calls = 0

    def navigate_to_home(self):
        self.calls += 1
        return True


def test_leaving_the_suggestions_screen_uses_the_action_bar_arrow(no_pacing):
    """QA device : cet ecran n'a pas de barre d'onglets et ignore le back materiel.
    Le retour doit passer par la fleche de la barre d'action, pas par la touche."""
    device = _BackDevice([DISCOVER_WITH_BACK_ARROW, FEED_PLAIN])
    harness = _Harness(device)
    harness.nav_actions = _NavActions()

    assert harness._return_to_feed() is True
    assert device.arrow_taps == 1
    assert device.back_keys == 0, "la touche back ne doit pas etre le premier essai"
    assert harness.nav_actions.calls == 1


def test_a_stuck_suggestions_screen_is_reported_not_swallowed(no_pacing):
    """Si l'ecran ne se quitte pas, le run doit le DIRE plutot que de croire etre revenu."""
    device = _BackDevice([DISCOVER_WITH_BACK_ARROW, FEED_PLAIN], arrow_works=False)
    harness = _Harness(device)
    harness.nav_actions = _NavActions()

    assert harness._return_to_feed() is False
    assert harness.nav_actions.calls == 0, "on ne cherche pas l'accueil si on n'a pas quitte l'ecran"


def test_the_session_limit_stops_the_loop(no_pacing):
    class _Session:
        def should_continue(self):
            return False, "Follows limit reached (10/10)"

    device = _FakeDevice([SCREEN_MIXED])
    harness = _Harness(device)
    harness.session_manager = _Session()

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=2)

    assert result["stop_reason"] == "session_limit"
    assert device.taps == []


def test_the_daily_follow_quota_stops_the_loop(no_pacing):
    """Garde-fou de montee en charge : `max_follows_per_day` n'est PAS un motif d'arret
    de session, il desactive sa propre intention. Le moteur d'interaction le lit pour
    chaque profil — un chemin que ce mode ne traverse pas, il doit donc le lire lui-meme."""
    class _Session:
        def should_continue(self):
            return True, ""

        def exhausted_daily_quotas(self):
            return {'follow'}

    device = _FakeDevice([SCREEN_MIXED])
    harness = _Harness(device)
    harness.session_manager = _Session()

    result = harness.follow_discover_suggestions(max_follows=5, delay_range=(0, 0), max_scrolls=2)

    assert result["stop_reason"] == "session_limit"
    assert device.taps == [], "aucun follow ne part quand le budget du jour est consomme"


def test_a_spent_comment_quota_does_not_block_follows(no_pacing):
    """Seul le quota de FOLLOW nous concerne : un quota de commentaires consomme
    ne doit pas arreter une passe de suggestions."""
    class _Session:
        def should_continue(self):
            return True, ""

        def exhausted_daily_quotas(self):
            return {'comment'}

    device = _FakeDevice([SCREEN_MIXED, SCREEN_AFTER_FOLLOW])
    harness = _Harness(device)
    harness.session_manager = _Session()

    result = harness.follow_discover_suggestions(max_follows=1, delay_range=(0, 0), max_scrolls=1)

    assert result["follows"] == 1
