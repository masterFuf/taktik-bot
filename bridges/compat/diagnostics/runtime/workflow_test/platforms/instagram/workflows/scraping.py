"""Instagram scraping workflow-test runner.

Wired to production. Scraping only reads, so unlike publish there is nothing to hold back at the
end — but a diagnostic run must not leave a trace either, so it runs with persistence and CSV
export OFF and with the AI disabled. The bench measures whether the bot can still reach a list and
read profiles from it; it is not there to fill the database or to spend on qualification.

`run_scraping_bridge` was named as the entry point, but it is CLI-shaped: it parses argv AND opens
its own device connection, which would fight the one the bench already holds. The wiring therefore
targets `run_scraping_workflow`, the layer just below — the same one the bridge itself calls once
it has connected — and hands it the bench's own device manager.

`scrape_profile_posts` probes the post catalogue source: with persistence off it opens a few posts
of the target and reads their cards without writing a row.

`scrape_e_story` stays unwired: the production scraping workflow only knows target, hashtag,
post_url and profile_posts.
"""
from __future__ import annotations

from bridges.compat.diagnostics.runtime.workflow_test.execution.not_wired import not_wired

# Bench workflow type -> production scraping type.
_SCRAPING_TYPES = {
    "scrape_account": "target",
    "scrape_hashtag": "hashtag",
    "scrape_post_url": "post_url",
    "scrape_profile_posts": "profile_posts",
}


def _bridge_config(scraping_type: str, target, limits: dict, delays) -> dict:
    """Build the camelCase payload `build_scraping_config` expects.

    Persistence and AI are forced off: this is a capability probe, not a run.
    """
    limits = limits or {}
    config = {
        "type": scraping_type,
        "maxProfiles": int(limits.get("maxProfiles", limits.get("profiles", 10)) or 10),
        "sessionDurationMinutes": int(limits.get("sessionDurationMinutes", 10) or 10),
        # A diagnostic must not write to the operator's database or drop CSVs on their disk.
        "saveToDb": False,
        "exportCsv": False,
        "enrichProfiles": False,
        # Dedup would make a second run read nothing and report a false success.
        "rescrapeAfterDays": 0,
        "ai": {"enabled": False},
    }

    targets = target if isinstance(target, list) else [t for t in [target] if t]
    if scraping_type == "target":
        config["targetUsernames"] = targets
        config["scrapeType"] = "followers"
    elif scraping_type == "hashtag":
        config["hashtags"] = [str(t).lstrip("#") for t in targets]
        config["maxPosts"] = 5
    elif scraping_type == "profile_posts":
        config["targetUsernames"] = [str(t).lstrip("@") for t in targets]
        config["maxPostsPerTarget"] = 3
    else:
        config["postUrls"] = targets

    if delays:
        config["delays"] = delays
    return config


def run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays):
    scraping_type = _SCRAPING_TYPES.get(workflow_type)
    if not scraping_type:
        return not_wired(
            ipc,
            workflow_type,
            "bridges.instagram.scraping.runtime.workflow.run_scraping_workflow "
            "(production knows target, hashtag, post_url and profile_posts only)",
        )

    if not target:
        ipc.send(
            "workflow_step",
            step=workflow_type,
            status="error",
            error=f"'{workflow_type}' needs a target (account, hashtag or post URL)",
        )
        return False

    from bridges.instagram.scraping.runtime.config import build_scraping_config
    from bridges.instagram.scraping.runtime.workflow import run_scraping_workflow

    bridge_config = _bridge_config(scraping_type, target, limits, delays)
    scraping_config = build_scraping_config(bridge_config)

    ipc.send(
        "workflow_step",
        step=workflow_type,
        status="running",
        message=f"Scraping {scraping_type} (read-only, nothing saved)",
    )

    result = run_scraping_workflow(conn.device_manager, scraping_config, bridge_config)

    success = bool(result.get("success"))
    ipc.send(
        "action_event",
        action="scraping_probe",
        username="",
        success=success,
        data={
            "workflow": workflow_type,
            "scrapingType": scraping_type,
            "totalScraped": result.get("totalScraped", 0),
            "persisted": False,
            "error": result.get("error"),
        },
    )
    return success
