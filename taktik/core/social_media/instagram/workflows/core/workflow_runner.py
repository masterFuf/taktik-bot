import time
from typing import Dict, Any
from loguru import logger

from ..management.config import WorkflowConfigBuilder
from ...actions.business.workflows.common.distribution import (
    ipc_source_progress,
    normalize_distribution,
    run_distributed,
)


class WorkflowRunner:
    
    def __init__(self, automation):
        self.automation = automation
        self.logger = logger.bind(module="workflow-runner")
    
    def run_workflow_step(self, action: Dict[str, Any]) -> bool:
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
        # Le plan explicite (trois cases + budgets par post). Recopie cle par cle comme le
        # reste : `build_interaction_config` est selectif, donc une cle absente ici n'atteint
        # jamais le workflow — c'est ainsi que les bornes de likes s'etaient perdues.
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
            return interacted, bool(stop_reason)

        run_distributed(hashtags, budget, distribution, run_one_hashtag,
                        on_progress=ipc_source_progress('hashtag'))

        if last_stop_reason and not getattr(self.automation, 'session_finalized', False):
            self.automation.helpers.finalize_session(status='COMPLETED', reason=last_stop_reason)

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
            stop_reason = result.get('stop_reason') or ''
            if stop_reason:
                last_stop_reason = stop_reason
            return interacted, bool(stop_reason)

        run_distributed(post_urls, budget, distribution, run_one_post,
                        on_progress=ipc_source_progress('post_url'))

        if last_stop_reason and not getattr(self.automation, 'session_finalized', False):
            self.automation.helpers.finalize_session(status='COMPLETED', reason=last_stop_reason)

        # Return True only if we actually interacted with users
        return total_interacted > 0
    
    def _run_unfollow_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the unfollow workflow.
        
        Orchestrates: sync_following → scrape_non_followers → unfollow.
        Each sub-step is independent and reusable.
        """
        import time
        
        unfollow_business = self._get_unfollow_business()
        
        # Pré-étape 1: Sync following list (incrémental)
        self.logger.info("📊 Pre-step: syncing following list...")
        sync_stats = unfollow_business.sync_following_list()
        self.logger.info(
            f"📊 Following sync: {sync_stats['new_count']} new, "
            f"{sync_stats['updated_count']} updated"
        )
        
        # Pré-étape 2: Scrape non-followers (autonome — détecte l'état de navigation)
        self.logger.info("📊 Pre-step: scraping non-followers...")
        nf_stats = unfollow_business.scrape_non_followers_category()
        self.logger.info(
            f"📊 Non-followers: {nf_stats['non_followers_count']} non-followers, "
            f"{nf_stats['mutuals_count']} mutuals"
        )
        
        # Étape principale: Unfollow
        config = {
            'max_unfollows': action.get('max_unfollows', 50),
            'unfollow_delay_range': (
                action.get('min_delay', 2),
                action.get('max_delay', 5)
            ),
            'skip_verified': action.get('skip_verified', True),
            'skip_business': action.get('skip_business', False)
        }
        
        # Naviguer vers notre propre profil
        self.logger.info("📱 Navigating to own profile...")
        if not unfollow_business.nav_actions.navigate_to_profile_tab():
            self.logger.error("Failed to navigate to own profile")
            return False
        
        time.sleep(2)
        
        # Ouvrir la liste following
        self.logger.info("📋 Opening following list...")
        if not unfollow_business.nav_actions.open_following_list():
            self.logger.error("Failed to open following list")
            return False
        
        time.sleep(2)
        
        # Lancer le workflow simple (clic direct sur boutons)
        result = unfollow_business.run_simple_unfollow_from_list(config)
        
        # Mettre à jour les stats
        self.automation.stats['unfollows'] = self.automation.stats.get('unfollows', 0) + result.get('unfollows_made', 0)
        
        return result.get('success', False)
    
    def _run_feed_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the feed workflow."""
        config = {
            'max_interactions': action.get('max_interactions', 20),
            'max_posts_to_check': action.get('max_posts_to_check', 30),
            'like_percentage': action.get('like_percentage', 70),
            'follow_percentage': action.get('follow_percentage', 15),
            'comment_percentage': action.get('comment_percentage', 5),
            'story_watch_percentage': action.get('story_watch_percentage', 10),
            'max_likes_per_profile': action.get('max_likes_per_profile', 3),
            'interact_with_post_author': action.get('interact_with_post_author', True),
            'interact_with_post_likers': action.get('interact_with_post_likers', False),
            'skip_reels': action.get('skip_reels', True),
            'skip_ads': action.get('skip_ads', True),
            'filter_criteria': action.get('filters', {}),
            'min_post_likes': action.get('min_post_likes', 0),
            'max_post_likes': action.get('max_post_likes', 0),
            'custom_comments': action.get('custom_comments', [])
        }
        
        # Utiliser le FeedBusiness si disponible
        if hasattr(self.automation, 'feed_business'):
            result = self.automation.feed_business.interact_with_feed(config)
        else:
            # Créer une instance temporaire
            from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness
            feed_business = FeedBusiness(
                self.automation.device,
                self.automation.session_manager,
                self.automation
            )
            result = feed_business.interact_with_feed(config)
        
        # Mettre à jour les stats
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        return result.get('success', False)
    
    def _get_unfollow_business(self):
        """Get or create UnfollowBusiness instance."""
        from taktik.core.social_media.instagram.actions.business.workflows.unfollow import UnfollowBusiness
        
        if hasattr(self.automation, 'unfollow_business'):
            return self.automation.unfollow_business
        return UnfollowBusiness(
            self.automation.device,
            self.automation.session_manager,
            self.automation
        )
    
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
            f"📊 Non-followers: {nf_stats['non_followers_count']} non-followers, "
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
        
        Autonome: navigue depuis n'importe quel état (vue unifiée ou profil).
        """
        import json
        
        unfollow_business = self._get_unfollow_business()
        
        nf_stats = unfollow_business.scrape_non_followers_category()
        self.logger.info(
            f"📊 Non-followers: {nf_stats['non_followers_count']} non-followers, "
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
