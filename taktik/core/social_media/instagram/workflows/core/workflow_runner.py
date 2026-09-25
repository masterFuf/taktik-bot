import time
from typing import Dict, Any
from loguru import logger

from ..management.config import WorkflowConfigBuilder
from ...actions.business.workflows.common.distribution import (
    ipc_source_progress,
    normalize_distribution,
    run_distributed,
)
from taktik.core.shared.config import resolve_filter_criteria
from taktik.core.shared.telemetry.device_io import measure_device_io
from ..management.session import stop_reasons


def _motive_code(motive: Any) -> str:
    """The code of a stop motive, for a log line."""
    return getattr(motive, 'code', None) or str(motive)


class WorkflowRunner:
    
    def __init__(self, automation):
        self.automation = automation
        self.logger = logger.bind(module="workflow-runner")
    
    def run_workflow_step(self, action: Dict[str, Any]) -> bool:
        """Run one step, and emit what it cost on the phone (dumps, round trips, waits: M1)."""
        with measure_device_io(f"workflow.{action.get('type') or 'unknown'}", source="workflow"):
            return self._dispatch_workflow_step(action)

    def _dispatch_workflow_step(self, action: Dict[str, Any]) -> bool:
        action_type = action.get('type')
        
        if not action_type:
            self.logger.warning("Step without type, ignored")
            return False
        
        self.logger.info(f"Executing step: {action.get('id', action_type)} - {action.get('description', '')}")
        
        try:
            if action_type == 'initialize':
                self.logger.info("Initialization completed")
                return True
                
            elif action_type == 'interact_with_followers':
                return self._run_target_workflow(action)

            elif action_type == 'interact_with_profiles':
                return self._run_profile_list_workflow(action)

            elif action_type == 'hashtag':
                return self._run_hashtag_workflow(action)
                
            elif action_type == 'post_url':
                return self._run_post_url_workflow(action)

            # NOTE: there is no 'notifications' action here. Reading the activity feed is owned
            # by the notifications ENGAGEMENT bridge (`notifications_bridge`, the one the desktop
            # Notifications page and the scheduler node drive) — a single implementation, which
            # also handles persistence, dedup and closing Instagram. The legacy duplicate that
            # lived here treated notifications as just another profile source.
            elif action_type == 'unfollow':
                return self._run_unfollow_workflow(action)
            
            elif action_type == 'sync_following':
                return self._run_sync_following_workflow(action)
            
            elif action_type == 'sync_followers_following':
                return self._run_sync_followers_following_workflow(action)
            
            elif action_type == 'scrape_non_followers':
                return self._run_scrape_non_followers_workflow(action)
            
            elif action_type == 'feed':
                return self._run_feed_workflow(action)
                
            else:
                self.logger.warning(f"Unrecognized action type: {action_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing action {action_type}: {e}")
            return False
    
    def _run_target_workflow(self, action: Dict[str, Any]) -> bool:
        # Support multi-targets
        target_usernames = action.get('target_usernames', [])
        if not target_usernames and 'target_username' in action:
            target_usernames = [action.get('target_username')]
        
        if not target_usernames:
            self.logger.error("No target_username or target_usernames provided for interact_with_followers")
            return False
        
        if len(target_usernames) > 1:
            self.logger.info(f"🎯 Multi-target mode: {len(target_usernames)} targets configured")
        
        config = WorkflowConfigBuilder.build_interaction_config(action)
        
        # Pass all targets to interact_with_followers (the driver distributes the budget)
        result = self.automation.interact_with_followers(
            target_usernames=target_usernames,
            max_interactions=action.get('max_interactions', 10),
            like_posts=action.get('like_posts', True),
            max_likes_per_profile=action.get('max_likes_per_profile', 1),
            config=config
        )
        # Progress signal for the outer loop's no-progress exit (moot for targets today —
        # the driver always finalises — but every runner reports honestly).
        return bool((result or {}).get('processed', 0) > 0)

    def _run_profile_list_workflow(self, action: Dict[str, Any]) -> bool:
        """Interact with the listed profiles themselves (Target Search selection)."""
        target_usernames = action.get('target_usernames', [])
        if not target_usernames and 'target_username' in action:
            target_usernames = [action.get('target_username')]

        if not target_usernames:
            self.logger.error("No target_usernames provided for interact_with_profiles")
            return False

        self.logger.info(f"🎯 Direct mode: interacting with {len(target_usernames)} chosen profiles")

        config = WorkflowConfigBuilder.build_interaction_config(action)

        result = self.automation.interact_with_profiles(
            target_usernames=target_usernames,
            max_interactions=action.get('max_interactions', 10),
            config=config,
        )
        return bool((result or {}).get('processed', 0) > 0)

    def _run_hashtag_workflow(self, action: Dict[str, Any]) -> bool:
        # `hashtags` (list) is the canonical input; the singular `hashtag` is kept for
        # older payloads — historically it carried a raw comma-joined string, so several
        # hashtags reached this runner as ONE tag and the bot searched Instagram for the
        # literal "#tag1,tag2". Split defensively either way.
        hashtags = [
            tag.strip().lstrip('#')
            for raw in (action.get('hashtags') or [action.get('hashtag') or ''])
            for tag in str(raw).split(',')
            if tag.strip().lstrip('#')
        ]

        if not hashtags:
            self.logger.error("No hashtag provided for hashtag action")
            return False

        config = WorkflowConfigBuilder.build_interaction_config(action)

        config['post_criteria'] = action.get('post_criteria', {'min_likes': 100, 'max_likes': 50000})
        config['max_likes_per_profile'] = action.get('max_likes_per_profile', 2)
        # WHAT this run engages: the likers of one post, or the posts themselves. This copy
        # is not optional — `build_interaction_config` is selective, so a key absent here
        # never reaches the workflow, whatever the page and the config builder agreed on.
        # That is exactly how the post-like bounds were lost before.
        if action.get('interaction_mode'):
            config['interaction_mode'] = action['interaction_mode']
        # The explicit plan, with its three boxes and per-post budgets. Copied key by key
        # like the rest: the builder is selective, so a key absent here never reaches the
        # workflow — which is how the like bounds got lost.
        for key in ('engage_posts', 'walk_likers', 'walk_commenters',
                    'max_posts', 'max_likers_per_post', 'max_commenters_per_post'):
            if action.get(key) is not None:
                config[key] = action[key]

        budget = config.get('max_interactions', action.get('max_interactions', 10))
        distribution = normalize_distribution(action.get('distribution'))
        if len(hashtags) > 1:
            self.logger.info(f"🏷️ {len(hashtags)} hashtags, distribution: {distribution}")

        total_interacted = 0
        last_stop_reason = ''

        def run_one_hashtag(tag: str, quota: int):
            nonlocal total_interacted, last_stop_reason
            self.logger.info(f"🏷️ Processing hashtag: #{tag} (quota: {quota})")
            # finalize=False: the driver finalises ONCE below — the per-hashtag runner
            # finalising would end the session after the first tag.
            result = self.automation.hashtag_interaction_manager.interact_with_hashtag_likers(
                hashtag=tag,
                config={**config, 'max_interactions': quota, 'max_interactions_per_session': quota},
                finalize=False,
            )
            interacted = result.get('users_interacted', 0) if result else 0
            total_interacted += interacted
            stop_reason = (result or {}).get('stop_reason') or ''
            if stop_reason:
                last_stop_reason = stop_reason
            return interacted, stop_reasons.ends_the_session(stop_reason)

        run_distributed(hashtags, budget, distribution, run_one_hashtag,
                        on_progress=ipc_source_progress('hashtag'))

        if last_stop_reason and not getattr(self.automation, 'session_finalized', False):
            self.automation.helpers.finalize_session(
                status=stop_reasons.terminal_status(last_stop_reason), reason=last_stop_reason)

        self.logger.debug(f"Hashtag workflow completed: {total_interacted} users interacted")

        # Return True only if we actually interacted with users
        return total_interacted > 0
    
    def _run_post_url_workflow(self, action: Dict[str, Any]) -> bool:
        # `post_urls` (list) is the canonical input; the singular `post_url` covers older
        # payloads. Instagram post URLs never contain commas, so the defensive split is safe.
        post_urls = [
            url.strip()
            for raw in (action.get('post_urls') or [action.get('post_url') or ''])
            for url in str(raw).split(',')
            if url.strip()
        ]
        if not post_urls:
            self.logger.error("No post URL provided for post_url action")
            return False

        config = WorkflowConfigBuilder.build_post_url_config(action)

        budget = config.get('max_interactions', action.get('max_interactions', 10))
        distribution = normalize_distribution(action.get('distribution'))
        if len(post_urls) > 1:
            self.logger.info(f"🔗 {len(post_urls)} post URLs, distribution: {distribution}")

        total_interacted = 0
        last_stop_reason = ''
        # Links that failed in this pass, with their motive (the summary and the panel), and
        # what the session knows of every link (the end of the run).
        failed_now: Dict[str, Any] = {}
        links = self._post_links()

        def run_one_post(url: str, quota: int):
            nonlocal total_interacted, last_stop_reason
            self.logger.info(f"🔗 Processing post: {url} (quota: {quota})")
            # finalize=False: the driver finalises ONCE below — the per-post runner
            # finalising would end the session after the first URL.
            result = self.automation.actions.post_url_business.interact_with_post_likers(
                post_url=url,
                config={**config, 'max_interactions': quota, 'max_interactions_per_session': quota},
                finalize=False,
            )
            result = result or {}
            self.automation.stats['likes'] += result.get('likes_made', 0)
            self.automation.stats['follows'] += result.get('follows_made', 0)
            self.automation.stats['comments'] += result.get('comments_made', 0)
            self.automation.stats['interactions'] += result.get('users_interacted', 0)
            interacted = result.get('users_interacted', 0)
            total_interacted += interacted
            outcome = links.setdefault(url, {'reached': False, 'worked': False})
            if result.get('post_reached'):
                outcome['reached'] = True
            failure = result.get('link_failure')
            if failure:
                # A failure of THIS link (not reached, list closed): logged and counted, and the
                # run goes on to the next link (Kevin, 2026-09-25). It used to end the run.
                failed_now[url] = failure
                self.logger.warning(f"🔗 Link not worked ({_motive_code(failure)}), next link: {url}")
                return interacted, False
            outcome['worked'] = True
            failed_now.pop(url, None)
            stop_reason = result.get('stop_reason') or ''
            if stop_reason:
                last_stop_reason = stop_reason
            return interacted, stop_reasons.ends_the_session(stop_reason)

        run_distributed(post_urls, budget, distribution, run_one_post,
                        on_progress=ipc_source_progress('post_url', failure_of=failed_now.get))

        if failed_now:
            detail = ", ".join(f"{url} ({_motive_code(motive)})" for url, motive in failed_now.items())
            self.logger.warning(
                f"🔗 {len(failed_now)}/{len(post_urls)} post link(s) not worked: {detail}")

        # A run ends on its links' failures only when no link could be worked at all: none
        # reached is `navigation_lost`, reached but none of their lists opened is
        # `list_unavailable`. Otherwise it ends as it would have without the failed links.
        if not last_stop_reason:
            last_stop_reason = self._post_links_end(links)

        if last_stop_reason and not getattr(self.automation, 'session_finalized', False):
            self.automation.helpers.finalize_session(
                status=stop_reasons.terminal_status(last_stop_reason), reason=last_stop_reason)

        # Return True only if we actually interacted with users
        return total_interacted > 0

    def _post_links(self) -> Dict[str, Dict[str, bool]]:
        """What the session knows of each post link: reached (opened on its post) and worked
        (its list walked). Kept across the passes of one session, reset for the next one."""
        session = getattr(self.automation, 'current_session_id', None)
        state = getattr(self, '_post_links_state', None)
        if state is None or state[0] != session:
            state = (session, {})
            self._post_links_state = state
        return state[1]

    @staticmethod
    def _post_links_end(links: Dict[str, Dict[str, bool]]):
        """The motive of a run none of whose links could be worked, or '' otherwise."""
        if not links or any(outcome['worked'] for outcome in links.values()):
            return ''
        if any(outcome['reached'] for outcome in links.values()):
            return stop_reasons.list_unavailable()
        return stop_reasons.navigation_lost()
    
    def _run_unfollow_workflow(self, action: Dict[str, Any]) -> bool:
        """Run one unfollow batch through the one engine, with the whole page setting.

        Until 2026-09-24 this step kept only the maximum, the delays and verified/business, and
        dropped the mode, the lists, the delay since the follow and "bot follows only" before
        calling a loop that tapped every "Following" button from the top. The engine
        (`UnfollowBusiness.run_unfollow_workflow`) now receives every field `config_builder`
        builds, and runs its own syncs.
        """
        unfollow_business = self._get_unfollow_business()

        # The ceilings, counted in unfollows: what is left of the session's maximum and of the
        # day's unfollow budget. A spent ceiling ends the session with its own reason; it used to
        # cap one batch, which the session relaunched until its duration ran out.
        session_limit = action.get('max_unfollows', 50)
        room, cap_reason = self._unfollow_allowance(session_limit)
        if cap_reason:
            self._finalize_on(cap_reason)
            return False

        config = self._unfollow_engine_config(action, session_limit if room is None else room)
        result = unfollow_business.run_unfollow_workflow(config)

        # Update the statistics
        self.automation.stats['unfollows'] = self.automation.stats.get('unfollows', 0) + result.get('unfollows_made', 0)

        # A block, or unfollows the screen keeps refusing, end the session at once: the stop
        # reason travels with the result and the session is finalized with it here.
        stop_reason = result.get('stop_reason')
        if stop_reason:
            self._finalize_on(stop_reason)
            return False

        # A ceiling reached during this batch ends the session too.
        _room, cap_reason = self._unfollow_allowance(session_limit)
        if cap_reason:
            self._finalize_on(cap_reason)
            return False

        # Nobody left to unfollow: the session ends now, with that reason, instead of a batch
        # that would find it out again (review of 2026-09-24).
        if result.get('success') and not result.get('candidates_left'):
            self._finalize_on(stop_reasons.no_unfollow_candidates(
                self.automation.stats.get('unfollows', 0), sum((result.get('refusals') or {}).values())))
            return False

        # Progress means candidates handled: unfollowed, refused on their profile, not in the list.
        # A batch that handled nobody used to report success, and the session relaunched it until
        # its duration ran out, doing nothing but scrolling. Each batch handling at least one of a
        # finite list of candidates, the batches end.
        handled_now = (result.get('unfollows_made', 0) + result.get('unconfirmed', 0)
                       + result.get('not_in_list', 0)
                       + sum((result.get('profile_refusals') or {}).values()))
        return handled_now > 0

    @staticmethod
    def _unfollow_engine_config(action: Dict[str, Any], max_unfollows) -> Dict[str, Any]:
        """Every unfollow field of the step, as the engine reads it."""
        return {
            'max_unfollows': max_unfollows,
            'unfollow_mode': action.get('unfollow_mode', 'non-followers'),
            'unfollow_delay_range': (action.get('min_delay', 2), action.get('max_delay', 5)),
            'skip_verified': action.get('skip_verified', True),
            'skip_business': action.get('skip_business', False),
            'min_days_since_follow': action.get('min_days_since_follow', 3),
            'bot_follows_only': action.get('bot_follows_only', True),
            'whitelist': list(action.get('whitelist') or []),
            'blacklist': list(action.get('blacklist') or []),
        }

    def _unfollow_allowance(self, session_limit):
        """(room, stop_reason) from the session manager; unlimited in its absence."""
        session_manager = getattr(self.automation, 'session_manager', None)
        if session_manager is None or not hasattr(session_manager, 'unfollow_allowance'):
            return None, None
        return session_manager.unfollow_allowance(session_limit)

    def _finalize_on(self, reason) -> None:
        """End the session with `reason`, once."""
        if not getattr(self.automation, 'session_finalized', False):
            self.automation.helpers.finalize_session(
                status=stop_reasons.terminal_status(reason), reason=reason)
    
    def _run_feed_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the feed workflow with every setting of the step.

        `config_builder` is the whitelist of what the page may send. This runner used to list a
        dozen keys again, with defaults of its own, and drop everything else: the feed stories
        (`view_feed_stories`, `story_like_percentage`), the suggestions mode, the ad capture, the
        crawl toggles and the likers budget never reached the workflow, whose catalogue
        defaults applied instead of the operator's settings. The step now goes through whole;
        a key it does not carry takes `FEED_DEFAULTS`, merged by the workflow.
        """
        config = {key: value for key, value in action.items() if key != 'type'}
        config['filter_criteria'] = resolve_filter_criteria(action)

        result = self._get_feed_business().interact_with_feed(config) or {}

        # Update the statistics
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        return result.get('success', False)
    
    def _get_feed_business(self):
        """One FeedBusiness per session, like the unfollow one. A step used to build a new one
        each time, and its stats manager, which counts the posts the session engaged, went with
        it: the finalisation reads that count from `automation.feed_business`."""
        if getattr(self.automation, 'feed_business', None) is None:
            from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness
            self.automation.feed_business = FeedBusiness(
                self.automation.device,
                self.automation.session_manager,
                self.automation,
            )
        return self.automation.feed_business

    def _get_unfollow_business(self):
        """Get or create UnfollowBusiness instance."""
        from taktik.core.social_media.instagram.actions.business.workflows.unfollow import UnfollowBusiness
        
        # One instance per session: it remembers the rows already handled, so a later batch
        # never taps again an unfollow the screen did not confirm.
        if getattr(self.automation, 'unfollow_business', None) is None:
            self.automation.unfollow_business = UnfollowBusiness(
                self.automation.device,
                self.automation.session_manager,
                self.automation,
            )
        return self.automation.unfollow_business
    
    def _run_sync_following_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the sync_following workflow — incremental following list sync + non-follower detection.
        
        Standalone: syncs following list then scrapes non-followers, emits IPC and finalizes.
        """
        import json
        
        unfollow_business = self._get_unfollow_business()
        
        # Sync following list (incremental, sorted by latest)
        sync_stats = unfollow_business.sync_following_list()
        self.logger.info(
            f"📊 Following sync: {sync_stats['new_count']} new, "
            f"{sync_stats['updated_count']} updated, "
            f"stopped_early={sync_stats['stopped_early']}"
        )
        
        # Scrape non-followers category (autonome — détecte l'état de navigation)
        nf_stats = unfollow_business.scrape_non_followers_category()
        self.logger.info(
            f"📊 Fans (followers you do not follow back): {nf_stats['non_followers_count']}, "
            f"{nf_stats['mutuals_count']} mutuals"
        )
        
        # Emit sync_complete IPC message to frontend
        sync_complete_msg = {
            "type": "sync_complete",
            "new_count": sync_stats['new_count'],
            "updated_count": sync_stats['updated_count'],
            "non_followers_count": nf_stats['non_followers_count'],
            "mutuals_count": nf_stats['mutuals_count'],
            "success": sync_stats['success'] and nf_stats['success'],
        }
        print(json.dumps(sync_complete_msg), flush=True)
        
        # Finalize session immediately (sync is a one-shot workflow)
        self.automation.session_finalized = True
        
        return sync_stats['success']
    
    def _run_sync_followers_following_workflow(self, action: Dict[str, Any]) -> bool:
        """Run full followers + following sync workflow.
        
        Steps:
        1. Sync following list (incremental, sorted by latest)
        2. Scrape non-followers category (for mutual detection on following side)
        3. Sync followers list (full scroll)
        4. Emit sync_complete IPC message
        """
        import json
        
        mode = action.get('mode', 'fast')
        unfollow_business = self._get_unfollow_business()
        
        import time
        
        # Step 1/2: Sync following list
        self.logger.info("📊 Step 1/2: Syncing following list...")
        print(json.dumps({"type": "sync_step", "step": "following", "status": "started"}), flush=True)
        
        sync_stats = unfollow_business.sync_following_list({'mode': mode})
        self.logger.info(
            f"📊 Following sync: {sync_stats['new_count']} new, "
            f"{sync_stats['updated_count']} updated, "
            f"stopped_early={sync_stats['stopped_early']}"
        )
        print(json.dumps({
            "type": "sync_step", "step": "following", "status": "completed",
            "new_count": sync_stats['new_count'],
            "updated_count": sync_stats['updated_count'],
        }), flush=True)
        
        # Navigate back to profile before followers sync
        self.logger.debug("Navigating back to profile before followers sync")
        unfollow_business.device.device.press('back')
        time.sleep(1.5)
        
        # Step 2/2: Sync followers list (full scroll)
        self.logger.info("📊 Step 2/2: Syncing followers list...")
        print(json.dumps({"type": "sync_step", "step": "followers", "status": "started"}), flush=True)
        
        followers_stats = unfollow_business.sync_followers_list({'mode': mode})
        self.logger.info(
            f"📊 Followers sync: {followers_stats['new_count']} new, "
            f"{followers_stats['updated_count']} updated, "
            f"{followers_stats['total_seen']} seen"
        )
        print(json.dumps({
            "type": "sync_step", "step": "followers", "status": "completed",
            "new_count": followers_stats['new_count'],
            "updated_count": followers_stats['updated_count'],
            "total_seen": followers_stats['total_seen'],
        }), flush=True)
        
        # Emit final sync_complete IPC message
        sync_complete_msg = {
            "type": "sync_complete",
            "following": {
                "new_count": sync_stats['new_count'],
                "updated_count": sync_stats['updated_count'],
            },
            "followers": {
                "new_count": followers_stats['new_count'],
                "updated_count": followers_stats['updated_count'],
                "total_seen": followers_stats['total_seen'],
            },
            "non_followers_count": 0,
            "mutuals_count": 0,
            "success": sync_stats['success'] and followers_stats['success'],
        }
        print(json.dumps(sync_complete_msg), flush=True)
        
        # Finalize session immediately (sync is a one-shot workflow)
        self.automation.session_finalized = True
        
        return sync_stats['success'] and followers_stats['success']
    
    def _run_scrape_non_followers_workflow(self, action: Dict[str, Any]) -> bool:
        """Run scrape_non_followers as a standalone workflow step.
        
        Self-contained: navigates from any state, unified view or profile.
        """
        import json
        
        unfollow_business = self._get_unfollow_business()
        
        nf_stats = unfollow_business.scrape_non_followers_category()
        self.logger.info(
            f"📊 Fans (followers you do not follow back): {nf_stats['non_followers_count']}, "
            f"{nf_stats['mutuals_count']} mutuals"
        )
        
        # Emit IPC
        msg = {
            "type": "scrape_non_followers_complete",
            "non_followers_count": nf_stats['non_followers_count'],
            "mutuals_count": nf_stats['mutuals_count'],
            "success": nf_stats['success'],
        }
        print(json.dumps(msg), flush=True)
        
        return nf_stats['success']
