"""classify_following_usernames_batch (deep-qualify) must not lose a whole batch when the model's
JSON response is truncated. A full batch of 20 usernames used to overflow the token cap, the
response came back cut off ("Unterminated string"), json.loads raised, and EVERY username in the
batch was dropped. Now the token budget scales with the batch size and, if a response is still
truncated, every COMPLETE '"user": {...}' entry is salvaged so only the cut-off tail is lost.
"""

from taktik.core.ai.providers.openrouter import AIService


def _service(monkeypatch, model_text):
    # Bypass __init__: we only exercise the parsing, with ipc disabled and text_completion stubbed.
    svc = object.__new__(AIService)
    svc.ipc = None
    svc.text_model = "test/model"
    svc.niche_taxonomy = {}
    monkeypatch.setattr(
        svc, "text_completion",
        lambda *a, **k: {"success": True, "text": model_text, "model": "test/model", "cost_usd": 0.0},
    )
    return svc


# A response cut off part-way through the last entry (no closing brace on "carol").
TRUNCATED = (
    '{\n'
    '  "alice": {"niche_category": "beauty_wellness", "niche": "Nail Art", "gender": "female"},\n'
    '  "bob": {"niche_category": "fitness_sports", "niche": "Gym", "gender": "male"},\n'
    '  "carol": {"niche_category": "trav'
)


def test_salvage_recovers_complete_entries_from_truncated_json():
    svc = object.__new__(AIService)
    out = svc._salvage_batch_entries(TRUNCATED)
    assert set(out) == {"alice", "bob"}          # carol (truncated) is dropped, not the whole batch
    assert out["alice"]["niche"] == "Nail Art"
    assert out["bob"]["niche_category"] == "fitness_sports"


def test_salvage_ignores_inner_string_keys():
    # Only top-level "user": {...} pairs are entries; inner "niche_category": "..." must not match.
    svc = object.__new__(AIService)
    out = svc._salvage_batch_entries(TRUNCATED)
    assert "niche_category" not in out and "niche" not in out


def test_salvage_empty_text_returns_empty():
    svc = object.__new__(AIService)
    assert svc._salvage_batch_entries("") == {}


def test_truncated_batch_is_salvaged_not_dropped(monkeypatch):
    svc = _service(monkeypatch, TRUNCATED)
    out = svc.classify_following_usernames_batch(["alice", "bob", "carol"])
    assert set(out) == {"alice", "bob"}          # was {} before the fix (whole batch lost)
    assert out["alice"]["niche"] == "Nail Art"
    assert "carol" not in out


def test_valid_batch_parses_all(monkeypatch):
    valid = ('{"alice": {"niche_category": "beauty_wellness", "niche": "Nail Art", "gender": "female"}, '
             '"bob": {"niche_category": "fitness_sports", "niche": "Gym", "gender": "male"}}')
    svc = _service(monkeypatch, valid)
    out = svc.classify_following_usernames_batch(["alice", "bob"])
    assert set(out) == {"alice", "bob"}
    assert out["bob"]["gender"] == "male"


def test_fenced_batch_is_parsed(monkeypatch):
    fenced = ('```json\n{"alice": {"niche_category": "beauty_wellness", "niche": "Nail Art", '
              '"gender": "female"}}\n```')
    svc = _service(monkeypatch, fenced)
    out = svc.classify_following_usernames_batch(["alice"])
    assert out["alice"]["niche"] == "Nail Art"
