"""Le verdict IA d'un profil TikTok — et la capture sans laquelle il n'existe pas.

Le double de device de ce fichier exposait `screenshot_pil()`, la forme de la FACADE. La
production n'en passe jamais une : `DeviceManager.device` est le device uiautomator2 **brut**
(`u2.connect(...)`), qui n'a pas cette méthode. Chaque analyse de profil TikTok mourait donc sur
`'Device' object has no attribute 'screenshot_pil'`, avalé en avertissement pendant que le run
continuait — et ces tests restaient verts parce qu'ils testaient une forme que personne ne
fournit. C'est toute la raison pour laquelle `profile_qualification` ne contenait aucune ligne
TikTok : pas un tuyau manquant, une capture manquante.

Le double reproduit maintenant la forme RÉELLE, et un test dédié garde la façade, pour que le
lecteur marche sur les deux.
"""

from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
    build_tiktok_profile_qualifier,
    qualify_tiktok_profile,
)


class _FakeImage:
    """Une PIL.Image, vue par le lecteur partage : il verifie `crop` pour distinguer une vraie
    image d'un retour vide, donc un double sans `crop` ne franchit pas la porte."""

    def __init__(self, saved):
        self._saved = saved

    def save(self, path, format=None):  # noqa: A002 - PIL's own keyword
        self._saved.append((path, format))

    def crop(self, box):
        return self


class _FakeDevice:
    """Le device uiautomator2 BRUT, tel que les workflows TikTok le recoivent."""

    def __init__(self, image=None):
        self.image = image
        self.saved = []

    def screenshot(self, *args, **kwargs):
        if args or kwargs:            # u2 accepte screenshot(format=...)
            raise TypeError("unsupported")
        return _FakeImage(self.saved) if self.image is None else self.image


class _FakeFacadeDevice:
    """La facade du projet, qui expose le device brut sous `_device`."""

    def __init__(self):
        self._device = _FakeDevice()


class _FakeAI:
    def __init__(self, classification):
        self.classification = classification
        self.calls = []

    def classify_profile_niche(self, **kwargs):
        self.calls.append(kwargs)
        return {"classification": self.classification}


def _engagement(**overrides):
    base = {"relevant": True, "score": 0.82, "reason": "same niche", "follow": True,
            "comment": False, "like": True}
    base.update(overrides)
    return base


def test_a_profile_verdict_is_returned_and_its_niche_is_persisted():
    """The vision call buys two things and the niche is the reusable one.

    Would have caught the extraction losing `emit_classification` and making TikTok pay for the
    same profile on every pass — which is exactly what it did before the hook gained it.
    """
    ai = _FakeAI({"niche": "fitness", "niche_category": "sport", "engagement": _engagement()})
    persisted = []
    surfaced = []

    verdict = qualify_tiktok_profile(
        ai,
        _FakeDevice(),
        "creator",
        account_niche="fitness",
        language="fr",
        emit_classification=lambda username, classification: persisted.append((username, classification)),
        emit_relevance=lambda username, payload: surfaced.append((username, payload)),
    )

    assert verdict["relevant"] is True
    assert verdict["score"] == 0.82
    assert persisted[0][0] == "creator"
    assert surfaced[0][1]["follow"] is True
    assert ai.calls[0]["platform"] == "tiktok"
    assert ai.calls[0]["account_niche"] == "fitness"
    assert ai.calls[0]["response_language"] == "fr"


def test_a_screen_that_could_not_be_captured_yields_no_verdict_at_all():
    """Would have caught a black or missing screenshot producing a confident qualification —
    the failure that once wrote a niche onto 310 profiles from a blank frame."""

    class _NoScreenshot:
        def screenshot(self, *args, **kwargs):
            return None

    ai = _FakeAI({"engagement": _engagement()})

    assert qualify_tiktok_profile(ai, _NoScreenshot(), "creator") is None
    assert ai.calls == []


def test_a_classification_without_an_engagement_block_is_not_a_verdict():
    """Would have caught `{}` being read as "not relevant" instead of "the model did not answer"."""
    ai = _FakeAI({"niche": "fitness"})

    assert qualify_tiktok_profile(ai, _FakeDevice(), "creator") is None


def test_a_provider_error_yields_no_verdict_instead_of_raising_into_the_run():
    class _BoomAI:
        def classify_profile_niche(self, **kwargs):
            raise RuntimeError("provider 502")

    assert qualify_tiktok_profile(_BoomAI(), _FakeDevice(), "creator") is None


def test_a_persistence_callback_that_raises_does_not_lose_the_verdict():
    """The niche write is a side effect; losing it must not also lose the decision it came with."""
    ai = _FakeAI({"niche": "fitness", "engagement": _engagement()})

    def boom(_username, _classification):
        raise RuntimeError("desktop pipe closed")

    verdict = qualify_tiktok_profile(ai, _FakeDevice(), "creator", emit_classification=boom)

    assert verdict is not None
    assert verdict["relevant"] is True


def test_the_qualifier_binds_the_account_niche_once_for_every_profile_it_judges():
    """Would have caught the second consumer of this call forgetting the account niche and
    judging every profile against a generic "good target?" question."""
    ai = _FakeAI({"engagement": _engagement()})
    qualify = build_tiktok_profile_qualifier(
        ai,
        {"accountNiche": "fitness", "accountSubNiche": "crossfit"},
        language="fr",
    )

    qualify(_FakeDevice(), "one")
    qualify(_FakeDevice(), "two")

    assert [call["username"] for call in ai.calls] == ["one", "two"]
    assert {call["account_niche"] for call in ai.calls} == {"fitness"}
    assert {call["account_sub_niche"] for call in ai.calls} == {"crossfit"}


def test_the_raw_device_is_the_shape_production_actually_passes():
    """La garde qui manquait. Un double qui expose `screenshot_pil` teste la facade ; le bot
    passe le device brut, et c'est la difference qui a coute toutes les qualifications TikTok."""
    ai = _FakeAI({"niche": "fitness", "engagement": _engagement()})

    assert qualify_tiktok_profile(ai, _FakeDevice(), "creator") is not None
    assert ai.calls[0]["platform"] == "tiktok"


def test_a_facade_still_works_through_the_same_reader():
    """Les deux formes circulent selon l'appelant : le Lab construit une facade, les workflows
    recoivent le device brut. Le lecteur partage doit repondre aux deux."""
    ai = _FakeAI({"niche": "fitness", "engagement": _engagement()})

    assert qualify_tiktok_profile(ai, _FakeFacadeDevice(), "creator") is not None
