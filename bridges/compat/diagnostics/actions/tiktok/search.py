"""Search actions for TikTok compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.search.open")
def open_search(a, p):
    return a.search.open_search()


@action("tt.search.submit")
def search_submit(a, p):
    query = p.get("query", "")
    if not query:
        logger.error("Missing 'query' param")
        return False
    return a.search.search_and_submit(query)


@action("tt.search.click_first")
def search_click_first(a, p):
    return a.search.click_first_video_result()

