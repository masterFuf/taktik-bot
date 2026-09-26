"""The OpenRouter request policy is declared once, in a file the desktop app can read.

The app used to carry its own copy of the models: its generation model stayed on
gemini-3-flash-preview for two weeks after the bot moved to qwen. The app's copy is now
generated from `openrouter_policy.py` (`npm run ai:policy`), which runs this file on its own:
it must stay free of imports, and the provider must read it rather than redeclare it.
"""

import ast
import runpy
from pathlib import Path

from taktik.core.app.ai import openrouter_policy as policy
from taktik.core.app.ai.providers import openrouter

POLICY_FILE = Path(policy.__file__)


def test_the_policy_file_runs_on_its_own():
    tree = ast.parse(POLICY_FILE.read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert imports == []
    values = runpy.run_path(str(POLICY_FILE))
    assert values["MODEL_GENERATION"] == policy.MODEL_GENERATION


def test_the_provider_reads_the_policy():
    assert openrouter.MODEL_GENERATION == policy.MODEL_GENERATION
    assert openrouter.MODEL_CLASSIFICATION == policy.MODEL_CLASSIFICATION
    assert openrouter.MODEL_ANALYSIS == policy.MODEL_ANALYSIS
    assert openrouter.RATE_LIMIT_BACKOFF_SECONDS == policy.RATE_LIMIT_BACKOFF_SECONDS
    assert openrouter.PROVIDER_PREFERENCE == policy.PROVIDER_PREFERENCE


def test_generation_and_classification_run_on_the_same_model():
    assert policy.MODEL_GENERATION == "qwen/qwen3.7-flash"
    assert policy.MODEL_CLASSIFICATION == policy.MODEL_GENERATION


def test_only_transient_statuses_are_retried():
    assert 429 in policy.RETRYABLE_HTTP_STATUSES
    for status in (400, 401, 402, 404):
        assert status not in policy.RETRYABLE_HTTP_STATUSES
