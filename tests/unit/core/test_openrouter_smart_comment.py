"""generate_smart_comment returns a {reasoning, comment} pair so the Agent card can show WHY the
comment was written (decision context, also feeds the autonomous-mode trace).

The model is asked for a single-line JSON object; parsing must be robust and fall back to
"whole text = comment" when the model doesn't comply (backward compatible).
"""

from taktik.core.app.ai.providers.openrouter import AIService


def _service(monkeypatch, model_text):
    # Bypass __init__: we only exercise the parsing, with ipc disabled and text_completion stubbed.
    svc = object.__new__(AIService)
    svc.ipc = None
    svc.text_model = "test/model"
    # Comment generation routes to the GENERATION model explicitly (two-fixed-models design),
    # so the stub must carry it too — __init__ is bypassed here.
    svc.model_generation = "test/model-generation"
    svc.model_analysis = "test/model"
    svc.niche_taxonomy = {}
    monkeypatch.setattr(
        svc, "text_completion",
        lambda *a, **k: {"success": True, "text": model_text, "model": "test/model", "cost_usd": 0.0},
    )
    return svc


def test_parses_reasoning_and_comment_from_json(monkeypatch):
    svc = _service(
        monkeypatch,
        '{"reasoning": "Le post annonce une retraite; je réagis à l\'invitation avec enthousiasme.", '
        '"comment": "Ça donne trop envie ce moment 🙌"}',
    )
    out = svc.generate_smart_comment(post_description="a retreat announcement", username="x",
                                     language="fr", app_language="fr")
    assert out["success"] is True
    assert out["should_comment"] is True
    assert out["comment"] == "Ça donne trop envie ce moment 🙌"
    assert "retraite" in out["reasoning"]


def test_json_with_surrounding_text_is_still_parsed(monkeypatch):
    svc = _service(monkeypatch, 'Sure!\n{"reasoning": "why", "comment": "love this vibe ✨"}\nHope that helps')
    out = svc.generate_smart_comment(post_description="d", username="x", language="en", app_language="en")
    assert out["comment"] == "love this vibe ✨"
    assert out["reasoning"] == "why"


def test_fallback_when_not_json(monkeypatch):
    # The model ignored the JSON instruction and returned a bare comment -> use it as the comment.
    svc = _service(monkeypatch, "just a plain comment no json 🔥")
    out = svc.generate_smart_comment(post_description="d", username="x", language="en", app_language="en")
    assert out["comment"] == "just a plain comment no json 🔥"
    assert out["reasoning"] == ""


def test_strips_wrapping_quotes_in_fallback(monkeypatch):
    svc = _service(monkeypatch, '"quoted plain comment"')
    out = svc.generate_smart_comment(post_description="d", username="x", language="en", app_language="en")
    assert out["comment"] == "quoted plain comment"


def test_post_specific_comment_decision_can_reject_post(monkeypatch):
    svc = _service(
        monkeypatch,
        '{"should_comment": false, "reasoning": "Personal post unrelated to cinema", '
        '"comment": ""}',
    )

    out = svc.generate_smart_comment(
        post_description="A personal breakfast photo",
        username="x",
        language="fr",
        app_language="fr",
        require_relevance_decision=True,
    )

    assert out["success"] is True
    assert out["should_comment"] is False
    assert out["comment"] == ""
    assert "unrelated" in out["reasoning"]


def test_post_specific_comment_decision_accepts_grounded_post(monkeypatch):
    svc = _service(
        monkeypatch,
        '{"should_comment": true, "reasoning": "The caption announces a short film", '
        '"comment": "Hâte de découvrir ce court-métrage 🎬"}',
    )

    out = svc.generate_smart_comment(
        post_description="A short-film poster",
        post_caption="Notre court-métrage sort vendredi",
        username="x",
        language="fr",
        app_language="fr",
        require_relevance_decision=True,
    )

    assert out["should_comment"] is True
    assert out["comment"] == "Hâte de découvrir ce court-métrage 🎬"


def test_post_specific_comment_decision_fails_closed_on_bare_text(monkeypatch):
    svc = _service(monkeypatch, "super post 🔥")

    out = svc.generate_smart_comment(
        post_description="A post",
        username="x",
        require_relevance_decision=True,
    )

    assert out["should_comment"] is False
    assert out["comment"] == ""
