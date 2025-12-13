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
            
            elif action_type == 'feed':
                return self._run_feed_workflow(action)
                
            else:
                self.logger.warning(f"Unrecognized action type: {action_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing action {action_type}: {e}")
            return False
    
    def _run_target_workflow(self, action: Dict[str, Any]) -> bool:
        if not self.automation._check_action_limits('interact_with_followers', self.automation.active_username):
            self.logger.warning("Interaction with followers blocked by license limits")
            return False
        
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
        self.automation._record_action_performed('interact_with_followers', self.automation.active_username)
        return True
    
    def _run_hashtag_workflow(self, action: Dict[str, Any]) -> bool:
        if not self.automation._check_action_limits('hashtag', self.automation.active_username):
            self.logger.warning("Hashtag interaction blocked by license limits")
            return False
        
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
        
        self.automation._record_action_performed('hashtag', self.automation.active_username)
        
        if result:
            self.logger.debug(f"Hashtag workflow completed: {result.get('users_interacted', 0)} users interacted")
        
        return True
    
    def _run_post_url_workflow(self, action: Dict[str, Any]) -> bool:
        if not self.automation._check_action_limits('post_url', self.automation.active_username):
            self.logger.warning("Post URL interaction blocked by license limits")
            return False
        
        post_url = action.get('post_url')
        if not post_url:
            self.logger.error("No post URL provided for post_url action")
            return False
        
        config = WorkflowConfigBuilder.build_post_url_config(action)
        
        result = self.automation.actions.post_url_business.interact_with_post_likers(
            post_url=post_url,
            config=config
        )
        
        self.automation._record_action_performed('post_url', self.automation.active_username)
        
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        return True
    
    def _run_place_workflow_handler(self, action: Dict[str, Any]) -> bool:
        if not self.automation._check_action_limits('place', self.automation.active_username):
            self.logger.warning("Place interaction blocked by license limits")
            return False
        
        result = self._run_place_workflow_impl(action)
        
        self.automation._record_action_performed('place', self.automation.active_username)
        
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        return True
    
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
                    
                    is_reel = self.automation._is_current_post_reel()
                    if is_reel:
                        self.logger.info("🎬 Post detected as Reel - moving to next")
                        self.automation._scroll_to_next_post()
                        time.sleep(2)
                        continue
                    
                    if self.automation._has_likes_on_current_post():
                        self.logger.info("❤️ Post with likes detected - opening list")
                        
                        if self.automation._open_likes_list():
                            self.logger.info("✅ Likers list opened")
                            time.sleep(2)
                            
                            try:
                                interactions = self.automation._interact_with_likers(
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
                            
                            self.automation._close_likes_popup()
                            time.sleep(1)
                        else:
                            self.logger.warning("❌ Unable to open likes list")
                    else:
                        self.logger.info("💭 No likes on this post - moving to next")
                    
                    self.automation._scroll_to_next_post()
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error processing post in feed: {e}")
                    self.automation._scroll_to_next_post()
                    time.sleep(2)
            
            self.logger.info(f"🎉 Workflow completed: {processed_posts} interactions on {stats['posts_processed']} posts")
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Error in place workflow: {e}")
            return stats
    
    def _run_notifications_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the notifications workflow."""
        if not self.automation._check_action_limits('notifications', self.automation.active_username):
            self.logger.warning("Notifications interaction blocked by license limits")
            return False
        
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
        
        self.automation._record_action_performed('notifications', self.automation.active_username)
        
        # Mettre à jour les stats
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        return result.get('success', False)
    
    def _run_unfollow_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the unfollow workflow."""
        if not self.automation._check_action_limits('unfollow', self.automation.active_username):
            self.logger.warning("Unfollow action blocked by license limits")
            return False
        
        config = {
            'max_unfollows': action.get('max_unfollows', 20),
            'unfollow_delay_range': (
                action.get('min_delay', 30),
                action.get('max_delay', 60)
            ),
            'unfollow_non_followers': action.get('unfollow_non_followers', True),
            'min_days_since_follow': action.get('min_days_since_follow', 3),
            'skip_verified': action.get('skip_verified', True),
            'skip_business': action.get('skip_business', False)
        }
        
        # Utiliser le UnfollowBusiness si disponible
        if hasattr(self.automation, 'unfollow_business'):
            result = self.automation.unfollow_business.run_unfollow_workflow(config)
        else:
            # Créer une instance temporaire
            from ..actions.business.workflows.unfollow import UnfollowBusiness
            unfollow_business = UnfollowBusiness(
                self.automation.device,
                self.automation.session_manager,
                self.automation
            )
            result = unfollow_business.run_unfollow_workflow(config)
        
        self.automation._record_action_performed('unfollow', self.automation.active_username)
        
        # Mettre à jour les stats
        self.automation.stats['unfollows'] = self.automation.stats.get('unfollows', 0) + result.get('unfollows_made', 0)
        
        return result.get('success', False)
    
    def _run_feed_workflow(self, action: Dict[str, Any]) -> bool:
        """Run the feed workflow."""
        if not self.automation._check_action_limits('feed', self.automation.active_username):
            self.logger.warning("Feed interaction blocked by license limits")
            return False
        
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
            'filter_criteria': action.get('filters', {})
        }
        
        # Utiliser le FeedBusiness si disponible
        if hasattr(self.automation, 'feed_business'):
            result = self.automation.feed_business.interact_with_feed(config)
        else:
            # Créer une instance temporaire
            from ..actions.business.workflows.feed import FeedBusiness
            feed_business = FeedBusiness(
                self.automation.device,
                self.automation.session_manager,
                self.automation
            )
            result = feed_business.interact_with_feed(config)
        
        self.automation._record_action_performed('feed', self.automation.active_username)
        
        # Mettre à jour les stats
        self.automation.stats['likes'] += result.get('likes_made', 0)
        self.automation.stats['follows'] += result.get('follows_made', 0)
        self.automation.stats['comments'] += result.get('comments_made', 0)
        self.automation.stats['interactions'] += result.get('users_interacted', 0)
        
        return result.get('success', False)
