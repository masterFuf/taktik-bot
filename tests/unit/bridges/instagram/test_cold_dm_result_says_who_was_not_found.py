"""The last line of a Cold DM run says the recipients not found and those of a slow search.

`dmsNotFound` and `dmsSearchSlow` (declared in `contract/instagram_engagement.py`) are the run's
`dms_not_found` and `dms_search_slow`: the app shows them apart from `dmsFailed`.
"""

import json

from bridges.instagram.cold_dm import commands
from taktik.core.social_media.instagram.workflows.cold_dm import agent_handler


def test_the_result_line_carries_both_counts(monkeypatch, capsys):
    monkeypatch.setattr(agent_handler, "run_instagram_cold_dm", lambda config, **kwargs: {
        "success": True, "dms_sent": 0, "dms_success": 0, "dms_failed": 0, "dms_pending": 0,
        "dms_not_found": 2, "dms_search_slow": 1, "texts_refused": 0})

    commands.run_cold_dm({"deviceId": "emulator-5554"})

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    result = [line for line in lines if line.get("type") == "cold_dm_result"][-1]
    assert (result["dmsNotFound"], result["dmsSearchSlow"], result["dmsFailed"]) == (2, 1, 0)
