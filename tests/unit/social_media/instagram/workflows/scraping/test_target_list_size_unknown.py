"""The size of a target's list the profile could not read is unknown, never the number asked for.

The scraping read the target's followers (or following) on its profile and, when the counter could
not be read, announced the number of profiles asked for as what the list held (`target_info`,
`available_count`): the panel showed a measure nobody had made. Unknown is None now, a count read
(0 included) stays what it is.
"""

from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import plan_target_list_read


def test_a_counter_not_read_leaves_the_list_size_unknown():
    assert plan_target_list_read('followers', {'followers_count': None}, 200) == (None, 200)
    assert plan_target_list_read('following', {'following_count': None}, 50) == (None, 50)


def test_no_profile_read_leaves_the_list_size_unknown():
    assert plan_target_list_read('followers', None, 200) == (None, 200)


def test_a_read_count_bounds_the_read():
    assert plan_target_list_read('followers', {'followers_count': 120}, 200) == (120, 120)
    assert plan_target_list_read('followers', {'followers_count': 900}, 200) == (900, 200)
    assert plan_target_list_read('followers', {'followers_count': 0}, 200) == (0, 0)


def test_a_post_scrape_reads_no_list_size():
    assert plan_target_list_read('posts', {'followers_count': 900}, 200) == (None, 200)
