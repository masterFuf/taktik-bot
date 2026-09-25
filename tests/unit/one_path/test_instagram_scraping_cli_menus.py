"""The Instagram scraping menus of the CLI run the desktop's launcher, not a second reading.

The menus wrote the workflow's internal config themselves and ran `ScrapingWorkflow` by hand: no
restart, no profile filter of the page, and two choices that did nothing. A hashtag's "post
authors" and a post URL's "comments only" set a `scrape_type` the workflow does not read for those
sources: both scraped the likers. The prompts now describe the run the way the Scraping page does,
and the run goes through the scraping handler.
"""
import pytest

from instagram_scraping_rig import DEVICE_ID, INSTAGRAM


@pytest.fixture
def answer(monkeypatch):
    from rich.prompt import Confirm, Prompt

    def feed(*answers):
        queue = iter(answers)
        monkeypatch.setattr(Prompt, "ask", lambda *a, **k: next(queue))
        monkeypatch.setattr(Confirm, "ask", lambda *a, **k: True)

    return feed


def test_the_target_prompts_describe_the_run_like_the_page(answer):
    from taktik.cli.prompts import scraping as prompts

    answer("alpha, @beta", "2", "40", "15")

    assert prompts.generate_target_scraping_workflow() == {
        "type": "target",
        "scrapeType": "following",
        "targetUsernames": ["alpha", "beta"],
        "maxProfiles": 40,
        "sessionDurationMinutes": 15,
        "saveToDb": True,
        "exportCsv": True,
    }


def test_the_hashtag_prompts_choose_between_likers_and_commenters(answer):
    from taktik.cli.prompts import scraping as prompts

    answer("#cuisine", "2", "30", "8", "10")
    payload = prompts.generate_hashtag_scraping_workflow()

    assert payload["hashtags"] == ["cuisine"]
    assert (payload["scrapeHashtagLikers"], payload["scrapeHashtagCommenters"]) == (False, True)
    assert payload["maxPosts"] == 8


def test_the_post_url_comments_choice_scrapes_the_commenters(answer):
    from taktik.cli.prompts import scraping as prompts

    answer("https://www.instagram.com/p/AbC123/", "25", "5")
    payload = prompts.generate_url_scraping_workflow("commenters")

    assert payload["postUrls"] == ["https://www.instagram.com/p/AbC123/"]
    assert (payload["scrapePostUrlLikers"], payload["scrapePostUrlCommenters"]) == (False, True)


def test_a_menu_run_goes_through_the_launcher(igs_rig):
    from taktik.cli.common.instagram_host import run_instagram_scraping_payload

    run_instagram_scraping_payload(igs_rig.device_manager, DEVICE_ID, {
        "type": "target", "targetUsernames": ["alpha"], "scrapeType": "followers", "maxProfiles": 5,
        "sessionDurationMinutes": 10, "saveToDb": True, "exportCsv": True, "minPosts": 1,
    })

    assert igs_rig.calls.index(f"stop {INSTAGRAM}") < igs_rig.calls.index("run_scraping")
    assert igs_rig.built_config["minPosts"] == 1
    assert igs_rig.built_config["skipPrivateProfiles"] is True
