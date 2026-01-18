import time
import signal
import sys
import random
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from .....database.local_database import get_local_database


class WorkflowHelpers:
    def __init__(self, automation):
        self.automation = automation
        self.logger = logger.bind(module="workflow-helpers")
    
    def setup_signal_handlers(self):
        def signal_handler(signum, frame):
            self.logger.info("Stop signal received (Ctrl+C), finalizing session...")
            self.finalize_session(status='INTERRUPTED', reason='Manual stop (Ctrl+C)')
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def finalize_session(self, status='COMPLETED', reason='Limits reached'):
        self.logger.info(f"🏁 Finalizing session: {reason}")
        
        # Mark session as finalized to prevent further iterations
        self.automation.session_finalized = True
        
        # Send stop reason to frontend
        import json
        stop_message = {
            "type": "session_stop",
            "status": status,
            "reason": reason
        }
        print(json.dumps(stop_message), flush=True)
        
        # Update session in DB
        if hasattr(self.automation, 'current_session_id') and self.automation.current_session_id:
            try:
                self.automation._update_workflow_session(self.automation.current_session_id, status=status)
                self.logger.info(f"✅ Session {self.automation.current_session_id} updated in DB with status: {status}")
            except Exception as e:
                self.logger.error(f"❌ Error updating session {self.automation.current_session_id}: {e}")
        
        # Note: Final stats are already displayed by BaseStatsManager.display_final_stats()
        # No need to display them again here
        
        self._close_instagram()
        
        self.logger.info("🎯 Session ended cleanly")
    
    def _close_instagram(self):
        self.logger.info("📱 Closing Instagram...")
        if self.automation.device_manager.stop_app("com.instagram.android"):
            self.logger.info("✅ Instagram closed successfully")
        else:
            self.logger.warning("⚠️ Failed to close Instagram")
    
    def display_session_stats(self, profile_username: Optional[str] = None):
        current_time = time.time()
        session_duration = current_time - self.automation.stats['start_time']
        
        stats_output = "\n" + "=" * 80 + "\n"
        stats_output += "📊 SESSION STATISTICS\n"
        stats_output += "=" * 80 + "\n"
        
        if profile_username:
            stats_output += f"👤 Profile: @{profile_username}\n"
        
        stats_output += f"⏱️  Duration: {int(session_duration // 60)}m {int(session_duration % 60)}s\n"
        stats_output += f"👥 Interactions: {self.automation.stats['interactions']}\n"
        stats_output += f"❤️  Likes: {self.automation.stats['likes']}\n"
        stats_output += f"➕ Follows: {self.automation.stats['follows']}\n"
        stats_output += f"➖ Unfollows: {self.automation.stats['unfollows']}\n"
        stats_output += f"💬 Comments: {self.automation.stats['comments']}\n"
        stats_output += f"📖 Stories viewed: {self.automation.stats['stories_viewed']}\n"
        stats_output += f"❤️  Stories liked: {self.automation.stats['stories_liked']}\n"
        stats_output += f"🚫 Profiles skipped: {self.automation.stats['skipped']}\n"
        
        if session_duration > 0:
            interactions_per_minute = (self.automation.stats['interactions'] / session_duration) * 60
            stats_output += f"📈 Interactions/min: {interactions_per_minute:.2f}\n"
        
        if hasattr(self.automation, 'session_manager') and self.automation.session_manager:
            session_settings = self.automation.session_manager.config.get('session_settings', {})
            session_counters = self.automation.session_manager.counters
            
            profiles_limit = session_settings.get('total_profiles_limit', 'unlimited')
            likes_limit = session_settings.get('total_likes_limit', 'unlimited')
            follows_limit = session_settings.get('total_follows_limit', 'unlimited')
            
            stats_output += "\n🎯 CONFIGURED LIMITS:\n"
            stats_output += f"   Profiles processed: {session_counters.get('profiles_processed', 0)}/{profiles_limit}\n"
            stats_output += f"   Total interactions (API): {session_counters.get('total_interactions', 0)}\n"
            stats_output += f"   Likes: {self.automation.stats['likes']}/{likes_limit}\n"
            stats_output += f"   Follows: {self.automation.stats['follows']}/{follows_limit}\n"
        
        stats_output += "=" * 80 + "\n"
        
        print(stats_output)
        self.logger.info(stats_output)
    
    def initialize_session(self) -> Optional[int]:
        # Always restart Instagram to ensure clean state
        # This is necessary because if Instagram is on a random page (like a profile),
        # the workflow cannot navigate properly to start
        self.logger.info("🔄 Restarting Instagram to ensure clean initial state...")
        if self.automation.device_manager.launch_app("com.instagram.android", stop_first=True):
            self.logger.info("✅ Instagram restarted successfully")
            
            # Wait for app to fully load (5-10s)
            wait_time = random.randint(5, 10)
            self.logger.info(f"⏳ Waiting {wait_time}s for Instagram to fully load...")
            time.sleep(wait_time)
        else:
            self.logger.warning("⚠️ Failed to restart Instagram, continuing with current state")
        
        if not self.automation.active_account_id:
            self.logger.info("Detecting active Instagram account...")
            self.automation.get_profile_info(username=None, save_to_db=True, log_result=False)
            
        if not self.automation.active_account_id:
            self.logger.error("Cannot detect active Instagram account")
            return None
            
        session_id = self.automation._create_workflow_session()
        if not session_id:
            self.logger.error("Cannot create session, stopping workflow")
            return None
            
        self.automation.current_session_id = session_id
        self.logger.info(f"Session created with ID: {session_id}")
        
        # Send session_id to frontend for tracking
        import json
        session_start_message = {
            "type": "session_start",
            "session_id": session_id
        }
        print(json.dumps(session_start_message), flush=True)
        
        return session_id
    
    def create_workflow_session(self, action_override: Optional[Dict[str, Any]] = None) -> Optional[int]:
        try:
            if not self.automation.active_account_id:
                self.logger.error("Cannot get active account ID to create session")
                return None
            
            # Determine target type and target from action
            target_type = "USER"
            target = "unknown"
            
            if action_override:
                action_type = action_override.get('type')
                if action_type == 'interact_with_followers':
                    target_type = "USER"
                    target = action_override.get('target_username', 'unknown')
                elif action_type == 'hashtag':
                    target_type = "HASHTAG"
                    target = action_override.get('hashtag', 'unknown')
                elif action_type == 'post_url':
                    target_type = "POST_URL"
                    target = action_override.get('post_url', 'unknown')
                elif action_type == 'place':
                    target_type = "PLACE"
                    target = action_override.get('place_name', 'unknown')
            else:
                # Try to get from config (check both 'steps' and 'actions' for compatibility)
                steps_or_actions = self.automation.config.get('steps') or self.automation.config.get('actions', [])
                
                if steps_or_actions:
                    for action in steps_or_actions:
                        if action.get('type') == 'interact_with_followers':
                            target_type = "USER"
                            target = action.get('target_username', 'unknown')
                            self.logger.debug(f"Session target determined: {target_type} = {target}")
                            break
                        elif action.get('type') == 'hashtag':
                            target_type = "HASHTAG"
                            target = action.get('hashtag', 'unknown')
                            self.logger.debug(f"Session target determined: {target_type} = {target}")
                            break
                        elif action.get('type') == 'post_url':
                            target_type = "POST_URL"
                            target = action.get('post_url', 'unknown')
                            self.logger.debug(f"Session target determined: {target_type} = {target}")
                            break
                        elif action.get('type') == 'place':
                            target_type = "PLACE"
                            target = action.get('place_name', 'unknown')
                            self.logger.debug(f"Session target determined: {target_type} = {target}")
                            break
                
                # Fallback to workflow info if available
                if target == "unknown" and hasattr(self.automation, 'current_workflow_info'):
                    workflow_info = getattr(self.automation, 'current_workflow_info', {})
                    if 'target_username' in workflow_info:
                        target_type = "USER"
                        target = workflow_info['target_username']
                        self.logger.debug(f"Session target retrieved from workflow: {target_type} = {target}")
                    elif 'hashtag' in workflow_info:
                        target_type = "HASHTAG"
                        target = workflow_info['hashtag']
                        self.logger.debug(f"Session target retrieved from workflow: {target_type} = {target}")
                    elif 'post_url' in workflow_info:
                        target_type = "POST_URL"
                        target = workflow_info['post_url']
                        self.logger.debug(f"Session target retrieved from workflow: {target_type} = {target}")
            
            self.logger.info(f"Session created with target_type='{target_type}', target='{target}'")
            
            session_name = f"Auto_{target_type}_{target}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            local_db = get_local_database()
            session_id = local_db.create_session(
                account_id=self.automation.active_account_id,
                session_name=session_name,
                target_type=target_type,
                target=target,
                config_used=self.automation.config
            )
            
            if session_id:
                self.logger.info(f"✅ Session created: {session_name} (ID: {session_id})")
                return session_id
            else:
                self.logger.error("❌ Session creation failed")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error creating session: {e}")
            return None
    
    def update_workflow_session(self, session_id: int, status: str = 'COMPLETED') -> bool:
        try:
            session_duration = int(time.time() - self.automation.stats['start_time'])
            update_data = {
                'status': status,
                'duration_seconds': session_duration
            }
            
            try:
                local_db = get_local_database()
                success = local_db.update_session(session_id, **update_data)
                
                if success:
                    self.logger.info(f"✅ Session {session_id} updated successfully")
                    return True
                else:
                    self.logger.warning(f"⚠️ Session {session_id} update failed")
                    return False
                    
            except Exception as db_error:
                self.logger.error(f"❌ Database error updating session {session_id}: {db_error}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error updating session: {e}")
            return False
