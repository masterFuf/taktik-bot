"""A run's BUDGET must never arrive as a filter criterion.

Every flat key of a TikTok workflow payload is read as a filter criterion, and `maxFollowers` is
aliased to `max_followers` — "reject any profile with more followers than this". A qualification
pass that sent its budget of four profiles as `maxFollowers` therefore rejected every account with
more than four followers, which is all of them.

Measured on 2026-09-02: three profiles rejected as `Too many followers (5300000 > 4)`, and
`profile_qualification` held zero TikTok rows, because the AI hook runs inside the branch a
filtered profile never enters.

The budget travels as `maxProfiles`, which the runner reads first and the evaluator does not know.
"""

from taktik.core.social_media.tiktok.actions.business.workflows.followers.filtering import (
    evaluate_tiktok_profile,
    resolve_tiktok_filter_criteria,
    tiktok_profile_for_filtering,
)

# The payload the qualification dialog sends for four handles, minus what does not matter here.
QUALIFICATION_PAYLOAD = {
    'deviceId': 'device', 'workflowType': 'target_profiles',
    'profiles': ['a', 'b', 'c', 'd'], 'maxProfiles': 4,
    'postsPerProfile': 0, 'likeProbability': 0, 'followProbability': 0, 'favoriteProbability': 0,
    'ai': {'enabled': True, 'profileAnalysis': True},
}

BIG_ACCOUNT = tiktok_profile_for_filtering(
    {'username': 'squeezie', 'followers_count': 5_300_000, 'videos_count': 9},
)


def _accepts(payload, profile):
    criteria = resolve_tiktok_filter_criteria(payload)
    if not criteria:
        return True
    return bool(evaluate_tiktok_profile(profile, criteria).get('suitable', True))


class TestBudgetIsNotAFilter:
    def test_a_qualification_pass_rejects_nobody(self):
        assert _accepts(QUALIFICATION_PAYLOAD, BIG_ACCOUNT) is True

    def test_the_budget_key_is_not_a_follower_ceiling(self):
        criteria = resolve_tiktok_filter_criteria(QUALIFICATION_PAYLOAD)
        assert 'max_followers' not in criteria

    def test_the_old_shape_is_what_rejected_everything(self):
        # Kept as the regression's own record: the same run, with the budget in `maxFollowers`.
        old = {**QUALIFICATION_PAYLOAD}
        del old['maxProfiles']
        old['maxFollowers'] = 4
        assert resolve_tiktok_filter_criteria(old).get('max_followers') == 4
        assert _accepts(old, BIG_ACCOUNT) is False


class TestARealFilterStillFilters:
    """The fix must not disarm the Followers workflow, which does mean this as a criterion."""

    def test_max_followers_still_rejects_when_asked_for(self):
        walking_followers = {'maxFollowers': 1000, 'targets': ['someone']}
        assert resolve_tiktok_filter_criteria(walking_followers).get('max_followers') == 1000
        assert _accepts(walking_followers, BIG_ACCOUNT) is False

    def test_min_followers_still_rejects_when_asked_for(self):
        small = tiktok_profile_for_filtering(
            {'username': 'tiny', 'followers_count': 5, 'videos_count': 9},
        )
        assert _accepts({'minFollowers': 300}, small) is False
