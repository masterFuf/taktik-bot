"""A run's BUDGET must never arrive as a filter criterion.

The two halves of this file are the same defect, found twice on the same day.

**Morning.** A qualification pass sent its budget of four profiles as `maxFollowers`. The
evaluator reads that name as "reject any profile with more followers than this", so the pass
rejected every account above four followers -- all of them. Three profiles logged as
`Too many followers (5300000 > 4)`, and `profile_qualification` held zero TikTok rows, because the
AI hook lives inside the branch a filtered profile never enters. The budget was moved to
`maxProfiles` and the symptom went away.

**Afternoon.** A Followers run on @adaluz_cabezas1 visited four profiles and interacted with none:
`Too many followers (73 > 20)`, where 20 was the number of profiles the run was allowed to visit.
Moving the qualification call had cured one caller and left the mechanism standing -- and the
Followers page had been sending its budget under that same name since filtering shipped on
2026-08-29.

The mechanism, now removed: every flat key of a TikTok workflow config was read as a criterion,
and `maxFollowers` means two different things depending on which half of the app you ask. On the
page it is "Followers to process". To the evaluator it is a ceiling. A name is only a criterion
when it sits in a filter BLOCK, where nobody puts a visit budget.
"""

import ast
import re
from pathlib import Path

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

# The payload the Followers page sends for "visit 20 followers of @adaluz_cabezas1" -- the run
# that visited four profiles and interacted with none.
FOLLOWERS_PAYLOAD = {
    'deviceId': '25171JEGR13922', 'workflowType': 'followers',
    'targets': ['adaluz_cabezas1'], 'maxFollowers': 20,
    'maxLikesPerSession': 50, 'maxFollowsPerSession': 20, 'postsPerProfile': 2,
    'likeProbability': 30, 'followProbability': 10,
}

BIG_ACCOUNT = tiktok_profile_for_filtering(
    {'username': 'squeezie', 'followers_count': 5_300_000, 'videos_count': 9},
)

# @jonathan.leiva80, first profile of the run, rejected at 73 followers against a budget of 20.
ORDINARY_ACCOUNT = tiktok_profile_for_filtering(
    {'username': 'jonathan.leiva80', 'followers_count': 73, 'following_count': 120,
     'videos_count': 8, 'bio': 'padel', 'display_name': 'Jonathan Leiva'},
)


def _accepts(payload, profile):
    criteria = resolve_tiktok_filter_criteria(payload)
    if not criteria:
        return True
    return bool(evaluate_tiktok_profile(profile, criteria).get('suitable', True))


class TestBudgetIsNotAFilter:
    def test_a_qualification_pass_rejects_nobody(self):
        assert _accepts(QUALIFICATION_PAYLOAD, BIG_ACCOUNT) is True

    def test_a_followers_run_rejects_nobody_either(self):
        """The afternoon's run, in one line. Twenty was how many profiles to visit."""
        assert _accepts(FOLLOWERS_PAYLOAD, ORDINARY_ACCOUNT) is True
        assert _accepts(FOLLOWERS_PAYLOAD, BIG_ACCOUNT) is True

    def test_neither_budget_becomes_a_follower_ceiling(self):
        assert 'max_followers' not in resolve_tiktok_filter_criteria(QUALIFICATION_PAYLOAD)
        assert 'max_followers' not in resolve_tiktok_filter_criteria(FOLLOWERS_PAYLOAD)


class TestADeclaredFilterStillFilters:
    """The cure must not disarm filtering: a criterion asked for is a criterion applied.

    Asked for means written in the block. That is the whole distinction -- and the earlier version
    of this file asserted the opposite, taking the Followers page's flat budget for a deliberate
    ceiling. It is the assertion that let the defect survive the morning's fix.
    """

    ASKED = {**FOLLOWERS_PAYLOAD, 'filters': {'maxFollowers': 5_000}}

    def test_a_ceiling_in_the_block_rejects_the_big_account(self):
        assert resolve_tiktok_filter_criteria(self.ASKED).get('max_followers') == 5_000
        assert _accepts(self.ASKED, BIG_ACCOUNT) is False

    def test_the_same_run_still_accepts_a_profile_under_that_ceiling(self):
        assert _accepts(self.ASKED, ORDINARY_ACCOUNT) is True

    def test_the_block_wins_over_the_flat_budget_of_the_same_name(self):
        """20 profiles to visit, 5000 followers maximum -- both, without contradiction."""
        assert self.ASKED['maxFollowers'] == 20
        assert resolve_tiktok_filter_criteria(self.ASKED)['max_followers'] == 5_000

    def test_a_floor_still_rejects_a_tiny_account(self):
        tiny = tiktok_profile_for_filtering({'username': 'tiny', 'followers_count': 5})
        assert _accepts({'filters': {'minFollowers': 300}}, tiny) is False


class TestNoOtherConfigKeyCollides:
    """The guard, and the only part of this file that can catch the NEXT one.

    Both incidents were one name meaning two things. This reads the names the bridge actually
    takes off a TikTok config, and the names the evaluator actually reads, and asserts the two
    sets do not touch -- so a config key added tomorrow under a criterion's name fails here
    instead of silently emptying a run.
    """

    ROOT = Path(__file__).resolve().parents[4]
    PLANNING = ROOT / 'bridges' / 'tiktok' / 'workflows' / 'automation' / 'runtime' / 'followers_planning.py'
    EVALUATOR = ROOT / 'taktik' / 'core' / 'shared' / 'filtering' / 'profile_filters.py'

    def _config_keys(self):
        """Every `config.get("x")` the followers planner reads off a flat payload."""
        keys = set()
        for node in ast.walk(ast.parse(self.PLANNING.read_text(encoding='utf-8'))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if getattr(func, 'attr', None) != 'get' or not node.args:
                continue
            if getattr(getattr(func, 'value', None), 'id', None) != 'config':
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                keys.add(argument.value)
        return keys

    def _evaluator_criteria(self):
        source = self.EVALUATOR.read_text(encoding='utf-8')
        return set(re.findall(r"criteria\.get\(['\"]([a-z_]+)['\"]", source))

    def test_the_two_halves_were_actually_read(self):
        """A guard measuring nothing passes forever. Both sides must be non-empty."""
        assert len(self._config_keys()) > 10
        assert len(self._evaluator_criteria()) > 5

    def test_no_flat_config_key_is_read_as_a_criterion(self):
        criteria = self._evaluator_criteria()
        collisions = {
            key for key in self._config_keys()
            if resolve_tiktok_filter_criteria({key: 1}).keys() & criteria
        }
        assert collisions == set(), (
            f"{sorted(collisions)} means one thing to the workflow and another to the evaluator. "
            "Rename the config key, or add it to _WORKFLOW_OWNED_KEYS if the workflow owns it."
        )
