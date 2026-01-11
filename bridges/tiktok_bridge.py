#!/usr/bin/env python3
"""
TikTok Bridge for TAKTIK Bot
This script allows the TAKTIK Desktop app to launch TikTok bot sessions programmatically.
It accepts a JSON configuration and runs the TikTok For You workflow.
"""

import sys
import os
import json
import signal
import time
from typing import Optional, Dict, Any
from loguru import logger

# Force UTF-8 encoding for stdout/stderr to support emojis on Windows
# Also disable buffering for real-time output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Configure loguru
logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    colorize=False
)

# Keep a reference to the original stdout buffer
_original_stdout_fd = None
try:
    _original_stdout_fd = os.dup(1)
except Exception:
    pass


def send_message(msg_type: str, **kwargs):
    """Send a structured JSON message to the desktop app."""
    global _original_stdout_fd
    try:
        message = {"type": msg_type, **kwargs}
        msg_bytes = (json.dumps(message) + '\n').encode('utf-8')
        if _original_stdout_fd is not None:
            try:
                os.write(_original_stdout_fd, msg_bytes)
                # Force flush to ensure immediate delivery
                os.fsync(_original_stdout_fd)
            except (OSError, ValueError):
                pass
        else:
            try:
                os.write(1, msg_bytes)
                # Force flush stdout
                try:
                    os.fsync(1)
                except OSError:
                    pass
            except (OSError, ValueError):
                pass
    except Exception:
        pass


def send_status(status: str, message: str = ""):
    """Send status update to desktop app."""
    send_message("status", status=status, message=message)


def send_stats(videos_watched: int = 0, videos_liked: int = 0, users_followed: int = 0, 
               videos_favorited: int = 0, videos_skipped: int = 0, errors: int = 0):
    """Send stats update to desktop app."""
    send_message("stats", stats={
        "videos_watched": videos_watched,
        "videos_liked": videos_liked,
        "users_followed": users_followed,
        "videos_favorited": videos_favorited,
        "videos_skipped": videos_skipped,
        "errors": errors
    })


def send_video_info(author: str, description: str = None, like_count: str = None, 
                    is_liked: bool = False, is_followed: bool = False, is_ad: bool = False):
    """Send current video info to desktop app."""
    send_message("video_info", video={
        "author": author,
        "description": description,
        "like_count": like_count,
        "is_liked": is_liked,
        "is_followed": is_followed,
        "is_ad": is_ad
    })


def send_action(action: str, target: str = ""):
    """Send action event to desktop app."""
    send_message("action", action=action, target=target)


def send_pause(duration: int):
    """Send pause event to desktop app."""
    send_message("pause", duration=duration)


def send_dm_conversation(conversation: Dict[str, Any]):
    """Send a conversation data to desktop app."""
    send_message("dm_conversation", conversation=conversation)


def send_dm_progress(current: int, total: int, name: str):
    """Send DM reading progress to desktop app."""
    send_message("dm_progress", current=current, total=total, name=name)


def send_dm_stats(stats: Dict[str, Any]):
    """Send DM workflow stats to desktop app."""
    send_message("dm_stats", stats=stats)


def send_dm_sent(conversation: str, success: bool, error: str = None):
    """Send DM sent result to desktop app."""
    send_message("dm_sent", conversation=conversation, success=success, error=error)


def send_error(error: str):
    """Send error to desktop app."""
    send_message("error", error=error)


def send_log(level: str, message: str):
    """Send log message to desktop app."""
    send_message("log", level=level, message=message)


# Global workflow reference for signal handling
_workflow = None


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global _workflow
    logger.info("🛑 Received interrupt signal, stopping workflow...")
    send_status("stopping", "Received stop signal")
    if _workflow:
        _workflow.stop()
    sys.exit(0)


def run_for_you_workflow(config: Dict[str, Any]):
    """Run the TikTok For You workflow."""
    global _workflow
    
    device_id = config.get('deviceId')
    if not device_id:
        send_error("No device ID provided")
        return False
    
    logger.info(f"🚀 Starting TikTok For You workflow on device: {device_id}")
    send_status("starting", f"Initializing TikTok For You workflow on {device_id}")
    
    try:
        # Import TikTok modules
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.actions.business.workflows.for_you_workflow import (
            ForYouWorkflow, ForYouConfig
        )
        
        # Create TikTok manager
        logger.info("📱 Connecting to device...")
        send_status("connecting", "Connecting to device")
        
        manager = TikTokManager(device_id=device_id)
        
        # Launch TikTok app
        logger.info("📱 Restarting TikTok (clean state)...")
        send_status("launching", "Restarting TikTok app")
        
        if not manager.restart():
            send_error("Failed to restart TikTok app")
            return False
        
        time.sleep(4)  # Wait for app to fully load
        
        # Create workflow config from frontend config
        workflow_config = ForYouConfig(
            max_videos=config.get('maxVideos', 50),
            min_watch_time=config.get('minWatchTime', 2.0),
            max_watch_time=config.get('maxWatchTime', 8.0),
            like_probability=config.get('likeProbability', 30) / 100.0,
            follow_probability=config.get('followProbability', 10) / 100.0,
            favorite_probability=config.get('favoriteProbability', 5) / 100.0,
            required_hashtags=config.get('requiredHashtags', []),
            excluded_hashtags=config.get('excludedHashtags', []),
            min_likes=config.get('minLikes'),
            max_likes=config.get('maxLikes'),
            max_likes_per_session=config.get('maxLikesPerSession', 50),
            max_follows_per_session=config.get('maxFollowsPerSession', 20),
            skip_already_liked=config.get('skipAlreadyLiked', True),
            skip_ads=config.get('skipAds', True),
            follow_back_suggestions=config.get('followBackSuggestions', False),
            pause_after_actions=config.get('pauseAfterActions', 10),
            pause_duration_min=config.get('pauseDurationMin', 30.0),
            pause_duration_max=config.get('pauseDurationMax', 60.0),
        )
        
        # Create workflow
        logger.info("🎯 Creating For You workflow...")
        send_status("running", "Starting For You workflow")
        
        _workflow = ForYouWorkflow(manager.device_manager.device, workflow_config)
        
        # Set callbacks for real-time updates
        def on_video(video_info):
            send_video_info(
                author=video_info.get('author', 'unknown'),
                description=video_info.get('description'),
                like_count=video_info.get('like_count'),
                is_liked=video_info.get('is_liked', False),
                is_followed=video_info.get('is_followed', False),
                is_ad=video_info.get('is_ad', False)
            )
        
        def on_like(video_info):
            send_action("like", video_info.get('author', 'unknown'))
            logger.info(f"❤️ Liked video by @{video_info.get('author', 'unknown')}")
        
        def on_follow(video_info):
            send_action("follow", video_info.get('author', 'unknown'))
            logger.info(f"👤 Followed @{video_info.get('author', 'unknown')}")
        
        def on_stats(stats_dict):
            send_stats(
                videos_watched=stats_dict.get('videos_watched', 0),
                videos_liked=stats_dict.get('videos_liked', 0),
                users_followed=stats_dict.get('users_followed', 0),
                videos_favorited=stats_dict.get('videos_favorited', 0),
                videos_skipped=stats_dict.get('videos_skipped', 0),
                errors=stats_dict.get('errors', 0)
            )
        
        def on_pause(duration: int):
            send_pause(duration)
            logger.info(f"⏸️ Taking a break for {duration}s")
        
        _workflow.set_on_video_callback(on_video)
        _workflow.set_on_like_callback(on_like)
        _workflow.set_on_follow_callback(on_follow)
        _workflow.set_on_stats_callback(on_stats)
        _workflow.set_on_pause_callback(on_pause)
        
        # Run workflow
        logger.info("▶️ Running workflow...")
        stats = _workflow.run()
        
        # Send final stats
        send_stats(
            videos_watched=stats.videos_watched,
            videos_liked=stats.videos_liked,
            users_followed=stats.users_followed,
            videos_favorited=stats.videos_favorited,
            videos_skipped=stats.videos_skipped,
            errors=stats.errors
        )
        
        logger.success(f"✅ Workflow completed: {stats.to_dict()}")
        send_status("completed", f"Workflow completed: {stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows")
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def run_dm_read_workflow(config: Dict[str, Any]):
    """Run the TikTok DM reading workflow."""
    global _workflow
    
    device_id = config.get('deviceId')
    if not device_id:
        send_error("No device ID provided")
        return False
    
    logger.info(f"📥 Starting TikTok DM reading workflow on device: {device_id}")
    send_status("starting", f"Initializing TikTok DM workflow on {device_id}")
    
    try:
        # Import TikTok modules
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.actions.business.workflows.dm_workflow import (
            DMWorkflow, DMConfig
        )
        
        # Create TikTok manager
        logger.info("📱 Connecting to device...")
        send_status("connecting", "Connecting to device")
        
        manager = TikTokManager(device_id=device_id)
        
        # Launch TikTok app
        logger.info("📱 Restarting TikTok (clean state)...")
        send_status("launching", "Restarting TikTok app")
        
        if not manager.restart():
            send_error("Failed to restart TikTok app")
            return False
        
        time.sleep(4)  # Wait for app to fully load
        
        # Create workflow config from frontend config
        workflow_config = DMConfig(
            max_conversations=config.get('maxConversations', 20),
            skip_notifications=config.get('skipNotifications', True),
            skip_groups=config.get('skipGroups', False),
            only_unread=config.get('onlyUnread', False),
            delay_between_conversations=config.get('delayBetweenConversations', 1.0),
        )
        
        # Create workflow
        logger.info("📥 Creating DM workflow...")
        send_status("running", "Reading DM conversations")
        
        _workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        
        # Set callbacks for real-time updates
        def on_conversation(conv_data):
            send_dm_conversation(conv_data)
            logger.info(f"📖 Read conversation: {conv_data.get('name', 'unknown')}")
        
        def on_stats(stats_dict):
            send_dm_stats(stats_dict)
        
        def on_progress(current, total, name):
            send_dm_progress(current, total, name)
        
        _workflow.set_on_conversation_callback(on_conversation)
        _workflow.set_on_stats_callback(on_stats)
        _workflow.set_on_progress_callback(on_progress)
        
        # Run workflow
        logger.info("▶️ Reading conversations...")
        conversations = _workflow.read_conversations()
        
        # Send final stats
        stats = _workflow.get_stats()
        send_dm_stats(stats.to_dict())
        
        logger.success(f"✅ DM reading completed: {len(conversations)} conversations")
        send_status("completed", f"Read {len(conversations)} conversations")
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"DM workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def run_dm_send_workflow(config: Dict[str, Any]):
    """Run the TikTok DM sending workflow."""
    global _workflow
    
    device_id = config.get('deviceId')
    messages = config.get('messages', [])  # List of {conversation, message}
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    if not messages:
        send_error("No messages to send")
        return False
    
    logger.info(f"📤 Starting TikTok DM sending workflow on device: {device_id}")
    send_status("starting", f"Sending {len(messages)} messages")
    
    try:
        # Import TikTok modules
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.actions.business.workflows.dm_workflow import (
            DMWorkflow, DMConfig
        )
        
        # Create TikTok manager
        logger.info("📱 Connecting to device...")
        send_status("connecting", "Connecting to device")
        
        manager = TikTokManager(device_id=device_id)
        
        # Launch TikTok app
        logger.info("📱 Restarting TikTok (clean state)...")
        send_status("launching", "Restarting TikTok app")
        
        if not manager.restart():
            send_error("Failed to restart TikTok app")
            return False
        
        time.sleep(4)  # Wait for app to fully load
        
        # Create workflow
        workflow_config = DMConfig(
            delay_between_conversations=config.get('delayBetweenMessages', 1.0),
            delay_after_send=config.get('delayAfterSend', 0.5),
        )
        
        _workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        
        # Set callbacks
        def on_message_sent(result):
            send_dm_sent(
                conversation=result.get('conversation', ''),
                success=result.get('success', False),
                error=result.get('error')
            )
        
        def on_stats(stats_dict):
            send_dm_stats(stats_dict)
        
        def on_progress(current, total, name):
            send_dm_progress(current, total, name)
        
        _workflow.set_on_message_sent_callback(on_message_sent)
        _workflow.set_on_stats_callback(on_stats)
        _workflow.set_on_progress_callback(on_progress)
        
        # Send messages
        logger.info(f"▶️ Sending {len(messages)} messages...")
        send_status("running", f"Sending {len(messages)} messages")
        
        results = _workflow.send_bulk_messages(messages)
        
        # Count successes
        sent_count = sum(1 for r in results if r['success'])
        
        # Send final stats
        stats = _workflow.get_stats()
        send_dm_stats(stats.to_dict())
        
        logger.success(f"✅ DM sending completed: {sent_count}/{len(messages)} sent")
        send_status("completed", f"Sent {sent_count}/{len(messages)} messages")
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"DM send error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def run_search_workflow(config: Dict[str, Any]):
    """Run the TikTok Search/Target workflow."""
    global _workflow
    
    device_id = config.get('deviceId')
    search_query = config.get('searchQuery')
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    if not search_query:
        send_error("No search query provided")
        return False
    
    logger.info(f"🔍 Starting TikTok Search workflow on device: {device_id}")
    logger.info(f"🔍 Search query: {search_query}")
    send_status("starting", f"Initializing TikTok Search workflow on {device_id}")
    
    try:
        # Import TikTok modules
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.actions.business.workflows.search_workflow import (
            SearchWorkflow, SearchConfig
        )
        
        # Create TikTok manager
        logger.info("📱 Connecting to device...")
        send_status("connecting", "Connecting to device")
        
        manager = TikTokManager(device_id=device_id)
        
        # Launch TikTok app
        logger.info("📱 Restarting TikTok (clean state)...")
        send_status("launching", "Restarting TikTok app")
        
        if not manager.restart():
            send_error("Failed to restart TikTok app")
            return False
        
        time.sleep(4)  # Wait for app to fully load
        
        # Create workflow config from frontend config
        workflow_config = SearchConfig(
            search_query=search_query,
            max_videos=config.get('maxVideos', 50),
            min_watch_time=config.get('minWatchTime', 2.0),
            max_watch_time=config.get('maxWatchTime', 8.0),
            like_probability=config.get('likeProbability', 30) / 100.0,
            follow_probability=config.get('followProbability', 10) / 100.0,
            favorite_probability=config.get('favoriteProbability', 5) / 100.0,
            min_likes=config.get('minLikes'),
            max_likes=config.get('maxLikes'),
            max_likes_per_session=config.get('maxLikesPerSession', 50),
            max_follows_per_session=config.get('maxFollowsPerSession', 20),
            skip_already_liked=config.get('skipAlreadyLiked', True),
            skip_ads=config.get('skipAds', True),
            pause_after_actions=config.get('pauseAfterActions', 10),
            pause_duration_min=config.get('pauseDurationMin', 30.0),
            pause_duration_max=config.get('pauseDurationMax', 60.0),
        )
        
        # Create workflow
        logger.info(f"🎯 Creating Search workflow for: {search_query}")
        send_status("running", f"Searching for: {search_query}")
        
        _workflow = SearchWorkflow(manager.device_manager.device, workflow_config)
        
        # Set callbacks for real-time updates
        def on_video(video_info):
            send_video_info(
                author=video_info.get('author', 'unknown'),
                description=video_info.get('description'),
                like_count=video_info.get('like_count'),
                is_liked=video_info.get('is_liked', False),
                is_followed=video_info.get('is_followed', False),
                is_ad=video_info.get('is_ad', False)
            )
        
        def on_like(video_info):
            send_action("like", video_info.get('author', 'unknown'))
            logger.info(f"❤️ Liked video by @{video_info.get('author', 'unknown')}")
        
        def on_follow(video_info):
            send_action("follow", video_info.get('author', 'unknown'))
            logger.info(f"👤 Followed @{video_info.get('author', 'unknown')}")
        
        def on_stats(stats_dict):
            send_stats(
                videos_watched=stats_dict.get('videos_watched', 0),
                videos_liked=stats_dict.get('videos_liked', 0),
                users_followed=stats_dict.get('users_followed', 0),
                videos_favorited=stats_dict.get('videos_favorited', 0),
                videos_skipped=stats_dict.get('videos_skipped', 0),
                errors=stats_dict.get('errors', 0)
            )
        
        def on_pause(duration: int):
            send_pause(duration)
            logger.info(f"⏸️ Taking a break for {duration}s")
        
        _workflow.set_on_video_callback(on_video)
        _workflow.set_on_like_callback(on_like)
        _workflow.set_on_follow_callback(on_follow)
        _workflow.set_on_stats_callback(on_stats)
        _workflow.set_on_pause_callback(on_pause)
        
        # Run workflow
        logger.info("▶️ Running search workflow...")
        stats = _workflow.run()
        
        # Send final stats
        send_stats(
            videos_watched=stats.videos_watched,
            videos_liked=stats.videos_liked,
            users_followed=stats.users_followed,
            videos_favorited=stats.videos_favorited,
            videos_skipped=stats.videos_skipped,
            errors=stats.errors
        )
        
        logger.success(f"✅ Search workflow completed: {stats.to_dict()}")
        send_status("completed", f"Search completed: {stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows")
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Search workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def run_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok Followers workflow."""
    global _workflow
    
    device_id = config.get('deviceId')
    search_query = config.get('searchQuery')
    bot_username = config.get('botUsername')  # TikTok account username for database tracking
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    if not search_query:
        send_error("No search query provided")
        return False
    
    logger.info(f"👥 Starting TikTok Followers workflow on device: {device_id}")
    if bot_username:
        logger.info(f"📊 Bot account: @{bot_username}")
    logger.info(f"🔍 Target user: {search_query}")
    send_status("starting", f"Initializing TikTok Followers workflow on {device_id}")
    
    try:
        # Import TikTok modules
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.actions.business.workflows.followers_workflow import (
            FollowersWorkflow, FollowersConfig
        )
        
        # Create TikTok manager
        logger.info("📱 Connecting to device...")
        send_status("connecting", "Connecting to device")
        
        manager = TikTokManager(device_id=device_id)
        
        # Restart TikTok app (force stop + launch) to ensure clean state
        logger.info("📱 Restarting TikTok (clean state)...")
        send_status("launching", "Restarting TikTok app")
        
        if not manager.restart():
            send_error("Failed to restart TikTok app")
            return False
        
        time.sleep(4)  # Wait for app to fully load
        
        # Fetch own profile info for database tracking
        fetched_bot_username = None
        try:
            from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import ProfileActions
            
            logger.info("📊 Fetching own profile info...")
            send_status("fetching_profile", "Fetching your TikTok profile info")
            
            profile_actions = ProfileActions(manager.device_manager.device)
            profile_info = profile_actions.fetch_own_profile()
            
            if profile_info:
                fetched_bot_username = profile_info.username
                logger.info(f"✅ Bot account: @{fetched_bot_username} ({profile_info.display_name})")
                logger.info(f"   Followers: {profile_info.followers_count}, Following: {profile_info.following_count}")
                
                # Send profile info to frontend
                send_message("bot_profile", profile={
                    "username": profile_info.username,
                    "display_name": profile_info.display_name,
                    "followers_count": profile_info.followers_count,
                    "following_count": profile_info.following_count,
                    "likes_count": profile_info.likes_count
                })
            else:
                logger.warning("⚠️ Could not fetch own profile info, database tracking will be limited")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch profile info: {e}")
        
        # Use fetched username if available, otherwise fall back to config
        effective_bot_username = fetched_bot_username or bot_username
        
        # Create workflow config from frontend config
        workflow_config = FollowersConfig(
            search_query=search_query,
            max_followers=config.get('maxFollowers', 20),
            posts_per_profile=config.get('postsPerProfile', 2),
            min_watch_time=config.get('minWatchTime', 5.0),
            max_watch_time=config.get('maxWatchTime', 15.0),
            like_probability=config.get('likeProbability', 70) / 100.0,
            favorite_probability=config.get('favoriteProbability', 30) / 100.0,
            follow_probability=config.get('followProbability', 50) / 100.0,
            max_likes_per_session=config.get('maxLikesPerSession', 50),
            max_follows_per_session=config.get('maxFollowsPerSession', 20),
            min_delay=config.get('minDelay', 1.0),
            max_delay=config.get('maxDelay', 3.0),
            pause_after_actions=config.get('pauseAfterActions', 10),
            pause_duration_min=config.get('pauseDurationMin', 30.0),
            pause_duration_max=config.get('pauseDurationMax', 60.0),
            include_friends=config.get('includeFriends', False),
        )
        
        # Create workflow
        logger.info(f"🎯 Creating Followers workflow for: {search_query}")
        send_status("running", f"Following followers of: {search_query}")
        
        _workflow = FollowersWorkflow(manager.device_manager.device, workflow_config)
        
        # Send workflow start event with target
        send_message("workflow_start", target=search_query)
        
        # Set callbacks for real-time updates
        def on_action(action_info):
            send_action(action_info.get('action', 'unknown'), action_info.get('target', ''))
            logger.info(f"🎯 Action: {action_info.get('action')} on @{action_info.get('target', '')}")
        
        def on_stats(stats_dict):
            send_message("followers_stats", stats={
                "followers_seen": stats_dict.get('followers_seen', 0),
                "profiles_visited": stats_dict.get('profiles_visited', 0),
                "posts_watched": stats_dict.get('posts_watched', 0),
                "likes": stats_dict.get('likes', 0),
                "favorites": stats_dict.get('favorites', 0),
                "follows": stats_dict.get('follows', 0),
                "already_friends": stats_dict.get('already_friends', 0),
                "skipped": stats_dict.get('skipped', 0),
                "errors": stats_dict.get('errors', 0)
            })
        
        def on_pause(duration: int):
            send_pause(duration)
            logger.info(f"⏸️ Taking a break for {duration}s")
        
        _workflow.set_on_action_callback(on_action)
        _workflow.set_on_stats_callback(on_stats)
        _workflow.set_on_pause_callback(on_pause)
        
        # Run workflow
        logger.info("▶️ Running followers workflow...")
        stats = _workflow.run(bot_username=effective_bot_username)
        
        # Send final stats with completion reason
        completion_reason = getattr(stats, 'completion_reason', 'unknown')
        send_message("followers_stats", stats={
            "followers_seen": stats.followers_seen,
            "profiles_visited": stats.profiles_visited,
            "posts_watched": stats.posts_watched,
            "likes": stats.likes,
            "favorites": stats.favorites,
            "follows": stats.follows,
            "already_friends": stats.already_friends,
            "skipped": stats.skipped,
            "errors": stats.errors,
            "completion_reason": completion_reason
        })
        
        logger.success(f"✅ Followers workflow completed: {stats.to_dict()}")
        
        # Send completion status with reason
        send_message("status", status="completed", 
                     message=f"Visited {stats.profiles_visited} profiles, {stats.likes} likes, {stats.follows} follows",
                     completion_reason=completion_reason)
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Followers workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def main():
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check arguments
    if len(sys.argv) < 2:
        send_error("Usage: tiktok_bridge.py <config_file>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    # Load config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        sys.exit(1)
    
    logger.info(f"📋 Loaded config: {json.dumps(config, indent=2)}")
    
    # Get workflow type
    workflow_type = config.get('workflowType', 'for_you')
    
    # Run appropriate workflow
    success = False
    if workflow_type == 'for_you':
        success = run_for_you_workflow(config)
    elif workflow_type == 'dm_read':
        success = run_dm_read_workflow(config)
    elif workflow_type == 'dm_send':
        success = run_dm_send_workflow(config)
    elif workflow_type == 'search':
        success = run_search_workflow(config)
    elif workflow_type == 'followers':
        success = run_followers_workflow(config)
    elif workflow_type == 'hashtag':
        send_error("Hashtag workflow not yet implemented")
    elif workflow_type == 'target':
        # Legacy alias for search workflow
        success = run_search_workflow(config)
    else:
        send_error(f"Unknown workflow type: {workflow_type}")
    
    # Exit
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
