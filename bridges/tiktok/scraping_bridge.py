#!/usr/bin/env python3
"""
TikTok Scraping Bridge - Scrape profiles from TikTok (followers, following, hashtag)
Runs as standalone script, reads config from stdin
"""

import sys
import time
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directories to path for imports when run as standalone script
script_dir = os.path.dirname(os.path.abspath(__file__))
bridges_dir = os.path.dirname(script_dir)
bot_dir = os.path.dirname(bridges_dir)
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.tiktok.base import (
    logger, send_status, send_message, send_error, set_workflow, get_workflow
)


def send_scraping_progress(scraped: int, total: int, current: str):
    """Send scraping progress to frontend."""
    send_message("scraping_progress", scraped=scraped, total=total, current=current)


def send_scraped_profile(profile: Dict[str, Any]):
    """Send a scraped profile to frontend."""
    send_message("scraping_profile", 
                 username=profile.get('username', ''),
                 followersCount=profile.get('followers_count', 0),
                 followingCount=profile.get('following_count', 0),
                 scrapedAt=datetime.now().isoformat())


def send_scraping_completed(total_scraped: int):
    """Send scraping completed event."""
    send_message("scraping_completed", totalScraped=total_scraped)


def get_db_path() -> str:
    """Get the path to the local SQLite database."""
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        return os.path.join(appdata, 'taktik-desktop', 'taktik-data.db')
    elif sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/taktik-desktop/taktik-data.db')
    else:
        return os.path.expanduser('~/.config/taktik-desktop/taktik-data.db')


def save_scraping_session(source_type: str, source_name: str, total_scraped: int, 
                          status: str, duration_seconds: int, platform: str = 'tiktok') -> Optional[int]:
    """Save scraping session to database and return session ID."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if platform column exists, add it if not
        cursor.execute("PRAGMA table_info(scraping_sessions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'platform' not in columns:
            try:
                cursor.execute("ALTER TABLE scraping_sessions ADD COLUMN platform TEXT DEFAULT 'instagram'")
                logger.info("Added 'platform' column to scraping_sessions table")
            except Exception as e:
                logger.warning(f"Could not add platform column: {e}")
        
        cursor.execute("""
            INSERT INTO scraping_sessions (scraping_type, source_type, source_name, total_scraped, status, duration_seconds, platform)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (source_type, source_type, source_name, total_scraped, status, duration_seconds, platform))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Saved scraping session {session_id} to database")
        return session_id
    except Exception as e:
        logger.warning(f"Error saving scraping session: {e}")
        return None


def save_scraped_profile(session_id: int, profile: Dict[str, Any], platform: str = 'tiktok'):
    """Save a scraped profile to database.
    
    Architecture (like Instagram):
    - tiktok_profiles: main table with all profile data
    - tiktok_scraped_profiles: junction table linking scraping sessions to profiles
    """
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        username = profile.get('username', '')
        if not username:
            return
        
        # First, get or create the profile in tiktok_profiles (main table)
        cursor.execute("SELECT profile_id FROM tiktok_profiles WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            profile_id = row['profile_id']
            # Update existing profile with new data if we have better data
            updates = []
            values = []
            
            if profile.get('display_name'):
                updates.append("display_name = COALESCE(?, display_name)")
                values.append(profile['display_name'])
            if profile.get('followers_count', 0) > 0:
                updates.append("followers_count = ?")
                values.append(profile['followers_count'])
            if profile.get('following_count', 0) > 0:
                updates.append("following_count = ?")
                values.append(profile['following_count'])
            if profile.get('likes_count', 0) > 0:
                updates.append("likes_count = ?")
                values.append(profile['likes_count'])
            if profile.get('posts_count', 0) > 0:
                updates.append("videos_count = ?")
                values.append(profile['posts_count'])
            if profile.get('bio'):
                updates.append("biography = COALESCE(?, biography)")
                values.append(profile['bio'])
            if profile.get('is_private') is not None:
                updates.append("is_private = ?")
                values.append(1 if profile['is_private'] else 0)
            if profile.get('is_verified') is not None:
                updates.append("is_verified = ?")
                values.append(1 if profile['is_verified'] else 0)
            
            if updates:
                updates.append("updated_at = datetime('now')")
                values.append(profile_id)
                cursor.execute(
                    f"UPDATE tiktok_profiles SET {', '.join(updates)} WHERE profile_id = ?",
                    tuple(values)
                )
        else:
            # Create new profile
            cursor.execute("""
                INSERT INTO tiktok_profiles (username, display_name, followers_count, following_count,
                                             likes_count, videos_count, is_private, is_verified, biography)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                profile.get('display_name', ''),
                profile.get('followers_count', 0),
                profile.get('following_count', 0),
                profile.get('likes_count', 0),
                profile.get('posts_count', 0),
                1 if profile.get('is_private', False) else 0,
                1 if profile.get('is_verified', False) else 0,
                profile.get('bio', '')
            ))
            profile_id = cursor.lastrowid
        
        # Now create the junction table entry (tiktok_scraped_profiles)
        # This links the scraping session to the profile
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_scraped_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraping_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                is_enriched INTEGER DEFAULT 0,
                scraped_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (scraping_id) REFERENCES scraping_sessions(scraping_id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES tiktok_profiles(profile_id) ON DELETE CASCADE,
                UNIQUE(scraping_id, profile_id)
            )
        """)
        
        # Insert or ignore (in case profile was already scraped in this session)
        cursor.execute("""
            INSERT OR IGNORE INTO tiktok_scraped_profiles (scraping_id, profile_id, is_enriched)
            VALUES (?, ?, ?)
        """, (
            session_id,
            profile_id,
            1 if profile.get('is_enriched', False) else 0
        ))
        
        conn.commit()
        conn.close()
        logger.debug(f"Saved TikTok profile @{username} (profile_id={profile_id}) to session {session_id}")
    except Exception as e:
        logger.warning(f"Error saving scraped profile: {e}")


def update_scraping_session(session_id: int, total_scraped: int, status: str, duration_seconds: int):
    """Update scraping session in database."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE scraping_sessions 
            SET total_scraped = ?, status = ?, duration_seconds = ?, end_time = datetime('now')
            WHERE scraping_id = ?
        """, (total_scraped, status, duration_seconds, session_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Error updating scraping session: {e}")


class TikTokScrapingWorkflow:
    """TikTok Scraping workflow - scrapes profiles without interactions."""
    
    def __init__(self, device_id: str, enrich_profiles: bool = True, max_profiles_to_enrich: int = 50):
        self.device_id = device_id
        self.device = None
        self.manager = None
        self.navigation = None
        self.profile_actions = None
        self.stopped = False
        
        # Enrichment settings
        self.enrich_profiles = enrich_profiles
        self.max_profiles_to_enrich = max_profiles_to_enrich
        
        # Stats
        self.profiles_scraped = 0
        self.session_id = None
        self.start_time = None
    
    def stop(self):
        """Stop the workflow."""
        self.stopped = True
    
    def connect(self) -> bool:
        """Connect to the device and initialize TikTok actions."""
        logger.info(f"Connecting to device: {self.device_id}")
        
        try:
            from taktik.core.social_media.tiktok import TikTokManager
            from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
            
            self.manager = TikTokManager(device_id=self.device_id)
            
            # Must call connect() on device_manager before accessing device
            if not self.manager.device_manager.connect():
                logger.error("Failed to connect to device via device_manager")
                return False
            
            self.device = self.manager.device_manager.device
            if self.device is None:
                logger.error("Device is None after connect")
                return False
            
            # NavigationActions expects device, not device_manager
            self.navigation = NavigationActions(self.device)
            
            logger.info("Connected to device successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def restart_tiktok(self):
        """Restart TikTok for clean state."""
        logger.info("Restarting TikTok...")
        send_status("restarting", "Restarting TikTok app")
        
        if self.manager:
            self.manager.stop()
            time.sleep(1)
            self.manager.launch()
            time.sleep(4)
    
    def scrape_target_followers(self, target_username: str, scrape_type: str, max_profiles: int) -> List[Dict[str, Any]]:
        """Scrape followers or following from a target account."""
        logger.info(f"Scraping {scrape_type} of @{target_username}")
        send_status("navigating", f"Navigating to @{target_username}")
        
        profiles = []
        
        try:
            # Navigate to target user's profile
            if not self.navigation.navigate_to_user_profile(target_username):
                logger.warning(f"Could not find user: @{target_username}")
                return profiles
            
            time.sleep(2)
            
            # Click on followers or following count
            from taktik.core.social_media.tiktok.ui.selectors import PROFILE_SELECTORS
            from taktik.core.social_media.tiktok.actions.core.base_action import BaseAction
            
            # BaseAction expects device, not device_manager
            base_action = BaseAction(self.device)
            
            if scrape_type == 'followers':
                send_status("opening", "Opening followers list")
                # Click on followers count
                if not base_action._find_and_click(PROFILE_SELECTORS.followers_count, timeout=5):
                    logger.warning("Could not click followers count")
                    return profiles
            else:  # following
                send_status("opening", "Opening following list")
                # Click on following count
                if not base_action._find_and_click(PROFILE_SELECTORS.following_count, timeout=5):
                    logger.warning("Could not click following count")
                    return profiles
            
            time.sleep(2)
            
            # Scrape profiles from the list
            send_status("scraping", f"Scraping {scrape_type} profiles")
            
            scraped_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 50
            
            while len(profiles) < max_profiles and scroll_attempts < max_scroll_attempts and not self.stopped:
                # Get raw uiautomator2 device
                raw_device = self.device._device if hasattr(self.device, '_device') else self.device
                
                # Find username elements in the followers list
                # Based on UI dump: com.zhiliaoapp.musically:id/ygv contains the username
                username_elements = raw_device(resourceId="com.zhiliaoapp.musically:id/ygv")
                
                if not username_elements.exists:
                    # Try display name selector as fallback
                    username_elements = raw_device(resourceId="com.zhiliaoapp.musically:id/yhq")
                
                found_new = False
                
                # Also get display names to pair with usernames
                display_name_elements = raw_device(resourceId="com.zhiliaoapp.musically:id/yhq")
                
                # Get clickable list items for enrichment
                list_items = raw_device(resourceId="", className="android.widget.LinearLayout", clickable=True)
                
                for i in range(username_elements.count):
                    if self.stopped:
                        break
                    
                    try:
                        elem = username_elements[i]
                        username_text = elem.get_text()
                        
                        if username_text and username_text not in scraped_usernames:
                            # Clean username
                            username = username_text.replace('@', '').strip()
                            if username and len(username) > 0:
                                scraped_usernames.add(username_text)
                                found_new = True
                                
                                # Try to get display name
                                display_name = ''
                                if display_name_elements.exists and i < display_name_elements.count:
                                    try:
                                        display_name = display_name_elements[i].get_text() or ''
                                    except:
                                        pass
                                
                                profile = {
                                    'username': username,
                                    'display_name': display_name,
                                    'followers_count': 0,
                                    'following_count': 0,
                                    'likes_count': 0,
                                    'posts_count': 0,
                                    'bio': '',
                                    'website': '',
                                    'is_private': False,
                                    'is_verified': False,
                                    'is_enriched': False
                                }
                                
                                # Enrich profile by clicking on it
                                if self.enrich_profiles and len(profiles) < self.max_profiles_to_enrich:
                                    try:
                                        send_status("enriching", f"Enriching @{username}")
                                        
                                        # Click on the username element to go to profile
                                        elem.click()
                                        time.sleep(3.5)  # Wait longer for profile to fully load
                                        
                                        # Extract profile data
                                        enriched_data = self.enrich_profile(username)
                                        if enriched_data:
                                            profile.update(enriched_data)
                                            logger.info(f"Enriched @{username}: {enriched_data.get('followers_count', 0)} followers, bio: {enriched_data.get('bio', '')[:50]}...")
                                        
                                        # Go back to followers list
                                        raw_device.press("back")
                                        time.sleep(2)
                                        
                                    except Exception as e:
                                        logger.warning(f"Error enriching @{username}: {e}")
                                        # Try to go back anyway
                                        try:
                                            raw_device.press("back")
                                            time.sleep(1)
                                        except:
                                            pass
                                
                                profiles.append(profile)
                                self.profiles_scraped += 1
                                
                                # Send progress
                                send_scraping_progress(len(profiles), max_profiles, username)
                                send_scraped_profile(profile)
                                
                                # Save to database
                                if self.session_id:
                                    save_scraped_profile(self.session_id, profile, 'tiktok')
                                
                                enriched_tag = " [enriched]" if profile.get('is_enriched') else ""
                                logger.info(f"Scraped [{len(profiles)}/{max_profiles}]: @{username} ({display_name}){enriched_tag}")
                                
                                if len(profiles) >= max_profiles:
                                    break
                    except Exception as e:
                        logger.warning(f"Error extracting username: {e}")
                        continue
                
                if len(profiles) >= max_profiles:
                    break
                
                # Scroll down to load more
                if not found_new:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0  # Reset if we found new profiles
                
                # Scroll within the RecyclerView area (bounds [0,242] to [720,1430])
                try:
                    raw_device.swipe(360, 1200, 360, 400, duration=0.4)
                    time.sleep(1.5)
                except Exception as e:
                    logger.warning(f"Scroll error: {e}")
                    scroll_attempts += 1
            
            logger.info(f"Scraped {len(profiles)} profiles from @{target_username}'s {scrape_type}")
            
        except Exception as e:
            logger.error(f"Error scraping {scrape_type}: {e}")
        
        return profiles
    
    def enrich_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Visit a user's profile and extract detailed information."""
        logger.info(f"Enriching profile: @{username}")
        
        try:
            raw_device = self.device._device if hasattr(self.device, '_device') else self.device
            
            # Extract profile info from current screen
            profile_data = {
                'username': username,
                'display_name': '',
                'followers_count': 0,
                'following_count': 0,
                'likes_count': 0,
                'posts_count': 0,
                'bio': '',
                'website': '',
                'is_private': False,
                'is_verified': False,
                'is_enriched': True
            }
            
            # Get display name (com.zhiliaoapp.musically:id/qh5 contains @username)
            username_elem = raw_device(resourceId="com.zhiliaoapp.musically:id/qh5")
            if username_elem.exists:
                profile_data['username'] = username_elem.get_text().replace('@', '').strip()
            
            # Get stats - Following, Followers, Likes (all use qfw for count, qfv for label)
            stat_counts = raw_device(resourceId="com.zhiliaoapp.musically:id/qfw")
            stat_labels = raw_device(resourceId="com.zhiliaoapp.musically:id/qfv")
            
            if stat_counts.exists and stat_labels.exists:
                for i in range(min(stat_counts.count, stat_labels.count)):
                    try:
                        count_text = stat_counts[i].get_text() or '0'
                        label_text = stat_labels[i].get_text() or ''
                        
                        # Parse count (handle K, M suffixes)
                        count = self._parse_count(count_text)
                        
                        if 'Following' in label_text:
                            profile_data['following_count'] = count
                        elif 'Followers' in label_text:
                            profile_data['followers_count'] = count
                        elif 'Likes' in label_text:
                            profile_data['likes_count'] = count
                    except Exception as e:
                        logger.warning(f"Error parsing stat: {e}")
            
            # Get bio (usually a Button with the bio text)
            bio_buttons = raw_device(className="android.widget.Button", clickable=True)
            for i in range(bio_buttons.count):
                try:
                    btn = bio_buttons[i]
                    text = btn.get_text() or ''
                    # Bio usually contains emojis or multiple lines
                    if '\n' in text or len(text) > 50:
                        profile_data['bio'] = text
                        break
                except:
                    pass
            
            # Get website (look for link icon or URL pattern)
            link_elems = raw_device(textContains="http")
            if link_elems.exists:
                try:
                    profile_data['website'] = link_elems[0].get_text()
                except:
                    pass
            
            logger.info(f"Enriched @{username}: {profile_data['followers_count']} followers, {profile_data['following_count']} following")
            return profile_data
            
        except Exception as e:
            logger.warning(f"Error enriching profile @{username}: {e}")
            return None
    
    def _parse_count(self, text: str) -> int:
        """Parse count text like '1.2K', '3.5M' to integer."""
        if not text:
            return 0
        
        text = text.strip().replace(',', '').replace(' ', '')
        
        try:
            if 'K' in text.upper():
                return int(float(text.upper().replace('K', '')) * 1000)
            elif 'M' in text.upper():
                return int(float(text.upper().replace('M', '')) * 1000000)
            elif 'B' in text.upper():
                return int(float(text.upper().replace('B', '')) * 1000000000)
            else:
                return int(text)
        except:
            return 0
    
    def scrape_hashtag(self, hashtag: str, max_profiles: int, max_videos: int) -> List[Dict[str, Any]]:
        """Scrape profiles from hashtag videos."""
        logger.info(f"Scraping profiles from #{hashtag}")
        send_status("navigating", f"Navigating to #{hashtag}")
        
        profiles = []
        scraped_usernames = set()
        
        try:
            # Navigate to hashtag
            if not self.navigation.open_search():
                logger.warning("Could not open search")
                return profiles
            
            time.sleep(1)
            
            # Search for hashtag
            if not self.navigation.search_and_submit(f"#{hashtag}"):
                logger.warning(f"Could not search for #{hashtag}")
                return profiles
            
            time.sleep(2)
            
            send_status("scraping", f"Scraping videos from #{hashtag}")
            
            videos_processed = 0
            
            while len(profiles) < max_profiles and videos_processed < max_videos and not self.stopped:
                # Get author username from current video
                raw_device = self.device._device if hasattr(self.device, '_device') else self.device
                
                # Try to find author username
                author_elem = raw_device(resourceId="com.zhiliaoapp.musically:id/title")
                if not author_elem.exists:
                    author_elem = raw_device(resourceId="com.zhiliaoapp.musically:id/ej6")
                
                if author_elem.exists:
                    try:
                        username_text = author_elem.get_text()
                        if username_text:
                            username = username_text.replace('@', '').strip()
                            
                            if username and username not in scraped_usernames:
                                scraped_usernames.add(username)
                                
                                profile = {
                                    'username': username,
                                    'display_name': '',
                                    'followers_count': 0,
                                    'following_count': 0,
                                    'likes_count': 0,
                                    'posts_count': 0,
                                    'bio': '',
                                    'is_private': False,
                                    'is_verified': False
                                }
                                
                                profiles.append(profile)
                                self.profiles_scraped += 1
                                
                                send_scraping_progress(len(profiles), max_profiles, username)
                                send_scraped_profile(profile)
                                
                                if self.session_id:
                                    save_scraped_profile(self.session_id, profile, 'tiktok')
                                
                                logger.info(f"Scraped [{len(profiles)}/{max_profiles}]: @{username}")
                    except Exception as e:
                        logger.warning(f"Error extracting author: {e}")
                
                videos_processed += 1
                
                if len(profiles) >= max_profiles:
                    break
                
                # Swipe to next video
                try:
                    raw_device.swipe(540, 1500, 540, 500, duration=0.2)
                    time.sleep(1.5)
                except Exception as e:
                    logger.warning(f"Swipe error: {e}")
                    break
            
            logger.info(f"Scraped {len(profiles)} profiles from #{hashtag}")
            
        except Exception as e:
            logger.error(f"Error scraping hashtag: {e}")
        
        return profiles
    
    def run(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run the scraping workflow."""
        scrape_type = config.get('type', 'target')
        target_usernames = config.get('targetUsernames', [])
        target_scrape_type = config.get('scrapeType', 'followers')
        hashtag = config.get('hashtag', '')
        max_profiles = config.get('maxProfiles', 500)
        max_videos = config.get('maxPosts', 50)
        save_to_db = config.get('saveToDb', True)
        
        self.start_time = time.time()
        all_profiles = []
        
        # Create scraping session in database
        if save_to_db:
            source_name = target_usernames[0] if target_usernames else hashtag
            self.session_id = save_scraping_session(
                source_type=target_scrape_type.upper() if scrape_type == 'target' else 'HASHTAG',
                source_name=source_name,
                total_scraped=0,
                status='RUNNING',
                duration_seconds=0,
                platform='tiktok'
            )
        
        # Restart TikTok for clean state
        self.restart_tiktok()
        
        try:
            if scrape_type == 'target':
                for username in target_usernames:
                    if self.stopped:
                        break
                    
                    remaining = max_profiles - len(all_profiles)
                    if remaining <= 0:
                        break
                    
                    profiles = self.scrape_target_followers(username, target_scrape_type, remaining)
                    all_profiles.extend(profiles)
                    
                    # Go back to home between targets
                    self.navigation.navigate_to_home()
                    time.sleep(2)
                    
            elif scrape_type == 'hashtag':
                all_profiles = self.scrape_hashtag(hashtag, max_profiles, max_videos)
        
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            send_error(str(e))
        
        # Calculate duration
        duration = int(time.time() - self.start_time)
        
        # Update session in database
        if save_to_db and self.session_id:
            update_scraping_session(
                self.session_id,
                len(all_profiles),
                'COMPLETED' if not self.stopped else 'STOPPED',
                duration
            )
        
        # Send completion
        send_scraping_completed(len(all_profiles))
        
        return {
            'success': True,
            'profiles_scraped': len(all_profiles),
            'duration_seconds': duration
        }


def run_scraping_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok scraping workflow."""
    device_id = config.get('deviceId')
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    # Get enrichment settings from config
    enrich_profiles = config.get('enrichProfiles', True)
    max_profiles_to_enrich = config.get('maxProfilesToEnrich', 50)
    
    logger.info(f"Starting TikTok Scraping workflow on device: {device_id}")
    logger.info(f"Enrichment: {'enabled' if enrich_profiles else 'disabled'}, max: {max_profiles_to_enrich}")
    send_status("starting", "Initializing TikTok Scraping workflow")
    
    # Initialize workflow with enrichment settings
    workflow = TikTokScrapingWorkflow(device_id, enrich_profiles, max_profiles_to_enrich)
    set_workflow(workflow)
    
    if not workflow.connect():
        send_error("Failed to connect to device")
        return False
    
    # Run workflow
    result = workflow.run(config)
    
    # Send final status
    if result.get('success'):
        send_status("completed", f"Scraped {result.get('profiles_scraped', 0)} profiles")
        return True
    else:
        send_status("error", "Scraping failed")
        return False


def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}, stopping workflow...")
    workflow = get_workflow()
    if workflow:
        workflow.stop()
    sys.exit(0)


def main():
    """Main entry point - reads config from stdin."""
    logger.info("TikTok Scraping Bridge started")
    
    # Register signal handlers for graceful shutdown
    import signal
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Read config from stdin
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No configuration received")
            sys.exit(1)
        
        config = json.loads(config_line)
        logger.info(f"Received config: {json.dumps(config, indent=2)[:500]}...")
        
        # Run workflow
        success = run_scraping_workflow(config)
        
        if not success:
            sys.exit(1)
            
    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON config: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        send_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
