"""
Cold DM Workflow - Send direct messages to a list of recipients
"""

import time
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from taktik.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
from taktik.core.social_media.instagram.actions.business.messaging import send_dm

console = Console()


class ColdDMWorkflow:
    """
    Cold DM Workflow - Send personalized DMs to a list of recipients.
    
    Supports two modes:
    - Manual: Use predefined message templates
    - AI: Generate personalized messages using AI (future implementation)
    """
    
    def __init__(self, device_manager: DeviceManager, config: Dict[str, Any]):
        """
        Initialize Cold DM workflow.
        
        Args:
            device_manager: Device manager instance
            config: Workflow configuration
        """
        self.device_manager = device_manager
        self.device = device_manager.device
        self.config = config
        self.logger = device_manager.logger
        
        # Initialize actions
        self.nav_actions = NavigationActions(device_manager)
        self.detection_actions = DetectionActions(device_manager)
        
        # Stats
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.skipped_profiles = 0
        
        # Recipients
        self.recipients = config.get('recipients', [])
        self.message_mode = config.get('message_mode', 'manual')
        self.messages = config.get('messages', [])
        self.ai_prompt = config.get('ai_prompt', '')
        
        # Settings
        self.delay_min = config.get('delay_min', 30)
        self.delay_max = config.get('delay_max', 60)
        self.max_dms = config.get('max_dms', 50)
        self.skip_private = config.get('skip_private', True)
        self.skip_verified = config.get('skip_verified', False)
        
        self.logger.info(f"Cold DM Workflow initialized: {len(self.recipients)} recipients, {self.message_mode} mode")
    
    def run(self) -> Dict[str, Any]:
        """
        Run the Cold DM workflow.
        
        Returns:
            Dictionary with workflow results
        """
        try:
            console.print("\n[bold cyan]🚀 Starting Cold DM Workflow[/bold cyan]")
            console.print(f"[dim]Recipients: {len(self.recipients)}, Mode: {self.message_mode}[/dim]\n")
            
            if not self.recipients:
                self.logger.error("No recipients provided")
                return {"success": False, "error": "No recipients provided"}
            
            if self.message_mode == 'manual' and not self.messages:
                self.logger.error("No messages provided for manual mode")
                return {"success": False, "error": "No messages provided"}
            
            if self.message_mode == 'ai' and not self.ai_prompt:
                self.logger.error("No AI prompt provided for AI mode")
                return {"success": False, "error": "No AI prompt provided"}
            
            # Navigate to Instagram DM screen
            console.print("[cyan]📱 Navigating to Instagram DM...[/cyan]")
            if not self._navigate_to_dm_screen():
                return {"success": False, "error": "Failed to navigate to DM screen"}
            
            time.sleep(2)
            
            # Process recipients
            self._process_recipients()
            
            # Display final stats
            self._display_final_stats()
            
            return {
                "success": True,
                "dms_sent": self.dms_sent,
                "dms_success": self.dms_success,
                "dms_failed": self.dms_failed,
                "skipped": self.skipped_profiles
            }
            
        except Exception as e:
            self.logger.error(f"Cold DM workflow error: {e}")
            console.print(f"[red]❌ Cold DM error: {e}[/red]")
            return {"success": False, "error": str(e)}
    
    def _navigate_to_dm_screen(self) -> bool:
        """Navigate to Instagram DM screen."""
        try:
            # Open Instagram app
            self.device.app_start("com.instagram.android")
            time.sleep(2)
            
            # Navigate to DM via deep link
            dm_intent = "android.intent.action.VIEW -d instagram://direct-inbox"
            self.device.shell(f"am start -a {dm_intent}")
            time.sleep(2)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate to DM screen: {e}")
            return False
    
    def _process_recipients(self):
        """Process all recipients and send DMs."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                f"[cyan]Sending DMs (0/{min(len(self.recipients), self.max_dms)})...", 
                total=min(len(self.recipients), self.max_dms)
            )
            
            for i, username in enumerate(self.recipients):
                if self.dms_sent >= self.max_dms:
                    self.logger.info(f"Reached max DMs limit: {self.max_dms}")
                    break
                
                progress.update(
                    task,
                    description=f"[cyan]Sending DM to @{username} ({i+1}/{min(len(self.recipients), self.max_dms)})..."
                )
                
                # Send DM to recipient
                success = self._send_dm_to_recipient(username)
                
                if success:
                    self.dms_sent += 1
                    self.dms_success += 1
                    progress.update(task, advance=1)
                else:
                    self.dms_failed += 1
                
                # Random delay between DMs
                if self.dms_sent < self.max_dms and i < len(self.recipients) - 1:
                    delay = random.randint(self.delay_min, self.delay_max)
                    self.logger.debug(f"Waiting {delay}s before next DM...")
                    time.sleep(delay)
    
    def _send_dm_to_recipient(self, username: str) -> bool:
        """
        Send a DM to a specific recipient.
        
        Args:
            username: Instagram username
            
        Returns:
            True if DM sent successfully, False otherwise
        """
        try:
            self.logger.info(f"📨 Sending DM to @{username}")
            
            # Navigate to user profile to check filters
            if not self.nav_actions.navigate_to_profile(username, deep_link_usage_percentage=50):
                self.logger.warning(f"Failed to navigate to @{username}")
                return False
            
            time.sleep(1.5)
            
            # Check if should skip this profile
            if self._should_skip_profile(username):
                self.skipped_profiles += 1
                self.logger.info(f"⏭️ Skipped @{username}")
                return False
            
            # Get message to send
            message = self._get_message_for_recipient(username)
            if not message:
                self.logger.warning(f"No message generated for @{username}")
                return False
            
            # Send DM
            success = send_dm(
                device_manager=self.device_manager,
                username=username,
                message=message,
                navigate_to_profile=False  # Already navigated
            )
            
            if success:
                self.logger.info(f"✅ DM sent to @{username}")
            else:
                self.logger.warning(f"❌ Failed to send DM to @{username}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending DM to @{username}: {e}")
            return False
    
    def _should_skip_profile(self, username: str) -> bool:
        """
        Check if profile should be skipped based on filters.
        
        Args:
            username: Instagram username
            
        Returns:
            True if should skip, False otherwise
        """
        try:
            # Check if private account
            if self.skip_private:
                is_private = self.detection_actions.is_private_account()
                if is_private:
                    self.logger.debug(f"Skipping @{username} - private account")
                    return True
            
            # Check if verified account
            if self.skip_verified:
                is_verified = self.detection_actions.is_verified_account()
                if is_verified:
                    self.logger.debug(f"Skipping @{username} - verified account")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking filters for @{username}: {e}")
            return False
    
    def _get_message_for_recipient(self, username: str) -> Optional[str]:
        """
        Get message to send to recipient.
        
        Args:
            username: Instagram username
            
        Returns:
            Message text or None
        """
        if self.message_mode == 'manual':
            # Pick a random message from templates
            if not self.messages:
                return None
            return random.choice(self.messages)
        
        elif self.message_mode == 'ai':
            # TODO: Implement AI message generation
            # For now, return a placeholder
            self.logger.warning("AI mode not yet implemented, using placeholder")
            return f"Hi @{username}! {self.ai_prompt}"
        
        return None
    
    def _display_final_stats(self):
        """Display final workflow statistics."""
        console.print("\n[bold green]✅ Cold DM Workflow Completed[/bold green]")
        console.print(f"[green]DMs sent: {self.dms_sent}[/green]")
        console.print(f"[green]Success: {self.dms_success}[/green]")
        console.print(f"[red]Failed: {self.dms_failed}[/red]")
        console.print(f"[yellow]Skipped: {self.skipped_profiles}[/yellow]")
