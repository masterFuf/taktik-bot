import os
import time
import signal
import sys
import random
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from taktik.core.shared.diagnostics import capture_screen_snapshot
from .....database.local.service import get_local_database
from ...ui.language import redetect_if_unknown
from ..management.session import stop_reasons
from ..management.session.stop_reasons import StopReason


class WorkflowHelpers:
    def __init__(self, automation):
        self.automation = automation
        self.logger = logger.bind(module="workflow-helpers")
    
    def setup_signal_handlers(self):
        def signal_handler(signum, frame):
            self.logger.info("Stop signal received (Ctrl+C), finalizing session...")
            self.finalize_session(status='INTERRUPTED', reason=stop_reasons.manual_stop())
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def _capture_final_screen(self, reason) -> dict:
        """Keep the last screen of the run, and say where it landed. Never raises.

        The paths travel on `session_stop` rather than through an index of their own: the event
        already carries what the desktop needs to file a finished run, and one more field costs
        nothing. The session id is in the file name too, so a capture stays findable even if the
        event is missed.
        """
        session_id = getattr(self.automation, 'current_session_id', None)
        device = getattr(self.automation, 'device', None)
        label = getattr(reason, 'code', None) or 'session_end'
        try:
            base = capture_screen_snapshot(device, label, session_id=session_id)
        except Exception as exc:  # noqa: BLE001 — a diagnostic must never break a finalisation
            self.logger.debug(f"Could not keep the final screen: {exc}")
            return {}
        if not base:
            return {}
        found = {}
        for key, extension in (('screenshot', '.png'), ('hierarchy', '.xml')):
            path = f'{base}{extension}'
            if os.path.exists(path):
                found[key] = path
        return found

    def finalize_session(self, status='COMPLETED', reason='Limits reached'):
        self.logger.info(f"🏁 Finalizing session: {reason}")
        
        # Mark session as finalized to prevent further iterations
        self.automation.session_finalized = True

        # Freeze the duration before publishing the terminal event. The desktop can
        # remount its recap as soon as session_stop arrives, so relying on its local
        # live timer loses the elapsed value and renders 00:00:00.
        try:
            duration_seconds = max(
                0,
                int(time.time() - self.automation.stats['start_time']),
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            duration_seconds = 0
        
        # Send stop reason to frontend.
        #
        # Additive on purpose: `reason` keeps carrying the English sentence it always carried,
        # so a desktop build that predates the catalogue reads exactly what it read before. A
        # motive from the catalogue adds `reason_code` and `reason_params` next to it, which is
        # what a current build reads instead of matching the sentence with a regular expression.
        import json
        stop_message = {
            "type": "session_stop",
            "status": status,
            "reason": reason,
            "duration_seconds": duration_seconds,
        }
        if isinstance(reason, StopReason):
            stop_message.update(reason.event_fields())
        # The screen the run ended on, kept for every session and not only the failures: an
        # operator asking "where did it stop?" gets an answer instead of a motive to interpret.
        # Taken HERE because the app is force-stopped a few lines below, and with it the evidence.
        stop_message.update(self._capture_final_screen(reason))
        print(json.dumps(stop_message), flush=True)
        
        # Update session in DB
        if hasattr(self.automation, 'current_session_id') and self.automation.current_session_id:
            try:
                # The motive travels to the row, not only to the wire: `session_stop` is consumed
                # by a live panel that closes, and the session then kept nothing but a status.
                self.automation._update_workflow_session(
                    self.automation.current_session_id, status=status, reason=reason,
                )
                self.logger.info(f"✅ Session {self.automation.current_session_id} updated in DB with status: {status}")
            except Exception as e:
                self.logger.error(f"❌ Error updating session {self.automation.current_session_id}: {e}")
        
        # Note: Final stats are already displayed by BaseStatsManager.display_final_stats()
        # No need to display them again here
        
        self._close_instagram()
        
        self.logger.info("🎯 Session ended cleanly")
    
    def _get_package(self) -> str:
        """Resolve active Instagram package (clone-aware)."""
        pkg = getattr(self.automation, 'package_name', None)
        if not pkg:
            from taktik.core.clone import get_active_package
            pkg = get_active_package()
        return pkg

    def _close_instagram(self):
        pkg = self._get_package()
        self.logger.info(f"📱 Closing Instagram ({pkg})...")
        if self.automation.device_manager.stop_app(pkg):
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
        
        self.logger.info(stats_output)
    
    def _handle_post_restart_popups(self):
        """Detect and dismiss popups that may appear after app restart (ad consent, etc.)."""
        try:
            from ...ui.detectors.problematic_page import ProblematicPageDetector
            detector = ProblematicPageDetector(self.automation.actions.device, debug_mode=False)
            result = detector.detect_and_handle_problematic_pages()
            if result.get('detected'):
                self.logger.info(f"📋 Post-restart popup detected: {result.get('page_type', 'unknown')}, closed={result.get('closed')}")
                if result.get('closed'):
                    time.sleep(2)
                    # Check again in case there's a multi-page flow
                    result2 = detector.detect_and_handle_problematic_pages()
                    if result2.get('detected') and result2.get('closed'):
                        self.logger.info(f"📋 Follow-up popup handled: {result2.get('page_type', 'unknown')}")
                        time.sleep(2)
        except Exception as e:
            self.logger.warning(f"Post-restart popup check failed: {e}")

    def initialize_session(self) -> Optional[int]:
        session_settings = self.automation.config.get('session_settings', {})
        skip_initial_restart = bool(session_settings.get('skip_initial_restart', False))

        if skip_initial_restart:
            # The bridge already did the CLEAN restart (force-stop + launch) for a consistent
            # initial state, so the bot must NOT restart again — but Instagram is freshly started,
            # so still dismiss any post-restart popup (ad consent, "what's new", etc.) before we try
            # to detect the account. Otherwise an interstitial covers the nav and detection fails.
            pkg = self._get_package()
            self.logger.info(f"Instagram restarted by the bridge ({pkg}); dismissing any post-restart popups")
            self._handle_post_restart_popups()
        else:
            # Keep the clean restart for standalone bot runs.
            pkg = self._get_package()
            self.logger.info(f"Restarting Instagram ({pkg}) to ensure clean initial state...")
            if self.automation.device_manager.launch_app(pkg, stop_first=True):
                self.logger.info("Instagram restarted successfully")
                wait_time = random.randint(5, 10)
                self.logger.info(f"Waiting {wait_time}s for Instagram to fully load...")
                time.sleep(wait_time)
                self._handle_post_restart_popups()
            else:
                self.logger.warning("Failed to restart Instagram, continuing with current state")

        if not self.automation.active_account_id:
            self.logger.info("Detecting active Instagram account...")
            profile_info = self.automation.get_profile_info(username=None, save_to_db=True, log_result=False)

            # A warm launch (skip_initial_restart) can resume Instagram deep inside
            # another user's profile, which navigate_to_profile_tab cannot always pop
            # out of (a single back per attempt doesn't unwind a multi-level stack),
            # so account detection fails. Recover by forcing one clean restart (a cold
            # start lands on the home feed) and retrying. Failure-path only: a run that
            # already detected the account never reaches this branch, so normal runs
            # are unchanged.
            if skip_initial_restart and not (profile_info and profile_info.get('username')):
                pkg = self._get_package()
                self.logger.warning(
                    f"Account detection failed on warm launch; forcing a clean restart of {pkg} and retrying"
                )
                if self.automation.device_manager.launch_app(pkg, stop_first=True):
                    wait_time = random.randint(5, 10)
                    self.logger.info(f"Waiting {wait_time}s for Instagram to fully load...")
                    time.sleep(wait_time)
                    self._handle_post_restart_popups()
                    profile_info = self.automation.get_profile_info(username=None, save_to_db=True, log_result=False)
                else:
                    self.logger.warning("Failed to restart Instagram during account-detection recovery")

            # We are standing on the account's own profile — the richest screen of the app
            # ("Modifier le profil", "publications", "abonnés", "abonnements"). If the startup
            # dump was too poor to decide the language, this is the second chance the log has
            # been promising; a language already decided is left alone.
            try:
                redetect_if_unknown(self.automation.device)
            except Exception as exc:
                self.logger.debug(f"Language re-detection skipped: {exc}")

            if profile_info and profile_info.get('username'):
                import json
                active_account_msg = {
                    "type": "active_account",
                    "username": profile_info.get('username', ''),
                    "followers": profile_info.get('followers_count', 0),
                    "following": profile_info.get('following_count', 0),
                    "posts": profile_info.get('posts_count', 0),
                }
                print(json.dumps(active_account_msg), flush=True)
                self.logger.info(f"Active account sent to frontend: @{profile_info['username']}")

        if not self.automation.active_account_id:
            self.logger.error("Cannot detect active Instagram account")
            return None

        session_id = self.automation._create_workflow_session()
        if not session_id:
            self.logger.error("Cannot create session, stopping workflow")
            return None

        self.automation.current_session_id = session_id
        self.logger.info(f"Session created with ID: {session_id}")

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
            
            # Determine target type and target from action.
            #
            # A MAPPING, not a chain of elifs, and an explicit entry for the workflows that
            # have no target of their own. Those four (feed, unfollow, the two syncs) used to
            # fall through to the default below and were recorded as USER / "unknown": the
            # session existed, the history simply called it a target run. That is why no Feed
            # line ever appeared in the sessions page — nothing was lost, everything was
            # mislabelled. An unmapped type now says so in the log instead of borrowing an
            # identity from whatever the default happens to be.
            target_type = "USER"
            target = "unknown"

            # action type -> (target_type, key holding the target, or None when there is none)
            _ACTION_TARGETS = {
                'interact_with_followers': ("USER", 'target_username'),
                'hashtag': ("HASHTAG", 'hashtag'),
                'post_url': ("POST_URL", 'post_url'),
                # No target: the run works on our own feed / our own following list.
                'feed': ("FEED", None),
                'unfollow': ("UNFOLLOW", None),
                'sync_following': ("SYNC_FOLLOWING", None),
                'sync_followers_following': ("SYNC_FOLLOWING", None),
            }

            if action_override:
                action_type = action_override.get('type')
                mapping = _ACTION_TARGETS.get(action_type)
                if mapping:
                    target_type, target_key = mapping
                    target = action_override.get(target_key, 'unknown') if target_key else target_type.lower()
                elif action_type:
                    self.logger.warning(
                        f"Unmapped action type '{action_type}' for the session label — "
                        f"recorded as {target_type}. Add it to _ACTION_TARGETS."
                    )
            else:
                # Try to get from config (check both 'steps' and 'actions' for compatibility)
                steps_or_actions = self.automation.config.get('steps') or self.automation.config.get('actions', [])
                
                if steps_or_actions:
                    for action in steps_or_actions:
                        mapping = _ACTION_TARGETS.get(action.get('type'))
                        if not mapping:
                            continue
                        target_type, target_key = mapping
                        target = action.get(target_key, 'unknown') if target_key else target_type.lower()
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
    
    def update_workflow_session(self, session_id: int, status: str = 'COMPLETED', reason: Any = None) -> bool:
        # Every caller of this method ends the session (COMPLETED, INTERRUPTED via the
        # signal handler, ERROR in automation), so finalize with the full snapshot:
        # end_time + stats_* aggregated from interactions. Electron only writes that
        # snapshot on its own manual-stop path — bot-ended sessions used to keep
        # stats_* at 0 and end_time NULL, under-reporting the account's real activity.
        try:
            session_duration = int(time.time() - self.automation.stats['start_time'])

            try:
                local_db = get_local_database()
                # The POSTS counter comes from the run, not from the per-profile aggregation: a
                # workflow that opens no profile writes nothing to the interactions table and
                # therefore came out at zero, then hidden
                # comme session vide.
                posts_engaged = 0
                try:
                    manager = getattr(self.automation.actions, 'stats_manager', None)
                    if manager is not None:
                        posts_engaged = int(manager.stats.get('posts_engaged', 0) or 0)
                except Exception:
                    posts_engaged = 0

                success = local_db.finalize_session(
                    session_id, status,
                    duration_seconds=session_duration,
                    posts_engaged=posts_engaged,
                    stop_reason=reason,
                )

                if success:
                    self.logger.info(f"✅ Session {session_id} finalized ({status})")
                    return True
                else:
                    self.logger.warning(f"⚠️ Session {session_id} finalize failed")
                    return False

            except Exception as db_error:
                self.logger.error(f"❌ Database error finalizing session {session_id}: {db_error}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error finalizing session: {e}")
            return False
