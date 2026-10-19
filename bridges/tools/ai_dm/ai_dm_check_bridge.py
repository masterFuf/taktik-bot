"""DM check bridge: the rule every DM written by an AI goes through, run on texts before the app keeps
them in a proposal (decision of 18/10, q. 33: the app never copies the rule).

    ai_dm_check_bridge <config.json>

    {"texts": ["...", ...], "aiDmRules"?: {"linksAllowed"?, "forbiddenTerms"?, "accountProfile"?}}

`aiDmRules` is the block the app sends to the workflows (`taktik/core/contract/ai_dm.py`); absent, the
most prudent frame. One line on stdout: `ai_dm_check` with the texts refused, each with its rank and
its reason, or `error` with an `error_code` when the file cannot be read as texts and a frame. No phone,
no base: the bridge only reads its file.
"""

from __future__ import annotations

from typing import Any, List

from bridges.common.bootstrap import setup_environment

setup_environment()

EXIT_OK = 0
EXIT_REFUSED = 2

USAGE = 'ai_dm_check_bridge <config.json>: {"texts": [...], "aiDmRules"?: {...}}'
INPUT_ERROR = "AI_DM_CHECK_INPUT"


def _default_ipc():
    from bridges.common.ipc import IPC

    return IPC()


def _texts_of(config: dict) -> List[str]:
    texts: Any = config.get("texts")
    if not isinstance(texts, list) or not texts:
        raise ValueError("texts: a non-empty list of texts is expected")
    if not all(isinstance(text, str) for text in texts):
        raise ValueError("texts: every item must be a text")
    return texts


def run(config: dict, ipc=None) -> int:
    """Checks the texts of `config` against its frame; emits `ai_dm_check`, or `error` on a bad file."""
    if ipc is None:
        ipc = _default_ipc()

    from taktik.core.ai.dm_rules import ai_dm_rules_from_payload, check_ai_dm_texts

    try:
        texts = _texts_of(config)
        rules = ai_dm_rules_from_payload(config.get("aiDmRules"))
    except ValueError as exc:
        ipc.error(f"{exc} (usage: {USAGE})", error_code=INPUT_ERROR)
        return EXIT_REFUSED

    refusals = check_ai_dm_texts(texts, rules)
    ipc.send("ai_dm_check", checked=len(texts), refusals=[refusal.as_line() for refusal in refusals])
    return EXIT_OK


class AiDmCheckRun:
    """One check, from its config file (read by `run_bridge_main`)."""

    def __init__(self, config: dict, ipc=None):
        self.config = config
        self.ipc = ipc

    def run(self) -> int:
        return run(self.config, ipc=self.ipc)


def main() -> None:
    from bridges.common.entrypoint import run_bridge_main

    ipc = _default_ipc()
    run_bridge_main(lambda config: AiDmCheckRun(config, ipc), usage=USAGE,
                    report_error=lambda message, _reason: ipc.error(message, error_code=INPUT_ERROR))
