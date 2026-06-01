"""Post actions for Instagram compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("post.like")
def like_post(a, p):
    return a.click.like_post()


@action("post.unlike")
def unlike_post(a, p):
    return a.click.unlike_post()


@action("post.click_comment_button")
def click_comment_btn(a, p):
    return a.click.click_comment_button()


@action("post.click_share_button")
def click_share(a, p):
    return a.click.click_share_button()


@action("post.click_save_button")
def click_save(a, p):
    return a.click.click_save_button()


@action("post.click_likes_count")
def click_likes_count(a, p):
    return a.click.click_likes_count()


@action("post.is_liked")
def is_liked(a, p):
    result = a.click.is_post_already_liked()
    logger.info(f"Post liked: {result}")
    return result

