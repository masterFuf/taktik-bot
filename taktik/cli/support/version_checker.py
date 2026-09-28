"""
Version checker utility to notify users of available updates.
"""

import requests
import logging
from typing import Optional, Tuple
from packaging import version

logger = logging.getLogger(__name__)


class VersionChecker:
    """Check for new versions of Taktik Bot on GitHub."""
    
    GITHUB_API_URL = "https://api.github.com/repos/masterFuf/taktik-bot/releases/latest"
    GITHUB_RELEASES_URL = "https://github.com/masterFuf/taktik-bot/releases"
    
    def __init__(self, current_version: str, timeout: int = 5):
        """
        Initialize version checker.
        
        Args:
            current_version: Current installed version
            timeout: Request timeout in seconds
        """
        self.current_version = current_version
        self.timeout = timeout
    
    def get_latest_version(self) -> Optional[str]:
        """
        Fetch the latest version from GitHub releases.
        
        Returns:
            Latest version string or None if failed
        """
        try:
            response = requests.get(
                self.GITHUB_API_URL,
                timeout=self.timeout,
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            response.raise_for_status()
            
            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")
            
            return latest_version if latest_version else None
            
        except requests.RequestException as e:
            logger.debug(f"Failed to check for updates: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error checking version: {e}")
            return None
    
    def check_for_updates(self) -> Tuple[bool, Optional[str]]:
        """
        Check if a new version is available.
        
        Returns:
            Tuple of (update_available, latest_version)
        """
        latest = self.get_latest_version()
        
        if not latest:
            return False, None
        
        try:
            current = version.parse(self.current_version)
            latest_parsed = version.parse(latest)
            
            return latest_parsed > current, latest
            
        except Exception as e:
            logger.debug(f"Error comparing versions: {e}")
            return False, None
    
    def get_update_message(self, latest_version: str) -> str:
        """
        Generate update notification message.
        
        Args:
            latest_version: Latest available version
            
        Returns:
            Formatted update message
        """
        return f"""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║  🎉 NEW VERSION AVAILABLE!                                ║
║                                                            ║
║  Current version: {self.current_version:<40} ║
║  Latest version:  {latest_version:<40} ║
║                                                            ║
║  📦 To update, run:                                       ║
║                                                            ║
║  Windows:                                                  ║
║    .\\scripts\\install.ps1 -Update                          ║
║                                                            ║
║  Linux/macOS:                                              ║
║    ./scripts/install.sh --update                           ║
║                                                            ║
║  📚 Release notes:                                        ║
║    {self.GITHUB_RELEASES_URL:<52} ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
"""
    
    def notify_if_update_available(self, silent: bool = False) -> bool:
        """
        Check for updates and print notification if available.
        
        Args:
            silent: If True, don't print anything
            
        Returns:
            True if update is available, False otherwise
        """
        update_available, latest = self.check_for_updates()
        
        if update_available and latest and not silent:
            print(self.get_update_message(latest))
        
        return update_available


def check_version(current_version: str, silent: bool = False) -> bool:
    """
    Convenience function to check for updates.
    
    Args:
        current_version: Current installed version
        silent: If True, don't print notification
        
    Returns:
        True if update is available, False otherwise
    """
    checker = VersionChecker(current_version)
    return checker.notify_if_update_available(silent=silent)
