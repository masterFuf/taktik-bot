import time
from typing import Dict, Any
from loguru import logger

from ..management.config import WorkflowConfigBuilder


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
                
            elif action_type == 'place':
                return self._run_place_workflow_handler(action)
            
            elif action_type == 'notifications':
                return self._run_notifications_workflow(action)
            
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
        
        # Pass all targets to interact_with_followers for smart extraction
        self.automation.interact_with_followers(
            target_usernames=target_usernames,
            max_interactions=action.get('max_interactions', 10),
            like_posts=action.get('like_posts', True),
            max_likes_per_profile=action.get('max_likes_per_profile', 1),
            config=config
        )
        return True
    
    def _run_hashtag_workflow(self, action: Dict[str, Any]) -> bool:
        hashtag = action.get('hashtag')
        hashtags = action.get('hashtags', [])
        
        if hashtag and not hashtags:
            hashtags = [hashtag]
        
        if not hashtags:
            self.logger.error("No hashtag provided for hashtag action")
            return False
        
        config = WorkflowConfigBuilder.build_interaction_config(action)
        
        config['post_criteria'] = action.get('post_criteria', {'min_likes': 100, 'max_likes': 50000})
        config['max_likes_per_profile'] = action.get('max_likes_per_profile', 2)
        
        hashtag_to_process = hashtags[0] if hashtags else None
        
        if not hashtag_to_process:
            self.logger.error("Empty hashtag list")
            return False
        
        self.logger.info(f"🏷️ Processing hashtag: #{hashtag_to_process}")
        self.logger.debug(f"📊 Config: post_criteria={config['post_criteria']}, max_likes_per_profile={config['max_likes_per_profile']}")
        
        result = self.automation.hashtag_interaction_manager.interact_with_hashtag_likers(
            hashtag=hashtag_to_process,
            config=config
        )
        
        users_interacted = result.get('users_interacted', 0) if result else 0
        self.logger.debug(f"Hashtag workflow completed: {users_interacted} users interacted")
        
        # Return True only if we actually interacted with users
        return users_interacted > 0
    
    def _run_post_url_workflow(self, action: Dict[str, Any]) -> bool:
        post_url = action.get('post_url')
        if not post_url:
            self.logger.error("No post URL provided for post_url action")
            return False
        
        config = WorkflowConfigBuilder.build_post_url_config(action)
        
        result = self.automation.actions.post_url_business.interact_with_post_likers(
            post_url=post_url,
            config=config
        )
        
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        # Return True only if we actually interacted with users
        return result.get('users_interacted', 0) > 0
    
    def _run_place_workflow_handler(self, action: Dict[str, Any]) -> bool:
        result = self._run_place_workflow_impl(action)
        
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        # Return True only if we actually interacted with users
        return result.get('users_interacted', 0) > 0
    
    def _run_place_workflow_impl(self, action: Dict[str, Any]) -> Dict[str, int]:
        import time
        import os
        
        place_name = action.get('place_name', '')
        max_users = action.get('max_users', 20)
        max_posts_check = int(action.get('max_posts_to_check', 5))
        like_percentage = float(action.get('like_percentage', 0)) / 100
        follow_percentage = float(action.get('follow_percentage', 0)) / 100
        filters = action.get('filters', {})
        
        stats = {
            "likes_made": 0,
            "follows_made": 0,
            "comments_made": 0,
            "users_interacted": 0,
            "posts_processed": 0
        }
        
        try:
            if not self.automation.nav_actions.navigate_to_search():
                self.logger.error("❌ Impossible de naviguer vers la recherche")
                return stats
                
            if not self.automation.nav_actions.search_place(place_name):
                self.logger.error(f"❌ Impossible de rechercher le lieu '{place_name}'")
                return stats
                
            if not self.automation.nav_actions.click_search_suggestion(place_name):
                self.logger.error("❌ Impossible de cliquer sur la suggestion de recherche")
                return stats
                
            if not self.automation.nav_actions.navigate_to_places_tab():
                self.logger.error("❌ Impossible de naviguer vers l'onglet Places")
                return stats
                
            if not self.automation.nav_actions.select_first_place_result():
                self.logger.error("❌ Impossible de sélectionner le premier résultat")
                return stats
                
            from ..views.place_view import PlaceView
            place_view = PlaceView(self.automation.device)
            
            if not place_view.switch_to_top_posts():
                self.logger.warning("⚠️ Impossible de basculer vers Top posts, continuons...")
                
            self.logger.info("🎯 New strategy: Navigating feed instead of grid")
            
            posts = place_view.get_visible_posts()
            if not posts:
                self.logger.error("❌ Aucun post trouvé dans le lieu")
                return stats
            
            first_post = posts[0]
            self.logger.info("📱 Opening first post to access feed")
            first_post['element'].click()
            time.sleep(3)
            
            processed_posts = 0
            posts_checked = 0
            
            while processed_posts < max_users and posts_checked < max_posts_check:
                try:
                    posts_checked += 1
                    self.logger.info(f"📱 Analyzing post {posts_checked}/{max_posts_check}")
                    
                    is_reel = self.automation.ui_helpers.is_current_post_reel()
                    if is_reel:
                        self.logger.info("🎬 Post detected as Reel - moving to next")
                        self.automation.ui_helpers.scroll_to_next_post()
                        time.sleep(2)
                        continue
                    
                    if self.automation.ui_helpers.has_likes_on_current_post():
                        self.logger.info("❤️ Post with likes detected - opening list")
                        
                        if self.automation.ui_helpers.open_likes_list():
                            self.logger.info("✅ Likers list opened")
                            time.sleep(2)
                            
                            try:
                                interactions = self.automation.ui_helpers.interact_with_likers(
                                    max_interactions=min(5, max_users - processed_posts),
                                    like_percentage=like_percentage,
                                    follow_percentage=follow_percentage,
                                    filters=filters
                                )
                                stats["users_interacted"] += interactions
                                processed_posts += interactions
                                stats["posts_processed"] += 1
                                
                                self.logger.info(f"✅ {interactions} interactions performed on this post")
                                
                            except Exception as e:
                                self.logger.error(f"❌ Error interacting with likers: {e}")
                            
                            self.automation.ui_helpers.close_likes_popup()
                            time.sleep(1)
                        else:
                            self.logger.warning("❌ Unable to open likes list")
                    else:
                        self.logger.info("💭 No likes on this post - moving to next")
                    
                    self.automation.ui_helpers.scroll_to_next_post()
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error processing post in feed: {e}")
                    self.automation.ui_helpers.scroll_to_next_post()
                    time.sleep(2)
            
            self.logger.info(f"🎉 Workflow completed: {processed_posts} interactions on {stats['posts_processed']} posts")
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Error in place workflow: {e}")
            return stats
    
    def _run_notifications_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the notifications workflow."""
        config = {
            'max_interactions': action.get('max_interactions', 20),
            'like_percentage': action.get('like_percentage', 70),
            'follow_percentage': action.get('follow_percentage', 15),
            'comment_percentage': action.get('comment_percentage', 5),
            'story_watch_percentage': action.get('story_watch_percentage', 10),
            'max_likes_per_profile': action.get('max_likes_per_profile', 3),
            'notification_types': action.get('notification_types', ['likes', 'follows', 'comments']),
            'filter_criteria': action.get('filters', {})
        }
        
        # Utiliser le NotificationsBusiness si disponible
        if hasattr(self.automation, 'notifications_business'):
            result = self.automation.notifications_business.interact_with_notifications(config)
        else:
            # Créer une instance temporaire
            from ..actions.business.workflows.notifications import NotificationsBusiness
            notifications_business = NotificationsBusiness(
                self.automation.device,
                self.automation.session_manager,
                self.automation
            )
            result = notifications_business.interact_with_notifications(config)
        
        # Mettre à jour les stats
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        return result.get('success', False)
    
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
        
        # Step 1: Sync following list (incremental)
        self.logger.info("📊 Step 1/3: Syncing following list...")
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
        
        # Step 2: Scrape non-followers category (mutual detection)
        self.logger.info("📊 Step 2/3: Detecting non-followers...")
        print(json.dumps({"type": "sync_step", "step": "non_followers", "status": "started"}), flush=True)
        
        nf_stats = unfollow_business.scrape_non_followers_category()
        self.logger.info(
            f"📊 Non-followers: {nf_stats['non_followers_count']} non-followers, "
            f"{nf_stats['mutuals_count']} mutuals"
        )
        print(json.dumps({
            "type": "sync_step", "step": "non_followers", "status": "completed",
            "non_followers_count": nf_stats['non_followers_count'],
            "mutuals_count": nf_stats['mutuals_count'],
        }), flush=True)
        
        # Step 3: Sync followers list (full scroll)
        self.logger.info("📊 Step 3/3: Syncing followers list...")
        print(json.dumps({"type": "sync_step", "step": "followers", "status": "started"}), flush=True)
        
        # Navigate back to profile first (we may be in the non-followers view)
        self.logger.debug("Pressing back to return to profile before followers sync")
        unfollow_business.device.device.press('back')
        import time
        time.sleep(1)
        unfollow_business.device.device.press('back')
        time.sleep(1)
        
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
            "non_followers_count": nf_stats['non_followers_count'],
            "mutuals_count": nf_stats['mutuals_count'],
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
