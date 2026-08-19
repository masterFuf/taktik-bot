"""Every AIService comes from one factory, and it always carries the taxonomy.

Four bridges used to build the service themselves and only one passed `niche_taxonomy`, so
the classifier saw the premium taxonomy during scraping and never during automation. The
model then invented its own category slugs and 13.1 % of them were clamped to `other` — a
classification paid for and discarded.

`test_no_bridge_builds_an_ai_service_directly` is the one that keeps this from coming back.
"""
from pathlib import Path

import pytest

from taktik.core.app.ai.factory import build_ai_service, create_ai_service

TAXONOMY = {"beauty_wellness": ["Naturopathy", "Massage"], "fashion": ["Streetwear"]}


def _config(**overrides):
    base = {"enabled": True, "openrouterApiKey": "sk-or-longenoughkey"}
    base.update(overrides)
    return base


def test_the_taxonomy_reaches_the_service():
    enabled, service = create_ai_service(ai_config=_config(nicheTaxonomy=TAXONOMY))
    assert enabled is True
    assert service.niche_taxonomy == TAXONOMY
    # What the classifier actually renders into its prompt.
    assert "Naturopathy" in service._niche_map_text()


def test_the_snake_case_spelling_is_accepted_too():
    """Bridges hand over a JS-shaped payload; the scraping config re-keys it."""
    _, service = create_ai_service(ai_config=_config(niche_taxonomy=TAXONOMY))
    assert service.niche_taxonomy == TAXONOMY


def test_a_standalone_run_without_taxonomy_still_classifies():
    """The open-source bot does not own the taxonomy — it must degrade, never fail."""
    enabled, service = create_ai_service(ai_config=_config())
    assert enabled is True
    assert service.niche_taxonomy == {}
    assert "no taxonomy provided" in service._niche_map_text()


def test_the_log_says_whether_the_taxonomy_arrived():
    """A free-form run is legitimate standalone and a silent regression on desktop."""
    lines = []
    create_ai_service(ai_config=_config(nicheTaxonomy=TAXONOMY), log=lambda lvl, msg: lines.append(msg))
    assert "2 categories" in lines[-1]

    lines.clear()
    create_ai_service(ai_config=_config(), log=lambda lvl, msg: lines.append(msg))
    assert "no taxonomy injected" in lines[-1]


@pytest.mark.parametrize("config", [
    {"enabled": False, "openrouterApiKey": "sk-or-longenoughkey"},
    {"enabled": True, "openrouterApiKey": ""},
    {"enabled": True, "openrouterApiKey": "sk"},
])
def test_ai_stays_off_without_a_usable_key(config):
    assert create_ai_service(ai_config=config) == (False, None)


def test_build_ai_service_defaults_to_no_taxonomy():
    assert build_ai_service(api_key="sk-or-longenoughkey").niche_taxonomy == {}


def test_no_bridge_builds_an_ai_service_directly():
    """The regression guard: constructing AIService outside the factory is how they drifted."""
    offenders = []
    for path in Path("bridges").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "AIService(" in source:
            offenders.append(str(path))
    assert offenders == [], f"these must go through app.ai.factory: {offenders}"
