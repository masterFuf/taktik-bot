"""The post scraping entries of the Instagram menu run the Scraping page's launcher.

"Full Post Scraping" built `PostScrapingWorkflow`, a CLI-only engine with its own format that the
app never ran. The entries now describe the Scraping page's two post sources, `post_url` (likers,
commenters, or both with each profile visited) and `profile_posts` (the posts of accounts: link,
likes, comments), and run through `instagram.scraping.<type>`.
"""
import ast
import sys
from pathlib import Path

import pytest

from instagram_scraping_rig import DEVICE_ID, INSTAGRAM

CORE = Path(__file__).resolve().parents[3]


@pytest.fixture
def answer(monkeypatch):
    from rich.prompt import Confirm, Prompt

    def feed(*answers, confirm=True):
        queue = iter(answers)
        monkeypatch.setattr(Prompt, "ask", lambda *a, **k: next(queue))
        monkeypatch.setattr(Confirm, "ask", lambda *a, **k: confirm)

    return feed


def test_likers_and_commenters_of_a_post_is_the_page_post_url_source(answer):
    from taktik.cli.prompts import scraping as prompts

    answer("https://www.instagram.com/p/AbC123/", "80", "30")

    assert prompts.generate_url_scraping_workflow("both") == {
        "type": "post_url",
        "postUrls": ["https://www.instagram.com/p/AbC123/"],
        "scrapePostUrlLikers": True,
        "scrapePostUrlCommenters": True,
        "maxProfiles": 80,
        "enrichProfiles": True,
        "sessionDurationMinutes": 30,
        "saveToDb": True,
        "exportCsv": True,
    }


def test_the_posts_of_accounts_prompts_describe_the_page_profile_posts_source(answer):
    from taktik.cli.prompts import scraping as prompts

    answer("alpha, @beta", "12", "25")

    assert prompts.generate_profile_posts_scraping_workflow() == {
        "type": "profile_posts",
        "targetUsernames": ["alpha", "beta"],
        "maxPostsPerTarget": 12,
        "sessionDurationMinutes": 25,
        "saveToDb": True,
        "exportCsv": True,
    }


def test_a_post_menu_run_goes_through_the_scraping_launcher(igs_rig, answer):
    from taktik.cli.common.instagram_host import run_instagram_scraping_payload
    from taktik.cli.prompts import scraping as prompts

    answer("https://www.instagram.com/p/AbC123/", "40", "20")
    run_instagram_scraping_payload(igs_rig.device_manager, DEVICE_ID, prompts.generate_url_scraping_workflow("both"))

    assert igs_rig.calls.index(f"stop {INSTAGRAM}") < igs_rig.calls.index("run_scraping")
    built = igs_rig.built_config
    assert (built["type"], built["scrape_likers"], built["scrape_commenters"]) == ("post_url", True, True)
    assert built["enrich_profiles"] is True


def test_a_posts_of_accounts_menu_run_goes_through_the_scraping_launcher(igs_rig, answer):
    from taktik.cli.common.instagram_host import run_instagram_scraping_payload
    from taktik.cli.prompts import scraping as prompts

    answer("alpha", "12", "25")
    run_instagram_scraping_payload(igs_rig.device_manager, DEVICE_ID,
                                   prompts.generate_profile_posts_scraping_workflow())

    built = igs_rig.built_config
    assert (built["type"], built["target_usernames"], built["max_posts_per_target"]) == (
        "profile_posts", ["alpha"], 12)


def test_the_interactive_menu_builds_no_engine_of_its_own():
    """Only the account lot's login is still excused in the menu; nothing else it runs is built
    by the menu itself."""
    sys.path.insert(0, str(CORE / "scripts"))
    import workflow_launchers

    inputs = workflow_launchers.collect_inputs()
    launchers = workflow_launchers.launcher_functions(inputs.launcher_trees)
    engines = workflow_launchers.engine_names(inputs.launcher_trees, launchers)
    tree = ast.parse((CORE / "taktik" / "cli" / "main.py").read_text(encoding="utf-8"))

    built = {name for name, _line in workflow_launchers.engine_calls(tree, engines, launchers)}

    assert built == {"LoginWorkflow"}
