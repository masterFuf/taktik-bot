"""L'unfollow TikTok garde les comptes suivis depuis moins que l'« Âge min. (jours) » du nœud, et
ceux dont la date de follow est inconnue.

L'âge : le dernier FOLLOW du bot, sinon la première fois qu'une synchro de la liste d'abonnements
a vu le compte (`TikTokFollowGraphService.get_follow_age_days`, comme l'unfollow Instagram date un
follow). Dans le doute, on protège : un compte que rien ne date (pas de pseudo sur la ligne,
compte actif inconnu, ni FOLLOW ni synchro) est gardé, motif `follow_date_unknown`.
"""

from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.payload import (
    unfollow_config_from_payload,
)


def test_an_account_followed_too_recently_is_kept(screen, make_workflow, base_db):
    base_db.ages.update({"fresh": 1, "old": 10})
    rows = [screen.Row("Fresh", "fresh"), screen.Row("Old", "old")]
    workflow = make_workflow(rows, min_follow_age_days=3)

    stats = workflow.run()

    assert [row.taps for row in rows] == [0, 1]
    assert ("skipped", "fresh", "followed_too_recently") in workflow.events
    assert stats.skipped_recent_follows == 1
    assert stats.unfollowed == 1
    assert ("fresh", 7) in base_db.looked_up


def test_an_account_without_a_known_follow_date_is_kept(screen, make_workflow, base_db):
    rows = [screen.Row("By hand", "followed_by_hand")]
    workflow = make_workflow(rows, min_follow_age_days=3)

    stats = workflow.run()

    assert rows[0].taps == 0
    assert workflow.events == [("skipped", "followed_by_hand", "follow_date_unknown")]
    assert stats.skipped_follow_date_unknown == 1
    assert stats.to_dict()["refusals"] == {"follow_date_unknown": 1}
    assert stats.unfollowed == 0


def test_a_row_without_a_handle_is_kept_when_an_age_is_required(screen, make_workflow, base_db):
    """The following list hides the handle on about half its rows: those cannot be dated."""
    rows = [screen.Row("Keo", None)]
    workflow = make_workflow(rows, min_follow_age_days=3)

    stats = workflow.run()

    assert rows[0].taps == 0
    assert stats.refusals == {"follow_date_unknown": 1}


def test_without_the_acting_account_every_account_is_kept(screen, make_workflow, base_db):
    base_db.ages.update({"old": 30})
    rows = [screen.Row("Old", "old")]
    workflow = make_workflow(rows, min_follow_age_days=3, bot_username=None)

    stats = workflow.run()

    assert rows[0].taps == 0
    assert stats.refusals == {"follow_date_unknown": 1}
    assert base_db.looked_up == []


def test_no_minimum_age_means_no_lookup_and_no_date_rule(screen, make_workflow, base_db):
    rows = [screen.Row("By hand", "followed_by_hand")]
    workflow = make_workflow(rows, min_follow_age_days=0)

    stats = workflow.run()

    assert rows[0].taps == 1
    assert stats.unfollowed == 1
    assert base_db.looked_up == []


def test_the_scheduler_payload_carries_the_minimum_age():
    # Ce que le runner du planificateur envoie depuis le 2026-09-24.
    config = unfollow_config_from_payload({"max_unfollows": 50, "min_follow_age": 3, "delay_min": 3})

    assert config.min_follow_age_days == 3


def test_the_page_payload_has_no_minimum_age():
    config = unfollow_config_from_payload({"max_unfollows": 50, "delay_min": 3, "delay_max": 8})

    assert config.min_follow_age_days == 0
