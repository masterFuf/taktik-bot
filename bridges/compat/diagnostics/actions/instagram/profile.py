"""Profile actions for Instagram compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("profile.click_follow")
def click_follow(a, p):
    return a.click.click_follow_button()


@action("profile.click_unfollow")
def click_unfollow(a, p):
    return a.click.click_unfollow_button()


@action("profile.is_follow_available")
def is_follow_available(a, p):
    result = a.click.is_follow_button_available()
    logger.info(f"Follow button available: {result}")
    return result


@action("profile.is_unfollow_available")
def is_unfollow_available(a, p):
    result = a.click.is_unfollow_button_available()
    logger.info(f"Unfollow button available: {result}")
    return result


@action("profile.click_followers_count")
def click_followers(a, p):
    return a.click.click_followers_count()


@action("profile.click_following_count")
def click_following(a, p):
    return a.click.click_following_count()


@action("profile.click_message_button")
def click_message(a, p):
    return a.click.click_message_button()

