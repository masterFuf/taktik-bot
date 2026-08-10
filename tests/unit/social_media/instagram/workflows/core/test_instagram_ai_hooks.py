from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_DETAIL_SELECTORS,
)
import pytest

from taktik.core.shared.text import detect_text_language
from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
    crop_screenshot_to_post,
    install_instagram_ai_hooks,
    _load_cached_qualification,
    _resolve_comment_language,
)


class FakeElement:
    def __init__(self, exists, bounds=None):
        self.exists = exists
        self.info = {"bounds": bounds or {}}


class FakeDevice:
    def __init__(self, elements):
        self.elements = elements

    def xpath(self, selector):
        return self.elements.get(selector, FakeElement(False))


class FakeImage:
    size = (100, 200)

    def __init__(self):
        self.crop_box = None

    def crop(self, box):
        cropped = FakeImage()
        cropped.crop_box = box
        return cropped


def test_crop_screenshot_to_post_uses_post_selector_catalogs():
    image = FakeImage()
    device = FakeDevice(
        {
            POST_DETAIL_SELECTORS.ai_crop_header_selectors[0]: FakeElement(
                True,
                {"top": 40},
            ),
            POST_DETAIL_SELECTORS.ai_crop_button_row_selectors[0]: FakeElement(
                True,
                {"bottom": 150},
            ),
        }
    )

    cropped = crop_screenshot_to_post(image, device)

    assert cropped.crop_box == (0, 32, 100, 156)


def test_install_ai_hooks_without_device_is_noop_and_logs_warning():
    logs = []

    install_instagram_ai_hooks(
        ai=object(),
        ai_config={"smartComments": True},
        device=None,
        log=lambda level, message: logs.append((level, message)),
    )

    assert logs == [("warning", "AI hooks: no device available, skipping")]


def test_decide_comment_analyzes_exact_post_and_can_skip(monkeypatch):
    from types import SimpleNamespace

    from taktik.core.social_media.instagram.actions.business.actions.comment.action import (
        CommentAction,
    )

    captured = {"original_calls": 0, "actions": []}
    logs = []

    def original_comment(*_args, **_kwargs):
        captured["original_calls"] += 1
        return True

    monkeypatch.setattr(CommentAction, "comment_on_post", original_comment)
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.core.ai_hooks.IPCEmitter.emit_action",
        staticmethod(lambda *args, **kwargs: captured["actions"].append((args, kwargs))),
    )

    class Screenshot:
        def save(self, *_args, **_kwargs):
            return None

    class Device:
        def screenshot(self):
            return Screenshot()

    class FakeAI:
        def analyze_post(self, **kwargs):
            captured["analysis"] = kwargs
            return {
                "success": True,
                "description": "Personal breakfast photo",
                "post_language": "french",
            }

        def generate_smart_comment(self, **kwargs):
            captured["generation"] = kwargs
            return {
                "success": True,
                "should_comment": False,
                "comment": "",
                "reasoning": "Post unrelated to the cinema objective",
            }

    install_instagram_ai_hooks(
        ai=FakeAI(),
        ai_config={
            "smartComments": True,
            "postAnalysis": False,
            "decision": {"mode": "decide", "dryRun": False},
            "accountProfile": {
                "niche": "Cinema",
                "objective": "Build a cinema community",
                "language": "fr",
            },
        },
        device=Device(),
        language="fr",
        log=lambda *args: logs.append(args),
    )

    result = CommentAction.comment_on_post(
        SimpleNamespace(),
        username="candidate",
    )

    assert result == {
        "commented": False,
        "comment_text": None,
        "errors": 0,
        "success": False,
        "skipped": True,
        "skip_reason": "Post unrelated to the cinema objective",
    }, logs
    assert captured["analysis"]["username"] == "candidate"
    assert captured["generation"]["require_relevance_decision"] is True
    assert captured["generation"]["post_description"] == "Personal breakfast photo"
    assert captured["original_calls"] == 0
    assert captured["actions"][-1:] == [(
        (
            "comment_skip",
            "candidate",
            {
                "reason": "Post unrelated to the cinema objective",
                "stage": "post_relevance",
            },
        ),
        {},
    )]


@pytest.mark.parametrize(
    "base_lang, post_language, expected",
    [
        # base_lang = account preferred language (fallback app). Allowed = {base_lang, English}.
        ("fr", "French", "fr"),           # post in base language -> comment in it
        ("fr", "english", "en"),          # English always allowed (case-insensitive)
        ("fr", "Spanish", None),          # other language -> skip
        ("fr", "Chinese", None),
        ("fr", None, "fr"),               # undetected -> default to base language
        ("fr", "", "fr"),
        ("en", "English", "en"),
        ("en", "French", None),           # EN account: French is NOT allowed (only English)
        ("en", None, "en"),
        ("en", "Mandarin", None),
        # Account targeting a non-FR/EN audience (preferred_language beyond fr/en).
        ("es", "Spanish", "es"),
        ("es", "español", "es"),
        ("es", "Castellano", "es"),
        ("es", "English", "en"),          # English still allowed for a Spanish account
        ("es", "French", None),           # Spanish account, French post -> skip
        ("es", None, "es"),
        ("de", "German", "de"),
        ("ar", "Arabic", "ar"),
        ("it", "Italian", "it"),
        ("pt", "Portuguese", "pt"),
        # Robustness: a name that merely CONTAINS "en" must not be read as English.
        ("fr", "Slovenian", None),
        # The model may emit a code instead of a name.
        ("fr", "fr", "fr"),
        ("fr", "en", "en"),
        # Decorated name (flag/extra) still resolves via startswith.
        ("fr", "French (Français)", "fr"),
    ],
)
def test_resolve_comment_language_policy(base_lang, post_language, expected):
    assert _resolve_comment_language(base_lang, post_language) == expected


@pytest.mark.parametrize(
    "base_lang, caption, expected",
    [
        # The account language is the ANCHOR; the CAPTION decides the comment language, never the
        # vision guess. This is the effective policy the smart-comment hook applies.
        # French account, French caption -> French (the account.two regression).
        ("fr", "Venez voir, revoir ou découvrir les IMPROMPTU pour deux concepts d'improvisa… more", "fr"),
        # French account, English caption -> English is allowed as the bilingual 2nd language.
        ("fr", "Omg this sounds so fun! love both concepts", "en"),
        # French account, caption too short/ambiguous -> DEFAULT to the account language (NOT English).
        ("fr", "🎉🎉", "fr"),
        ("fr", "", "fr"),
        ("fr", None, "fr"),
        # English account: English caption -> English; a French post -> skip (an English-only
        # account doesn't claim to speak French, so commenting in French isn't credible).
        ("en", "The new collection is finally here, check it out", "en"),
        ("en", "Venez nous voir pour deux concepts avec les amis", None),
    ],
)
def test_effective_comment_language_from_caption(base_lang, caption, expected):
    # Mirrors the hook: comment language = _resolve_comment_language(account_lang, caption_language).
    assert _resolve_comment_language(base_lang, detect_text_language(caption)) == expected


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def get_profiles_by_usernames(self, usernames):
        return list(self._rows)


def _patch_db(monkeypatch, rows):
    monkeypatch.setattr(
        "taktik.core.database.local.service.get_local_database",
        lambda: _FakeDb(rows),
    )


def test_load_cached_qualification_reuses_stored_niche(monkeypatch):
    # A profile already AI-qualified in the DB is returned so the interaction hook can reuse it
    # instead of re-paying for a fresh vision classification.
    _patch_db(monkeypatch, [{"username": "known", "niche": "fitness", "niche_category": "sport"}])
    row = _load_cached_qualification("known")
    assert row is not None
    assert row["niche"] == "fitness"


def test_load_cached_qualification_matches_case_insensitively(monkeypatch):
    _patch_db(monkeypatch, [{"username": "Known_User", "profession": "coach"}])
    assert _load_cached_qualification("known_user") is not None


def test_load_cached_qualification_none_when_not_ai_qualified(monkeypatch):
    # A bare profile row with no niche/category/profession must NOT be treated as qualified.
    _patch_db(monkeypatch, [{"username": "bare", "full_name": "Bare Profile"}])
    assert _load_cached_qualification("bare") is None


def test_load_cached_qualification_none_when_absent(monkeypatch):
    _patch_db(monkeypatch, [])
    assert _load_cached_qualification("ghost") is None


def test_load_cached_qualification_handles_db_errors(monkeypatch):
    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr("taktik.core.database.local.service.get_local_database", _boom)
    assert _load_cached_qualification("whoever") is None


# ---------------------------------------------------------------------------
# Cached-profile relevance verdict (the gating cache hole)
# ---------------------------------------------------------------------------
# A profile already AI-qualified reuses its stored niche and skips the vision call — which also
# skipped the engagement verdict, so cached profiles were NEVER gated (fail-open). With gating on,
# the hook now judges the KNOWN niche against the account persona via a cheap text-only call.

def _install_profile_hook(
    monkeypatch,
    fake_ai,
    ai_config,
    captured,
    log=None,
    decision_provider=None,
):
    from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
        InteractionEngineMixin,
    )

    def fake_perform(self_engine, username, config, profile_data=None):
        captured["profile_data"] = profile_data
        return "performed"

    # Patch BEFORE install so the hook's original_perform captures the fake; pytest's monkeypatch
    # restores the REAL method afterwards even though install overwrote the attribute again.
    monkeypatch.setattr(InteractionEngineMixin, "_perform_interactions_on_profile", fake_perform)
    # Silence the Agent-card emission (module-level IPCEmitter writes JSON to stdout).
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.core.ai_hooks.IPCEmitter.emit_action",
        staticmethod(lambda *a, **k: None),
    )
    install_instagram_ai_hooks(
        ai=fake_ai,
        ai_config=ai_config,
        device=object(),
        log=log or (lambda *a: None),
        decision_provider=decision_provider,
    )
    return InteractionEngineMixin


GATING = {"enabled": True, "minScore": 0.4, "maskIntents": True, "dryRun": False}
CACHED_ROW = {"username": "known", "niche": "Hair & Nail Art", "niche_category": "beauty_wellness"}


def test_cached_profile_gets_text_verdict_when_gating_on(monkeypatch):
    _patch_db(monkeypatch, [CACHED_ROW])
    captured = {}

    class FakeAI:
        def engagement_verdict_for_known_profile(self, **kwargs):
            captured["verdict_kwargs"] = kwargs
            return {"success": True, "engagement": {
                "relevant": True, "follow": True, "comment": False, "like": True,
                "score": 0.8, "reason": "adjacent",
            }}

    engine_cls = _install_profile_hook(
        monkeypatch, FakeAI(),
        {"profileAnalysis": True, "accountNiche": "beauty_wellness", "relevanceGating": GATING},
        captured,
    )
    profile_data = {}
    result = engine_cls._perform_interactions_on_profile(object(), "known", {}, profile_data)

    assert result == "performed"
    # The verdict AND the gating settings reached the engine (what apply_relevance_gating consumes).
    assert captured["profile_data"]["ai_engagement"]["relevant"] is True
    assert captured["profile_data"]["ai_relevance_gating"] == GATING
    # Judged relative to the operated account, fed from the CACHED classification.
    assert captured["verdict_kwargs"]["account_niche"] == "beauty_wellness"
    assert captured["verdict_kwargs"]["cached"]["niche"] == "Hair & Nail Art"
    # The reuse markers stay (no vision re-analysis happened).
    assert captured["profile_data"]["ai_reused_qualification"] is True


def test_relevance_log_labels_ai_output_as_advice_not_executed_plan(monkeypatch):
    _patch_db(monkeypatch, [CACHED_ROW])
    captured = {}
    logs = []

    class FakeAI:
        def engagement_verdict_for_known_profile(self, **kwargs):
            return {"success": True, "engagement": {
                "relevant": True, "follow": True, "comment": False, "like": True,
                "score": 0.8, "reason": "adjacent",
            }}

    engine_cls = _install_profile_hook(
        monkeypatch,
        FakeAI(),
        {"profileAnalysis": True, "accountNiche": "beauty_wellness", "relevanceGating": GATING},
        captured,
        log=lambda level, message: logs.append((level, message)),
    )

    engine_cls._perform_interactions_on_profile(object(), "known", {}, {})

    advice_logs = [message for _, message in logs if "avis IA @known" in message]
    assert len(advice_logs) == 1
    assert "recommande follow, like" in advice_logs[0]
    assert "plan final est calculé ensuite" in advice_logs[0]


def test_cached_profile_skips_verdict_when_gating_off(monkeypatch):
    # Without gating there is nothing to enforce — don't spend tokens on cached profiles.
    _patch_db(monkeypatch, [CACHED_ROW])
    captured = {}

    class FakeAI:
        def engagement_verdict_for_known_profile(self, **kwargs):
            raise AssertionError("must not be called when gating is off")

    engine_cls = _install_profile_hook(
        monkeypatch, FakeAI(), {"profileAnalysis": True, "accountNiche": "beauty_wellness"}, captured,
    )
    profile_data = {}
    result = engine_cls._perform_interactions_on_profile(object(), "known", {}, profile_data)

    assert result == "performed"
    assert "ai_engagement" not in captured["profile_data"]


def test_cached_profile_fails_open_when_verdict_errors(monkeypatch):
    # Historic behaviour preserved: verdict failure -> no verdict on profile_data -> engine
    # passthrough (fail-open), and the interaction still runs.
    _patch_db(monkeypatch, [CACHED_ROW])
    captured = {}

    class FakeAI:
        def engagement_verdict_for_known_profile(self, **kwargs):
            return {"success": False, "error": "model hiccup"}

    engine_cls = _install_profile_hook(
        monkeypatch, FakeAI(),
        {"profileAnalysis": True, "accountNiche": "beauty_wellness", "relevanceGating": GATING},
        captured,
    )
    profile_data = {}
    result = engine_cls._perform_interactions_on_profile(object(), "known", {}, profile_data)

    assert result == "performed"
    assert "ai_engagement" not in captured["profile_data"]


def test_decide_mode_requests_front_plan_for_cached_profile(monkeypatch):
    _patch_db(monkeypatch, [CACHED_ROW])
    captured = {}

    class FakeAI:
        def engagement_verdict_for_known_profile(self, **kwargs):
            return {"success": True, "engagement": {
                "relevant": True, "follow": True, "comment": False, "like": True,
                "score": 0.9, "reason": "strong",
                "relevance_tier": "direct", "evidence": "Same professional niche",
            }}

    response = {
        "ok": True,
        "plan": {"likes": 1, "follow": True},
        "decision": {"dryRun": True, "score": 0.9, "reason": "strong", "notes": []},
    }

    def decide(facts):
        captured["facts"] = facts
        return response

    engine_cls = _install_profile_hook(
        monkeypatch,
        FakeAI(),
        {
            "profileAnalysis": True,
            "accountNiche": "beauty_wellness",
            "decision": {"mode": "decide", "dryRun": True},
        },
        captured,
        decision_provider=decide,
    )
    profile_data = {"followers_count": 120, "following_count": 900, "posts_count": 42}

    engine_cls._perform_interactions_on_profile(
        object(),
        "known",
        {
            "max_likes_per_profile": 3,
            "max_comments_per_profile": 0,
            "max_stories_per_profile": 0,
            "max_story_likes_per_profile": 0,
        },
        profile_data,
    )

    assert captured["facts"]["profile"]["followersCount"] == 120
    assert captured["facts"]["engagement"]["relevanceTier"] == "direct"
    assert captured["facts"]["engagement"]["evidence"] == "Same professional niche"
    assert captured["facts"]["limits"]["maxCommentsPerProfile"] == 0
    assert captured["facts"]["limits"]["maxStoriesPerProfile"] == 0
    assert captured["facts"]["limits"]["maxStoryLikesPerProfile"] == 0
    assert captured["profile_data"]["ai_agent_decision"]["mode"] == "decide"


def test_decide_mode_sends_fresh_classification_facts_to_front(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.core.ai_hooks._load_cached_qualification",
        lambda _username: None,
    )

    class Screenshot:
        def save(self, *_args, **_kwargs):
            return None

    class Device:
        def screenshot(self):
            return Screenshot()

    class FakeAI:
        def classify_profile_niche(self, **_kwargs):
            return {
                "success": True,
                "classification": {
                    "niche_category": "arts",
                    "niche": "Filmmaking & Cinematography",
                    "engagement": {
                        "relevant": True,
                        "relevance_tier": "direct",
                        "evidence": "Explicit filmmaker profession",
                        "follow": True,
                        "comment": False,
                        "like": True,
                        "score": 0.9,
                        "reason": "Direct cinema match",
                    },
                },
            }

    def decide(facts):
        captured["facts"] = facts
        return {
            "ok": True,
            "plan": {"likes": 1, "follow": False},
            "decision": {
                "dryRun": True,
                "score": 0.9,
                "reason": "Direct cinema match",
                "notes": [],
            },
        }

    from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
        InteractionEngineMixin,
    )

    def fake_perform(self_engine, username, config, profile_data=None):
        captured["profile_data"] = profile_data
        return "performed"

    monkeypatch.setattr(
        InteractionEngineMixin,
        "_perform_interactions_on_profile",
        fake_perform,
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.core.ai_hooks.IPCEmitter.emit_action",
        staticmethod(lambda *a, **k: None),
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.core.ai_hooks.IPCEmitter.emit_profile_classification",
        staticmethod(lambda *a, **k: None),
    )

    install_instagram_ai_hooks(
        ai=FakeAI(),
        ai_config={
            "profileAnalysis": True,
            "decision": {"mode": "decide", "dryRun": True},
        },
        device=Device(),
        log=lambda *a: None,
        decision_provider=decide,
    )

    profile_data = {
        "followers_count": 433,
        "following_count": 998,
        "posts_count": 4,
    }
    result = InteractionEngineMixin._perform_interactions_on_profile(
        object(),
        "direct_filmmaker",
        {"max_likes_per_profile": 3},
        profile_data,
    )

    assert result == "performed"
    assert captured["facts"]["profile"]["niche"] == "Filmmaking & Cinematography"
    assert captured["facts"]["profile"]["nicheCategory"] == "arts"
    assert captured["facts"]["engagement"]["relevanceTier"] == "direct"
    assert captured["profile_data"]["ai_niche"] == "Filmmaking & Cinematography"
    assert captured["profile_data"]["ai_niche_category"] == "arts"


def test_decide_response_without_metadata_inherits_configured_dry_run(monkeypatch):
    _patch_db(monkeypatch, [CACHED_ROW])
    captured = {}

    class FakeAI:
        def engagement_verdict_for_known_profile(self, **kwargs):
            return {"success": True, "engagement": {
                "relevant": True, "follow": True, "comment": False, "like": True,
                "score": 0.9, "reason": "strong",
            }}

    engine_cls = _install_profile_hook(
        monkeypatch,
        FakeAI(),
        {
            "profileAnalysis": True,
            "decision": {"mode": "decide", "dryRun": False},
        },
        captured,
        decision_provider=lambda _facts: {"ok": False, "error": "timeout"},
    )

    engine_cls._perform_interactions_on_profile(object(), "known", {}, {})

    decision = captured["profile_data"]["ai_agent_decision"]
    assert decision["ok"] is False
    assert decision["decision"]["dryRun"] is False
