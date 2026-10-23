"""The model bench (`scripts/eval/replay_models.py`) replays on the model and the provider it is asked for.

Three things it got wrong or could not do, each checked without a call:
- a profile replay ran on the policy's classifier whatever `--models` said: the service's profile
  classifier (`model_classification`, its own model since the classifier and the describer were
  split) was never set, so the bench measured the model already in production;
- it could not replay on Anthropic (`--provider anthropic`, `ANTHROPIC_API_KEY`), the only way to
  move the proposed Claude model to "measured";
- its budget counted `ai_spend(cost, model, label, kind)` only, and an Anthropic call reports two
  fields more: the call was paid and the budget never saw it.
"""

import importlib.util

import pytest

from taktik.core.ai.credential import AICredential
from taktik.core.ai.openrouter_policy import ANTHROPIC_PRICES_USD_PER_MTOK
from unit.paths import CORE

ANTHROPIC = AICredential(provider="anthropic", api_key="sk-ant-api03-" + "b" * 40)


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("replay_models", CORE / "scripts" / "eval" / "replay_models.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_task_of_the_replayed_service_runs_on_the_candidate(bench):
    service = bench.service_on("claude-sonnet-5-5", ANTHROPIC, bench.SpendCapture(), None)

    assert service.provider == "anthropic"
    assert service.model_classification == service.model_analysis == service.model_generation == "claude-sonnet-5-5"


def test_an_anthropic_call_counts_against_the_budget(bench):
    spend = bench.SpendCapture()

    spend.ai_spend(0.0021, model="claude-haiku-5-5", label="t", kind="profile",
                   provider="anthropic", cost_basis="public_price")

    assert spend.total_usd == pytest.approx(0.0021)
    assert spend.calls == 1


def test_the_estimate_reads_anthropic_s_prices_from_the_policy(bench):
    prices = bench.prices_for("anthropic", ["claude-haiku-5-5", "claude-unknown"])

    assert prices == {"claude-haiku-5-5": {"in": ANTHROPIC_PRICES_USD_PER_MTOK["claude-haiku-5-5"]["input"],
                                           "out": ANTHROPIC_PRICES_USD_PER_MTOK["claude-haiku-5-5"]["output"]}}
