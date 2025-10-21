"""Centralized real-time statistics manager for Instagram workflows."""

from typing import Dict, Any, Optional
from datetime import datetime
import time
from loguru import logger


class BaseStatsManager:
    
    def __init__(self, workflow_type: str = "unknown"):
        self.workflow_type = workflow_type
        self.start_time = datetime.now()
        self.stats = self._initialize_stats()
        
    def _initialize_stats(self) -> Dict[str, Any]:
        return {
            'users_found': 0,
            'users_interacted': 0,
            'profiles_visited': 0,
            'profiles_filtered': 0,
            'profiles_interacted': 0,
            'skipped': 0,
            'private_profiles': 0,
            
            'likes': 0,
            'likes_made': 0,
            'follows': 0,
            'follows_made': 0,
            'comments': 0,
            'comments_made': 0,
            'stories_watched': 0,
            'story_likes': 0,
            
            'errors': 0,
            'error_list': [],
            
            'workflow_type': self.workflow_type,
            'start_time': self.start_time,
            'duration_seconds': 0
        }
    
    def increment(self, stat_name: str, value: int = 1) -> None:
        if stat_name in self.stats:
            if isinstance(self.stats[stat_name], (int, float)):
                self.stats[stat_name] += value
                logger.debug(f"📊 {stat_name}: {self.stats[stat_name]} (+{value})")
            else:
                logger.warning(f"Cannot increment {stat_name}: type {type(self.stats[stat_name])}")
        else:
            logger.warning(f"Unknown statistic: {stat_name}")
    
    def set_value(self, stat_name: str, value: Any) -> None:
        self.stats[stat_name] = value
        logger.debug(f"📊 {stat_name} = {value}")
    
    def add_error(self, error_message: str) -> None:
        self.increment('errors')
        if isinstance(self.stats['error_list'], list):
            self.stats['error_list'].append(error_message)
        else:
            self.stats['error_list'] = [error_message]
    
    def get_duration(self) -> float:
        duration = (datetime.now() - self.start_time).total_seconds()
        self.stats['duration_seconds'] = duration
        return duration
    
    def get_rate_per_hour(self, stat_name: str) -> float:
        duration_hours = self.get_duration() / 3600
        if duration_hours < (1/60):
            return 0.0
        
        value = self.stats.get(stat_name, 0)
        return value / duration_hours if duration_hours > 0 else 0.0
    
    def format_duration(self) -> str:
        duration = int(self.get_duration())
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            'workflow_type': self.workflow_type,
            'duration': self.format_duration(),
            'duration_seconds': self.get_duration(),
            
            'profiles_visited': self.stats.get('profiles_visited', 0),
            'profiles_interacted': self.stats.get('profiles_interacted', 0),
            'profiles_filtered': self.stats.get('profiles_filtered', 0),
            'skipped': self.stats.get('skipped', 0),
            'private_profiles': self.stats.get('private_profiles', 0),
            
            'likes': max(self.stats.get('likes', 0), self.stats.get('likes_made', 0)),
            'follows': max(self.stats.get('follows', 0), self.stats.get('follows_made', 0)),
            'comments': max(self.stats.get('comments', 0), self.stats.get('comments_made', 0)),
            'stories_watched': self.stats.get('stories_watched', 0),
            
            'likes_per_hour': self.get_rate_per_hour('likes'),
            'follows_per_hour': self.get_rate_per_hour('follows'),
            'profiles_per_hour': self.get_rate_per_hour('profiles_visited'),
            
            'errors': self.stats.get('errors', 0),
            'error_list': self.stats.get('error_list', [])
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return self.stats.copy()
    
    def update_automation_stats(self, automation) -> None:
        if hasattr(automation, 'stats'):
            automation.stats['likes'] = max(
                automation.stats.get('likes', 0),
                self.stats.get('likes', 0),
                self.stats.get('likes_made', 0)
            )
            automation.stats['follows'] = max(
                automation.stats.get('follows', 0),
                self.stats.get('follows', 0),
                self.stats.get('follows_made', 0)
            )
            automation.stats['interactions'] = self.stats.get('profiles_interacted', 0)
            
            logger.debug(f"Automation stats synchronized: {automation.stats}")
    
    def display_stats(self, current_profile: Optional[str] = None) -> None:
        summary = self.get_summary()
        
        logger.info("=" * 80)
        logger.info("📊 REAL-TIME SESSION STATISTICS")
        logger.info("=" * 80)
        
        if current_profile:
            logger.info(f"👤 Last profile processed: @{current_profile}")
        logger.info("-" * 80)
        
        logger.info(f"⏱️  Session duration: {summary['duration']}")
        logger.info(f"❤️  Likes performed: {summary['likes']} ({summary['likes_per_hour']:.1f}/h)")
        logger.info(f"👥 Follows performed: {summary['follows']} ({summary['follows_per_hour']:.1f}/h)")
        logger.info(f"💬 Comments: {summary['comments']}")
        logger.info(f"👤 Profiles visited: {summary['profiles_visited']} ({summary['profiles_per_hour']:.1f}/h)")
        logger.info(f"🚫 Profiles filtered: {summary.get('profiles_filtered', 0)} (criteria not met)")
        if summary.get('skipped', 0) > 0:
            logger.info(f"⏭️ Profiles skipped: {summary['skipped']} (already processed)")
        
        if summary['private_profiles'] > 0:
            logger.info(f"🔒 Private profiles: {summary['private_profiles']}")
        
        logger.info("-" * 80)
        logger.info(f"📈 Total actions: {summary['likes'] + summary['follows'] + summary['comments']}")
        logger.info(f"📊 Total profiles processed: {summary['profiles_visited']}")
        
        if summary['errors'] > 0:
            logger.info(f"❌ Errors: {summary['errors']}")
        
        logger.info("=" * 80)
    
    def display_final_stats(self, workflow_name: str = "SESSION") -> None:
        summary = self.get_summary()
        
        logger.info("=" * 80)
        logger.info(f"🏁 FINAL {workflow_name.upper()} SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"⏱️  Total duration: {summary['duration']}")
        logger.info(f"👤 Profiles visited: {summary['profiles_visited']}")
        logger.info(f"❤️  Likes performed: {summary['likes']}")
        logger.info(f"👥 Follows performed: {summary['follows']}")
        logger.info(f"👁️  Stories watched: {summary['stories_watched']}")
        logger.info(f"🔒 Private profiles: {summary['private_profiles']}")
        logger.info(f"🚫 Profiles filtered: {summary['profiles_filtered']}")
        logger.info(f"⏭️  Profiles skipped: {summary['skipped']}")
        
        if summary['errors'] > 0:
            logger.info(f"❌ Errors: {summary['errors']}")
        
        total_actions = summary['likes'] + summary['follows'] + summary['stories_watched']
        logger.info(f"📈 Total actions: {total_actions}")
        
        if summary['profiles_visited'] > 0:
            success_rate = ((summary['likes'] + summary['follows']) / summary['profiles_visited']) * 100
            logger.info(f"📊 Success rate: {success_rate:.1f}%")
        
        logger.info("=" * 80)
    
    def update_automation_stats(self, automation_obj) -> None:
        if not hasattr(automation_obj, 'stats'):
            return
            
        automation_obj.stats['interactions'] = automation_obj.stats.get('interactions', 0) + 1
        automation_obj.stats['likes'] = automation_obj.stats.get('likes', 0) + max(
            self.stats.get('likes', 0), self.stats.get('likes_made', 0)
        )
        automation_obj.stats['follows'] = automation_obj.stats.get('follows', 0) + max(
            self.stats.get('follows', 0), self.stats.get('follows_made', 0)
        )
        automation_obj.stats['stories_watched'] = automation_obj.stats.get('stories_watched', 0) + \
            self.stats.get('stories_watched', 0)
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.stats.copy()
        result.update(self.get_summary())
        return result
    
    def __str__(self) -> str:
        summary = self.get_summary()
        return (f"BaseStats({self.workflow_type}): "
                f"{summary['profiles_visited']} profiles, "
                f"{summary['likes']} likes, "
                f"{summary['follows']} follows, "
                f"{summary['duration']}")


def create_stats_manager(workflow_type: str) -> BaseStatsManager:
    return BaseStatsManager(workflow_type)
