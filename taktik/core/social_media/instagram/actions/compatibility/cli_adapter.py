import argparse
import sys
from typing import Dict, Any, Optional
from loguru import logger

from .modern_instagram_actions import ModernInstagramActions
from ..core.device_facade import DeviceFacade


class InstagramCLIAdapter:
    
    def __init__(self):
        self.logger = logger.bind(module="cli-adapter")
        self.actions: Optional[ModernInstagramActions] = None
        
    def setup_device(self, device_id: str = None) -> bool:
        try:
            self.logger.info(f"Setting up device: {device_id or 'auto'}")
            
            import uiautomator2 as u2
            
            if device_id:
                device = u2.connect(device_id)
                self.logger.debug(f"Connecting to specific device: {device_id}")
            else:
                device = u2.connect()
                self.logger.debug("Auto-detecting device")
            
            try:
                device_info = device.info
                self.logger.debug(f"Device detected: {device_info.get('productName', 'Unknown')}")
            except Exception as e:
                self.logger.error(f"Device not accessible: {e}")
                return False
            
            device_facade = DeviceFacade(device)
            
            device_ready = device_facade.ensure_device_ready()
            if not device_ready:
                self.logger.warning("DeviceFacade not fully ready, but continuing for CLI tests")
            else:
                self.logger.debug("DeviceFacade ready for interactions")
            
            self.actions = ModernInstagramActions(device=device_facade)
            
            self.logger.info("Device configured successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Device configuration error: {e}")
            return False
    
    def execute_target_command(self, target_username: str, max_interactions: int = 50,
                              device_id: str = None) -> Dict[str, Any]:
        self.logger.info(f"[CLI] Target command: @{target_username}")
        
        if not self.setup_device(device_id):
            return {'success': False, 'error': 'Device setup failed'}
        
        try:
            result = self.actions.execute_target_workflow(
                target_username=target_username,
                max_interactions=max_interactions
            )
            
            # Note: Final stats are already displayed by BaseStatsManager.display_final_stats()
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Target workflow error: {e}")
            return {'success': False, 'error': str(e)}
    
    def execute_hashtag_command(self, hashtag: str, max_interactions: int = 30,
                               device_id: str = None) -> Dict[str, Any]:

        self.logger.info(f"🏷️ [CLI] Hashtag command: #{hashtag}")
        
        if not self.setup_device(device_id):
            return {'success': False, 'error': 'Device setup failed'}
        
        try:
            result = self.actions.execute_hashtag_workflow(
                hashtag=hashtag,
                max_interactions=max_interactions
            )
            
            # Note: Final stats are already displayed by BaseStatsManager.display_final_stats()
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Hashtag workflow error: {e}")
            return {'success': False, 'error': str(e)}
    
    def execute_post_url_command(self, post_url: str, max_interactions: int = 20,
                                device_id: str = None, **kwargs) -> Dict[str, Any]:

        self.logger.info(f"🔗 [CLI] Post URL command: {post_url}")
        self.logger.info(f"📊 [CLI] Parameters: max_interactions={max_interactions}, kwargs={kwargs}")
        
        if not self.setup_device(device_id):
            return {'success': False, 'error': 'Device setup failed'}
        
        try:
            result = self.actions.execute_post_url_workflow(
                post_url=post_url,
                max_interactions=max_interactions,
                **kwargs
            )
            
            # Note: Final stats are already displayed by BaseStatsManager.display_final_stats()
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Post URL workflow error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _print_result(self, result: Dict[str, Any], workflow_type: str = "WORKFLOW") -> None:

        print(f"\n{'='*60}")
        print(f"WORKFLOW SUMMARY {workflow_type}")
        print(f"{'='*60}")
        
        if result['success']:
            print("Status: SUCCESS")
            
            details = result.get('details', {})
            for key, value in details.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        else:
            print("Status: FAILED")
            if result.get('error'):
                print(f"Error: {result['error']}")
        
        stats = result.get('stats', {})
        if stats:
            print(f"\nSTATISTICS:")
            for key, value in stats.items():
                if key != 'errors':
                    print(f"   {key.replace('_', ' ').title()}: {value}")
            
            errors = stats.get('errors', [])
            if errors:
                print(f"\nERRORS ({len(errors)}):")
                for i, error in enumerate(errors[-5:], 1):
                    print(f"   {i}. {error}")
        
        print(f"{'='*60}\n")


def create_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Instagram Bot - New Modular Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:

  # Target workflow (user's followers)
  python -m taktik.core.social_media.instagram.actions.compatibility.cli_adapter --verbose target test_user --max-interactions 50

  # Hashtag workflow (hashtag posts)
  python -m taktik.core.social_media.instagram.actions.compatibility.cli_adapter --verbose hashtag fitness --max-interactions 30

  # Post URL workflow (post likers)
  python -m taktik.core.social_media.instagram.actions.compatibility.cli_adapter --verbose post-url "https://instagram.com/p/ABC123/" --max-interactions 20

  # Specify a specific device
  python -m taktik.core.social_media.instagram.actions.compatibility.cli_adapter --device-id emulator-5554 target test_user
        """
    )
    
    parser.add_argument(
        '--device-id',
        type=str,
        help='Android device ID (optional, auto-detect by default)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose mode for more logs'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    target_parser = subparsers.add_parser(
        'target',
        help='Target workflow: interact with followers of a user'
    )
    target_parser.add_argument(
        'username',
        type=str,
        help='Target username (without @)'
    )
    target_parser.add_argument(
        '--max-interactions',
        type=int,
        default=50,
        help='Maximum number of interactions (default: 50)'
    )
    
    hashtag_parser = subparsers.add_parser(
        'hashtag',
        help='Hashtag workflow: interact with post authors from a hashtag'
    )
    hashtag_parser.add_argument(
        'hashtag',
        type=str,
        help='Hashtag to explore (without #)'
    )
    hashtag_parser.add_argument(
        '--max-interactions',
        type=int,
        default=30,
        help='Maximum number of interactions (default: 30)'
    )
    
    post_url_parser = subparsers.add_parser(
        'post-url',
        help='Post URL workflow: interact with post likers'
    )
    post_url_parser.add_argument(
        'url',
        type=str,
        help='Instagram post URL'
    )
    post_url_parser.add_argument(
        '--max-interactions',
        type=int,
        default=20,
        help='Maximum number of interactions (default: 20)'
    )
    post_url_parser.add_argument(
        '--like-percentage',
        type=int,
        default=70,
        help='Percentage of profiles to like (default: 70)'
    )
    post_url_parser.add_argument(
        '--follow-percentage',
        type=int,
        default=15,
        help='Percentage of profiles to follow (default: 15)'
    )
    post_url_parser.add_argument(
        '--comment-percentage',
        type=int,
        default=5,
        help='Percentage of profiles to comment (default: 5)'
    )
    post_url_parser.add_argument(
        '--story-watch-percentage',
        type=int,
        default=10,
        help='Percentage of stories to watch (default: 10)'
    )
    post_url_parser.add_argument(
        '--max-likes-per-profile',
        type=int,
        default=3,
        help='Maximum likes per profile (default: 3)'
    )
    post_url_parser.add_argument(
        '--min-followers',
        type=int,
        default=0,
        help='Minimum followers count (default: 0)'
    )
    post_url_parser.add_argument(
        '--max-followers',
        type=int,
        default=100000,
        help='Maximum followers count (default: 100000)'
    )
    post_url_parser.add_argument(
        '--min-posts',
        type=int,
        default=3,
        help='Minimum posts count (default: 3)'
    )
    post_url_parser.add_argument(
        '--max-following',
        type=int,
        default=10000,
        help='Maximum following count (default: 10000)'
    )
    post_url_parser.add_argument(
        '--allow-private',
        action='store_true',
        help='Allow private profiles'
    )
    
    return parser


def main():
    parser = create_cli_parser()
    args = parser.parse_args()
    
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    adapter = InstagramCLIAdapter()
    
    try:
        if args.command == 'target':
            username = args.username.lstrip('@')
            result = adapter.execute_target_command(
                target_username=username,
                max_interactions=args.max_interactions,
                device_id=args.device_id
            )
            
        elif args.command == 'hashtag':
            hashtag = args.hashtag.lstrip('#')
            result = adapter.execute_hashtag_command(
                hashtag=hashtag,
                max_interactions=args.max_interactions,
                device_id=args.device_id
            )
            
        elif args.command == 'post-url':
            result = adapter.execute_post_url_command(
                post_url=args.url,
                max_interactions=args.max_interactions,
                device_id=args.device_id,
                like_percentage=args.like_percentage,
                follow_percentage=args.follow_percentage,
                comment_percentage=args.comment_percentage,
                story_watch_percentage=args.story_watch_percentage,
                max_likes_per_profile=args.max_likes_per_profile,
                min_followers=args.min_followers,
                max_followers=args.max_followers,
                min_posts=args.min_posts,
                max_following=args.max_following,
                allow_private=args.allow_private
            )
        
        sys.exit(0 if result['success'] else 1)
        
    except KeyboardInterrupt:
        logger.info("User interruption")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
