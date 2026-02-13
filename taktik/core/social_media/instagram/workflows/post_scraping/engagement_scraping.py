"""Likers and comments scraping for the Post Scraping workflow."""

import re
import time
from typing import Dict, Any, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS
from .post_scraping_models import ScrapedProfile, CommentData

console = Console()


class PostEngagementScrapingMixin:
    """Mixin: scrape likers, comments, comment sort, expand replies."""

    def _scrape_likers(self):
        """Scrape likers from the post."""
        console.print(f"\n[cyan]❤️ Scraping likers (max {self.max_likers})...[/cyan]")
        
        try:
            # Find and click like count button
            like_count_clicked = False
            buttons = self.device.xpath('//android.widget.Button').all()
            
            for i, btn in enumerate(buttons):
                if i > 0:
                    prev_info = buttons[i-1].info
                    if 'Like' in prev_info.get('contentDescription', ''):
                        text = btn.get_text() if hasattr(btn, 'get_text') else ''
                        if text and text.isdigit():
                            btn.click()
                            like_count_clicked = True
                            time.sleep(2)
                            break
            
            if not like_count_clicked:
                console.print("[yellow]⚠️ Could not find like count button[/yellow]")
                return
            
            # Scrape likers list
            seen_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Scraping likers...", total=self.max_likers)
                
                while len(self.likers) < self.max_likers and scroll_attempts < max_scroll_attempts:
                    # Find username buttons
                    found_new = False
                    
                    # Look for profile buttons/usernames in the list
                    elements = self.device.xpath('//android.widget.Button').all()
                    for elem in elements:
                        text = elem.get_text() if hasattr(elem, 'get_text') else ''
                        desc = elem.info.get('contentDescription', '')
                        
                        # Skip non-username elements
                        if not text or text in ['Follow', 'Following', 'Remove']:
                            continue
                        
                        # Check if it looks like a username
                        if text and text not in seen_usernames and not text.isdigit():
                            # Validate it's a username (no spaces, reasonable length)
                            if ' ' not in text and len(text) <= 30:
                                seen_usernames.add(text)
                                self.likers.append(ScrapedProfile(
                                    username=text,
                                    source_type='liker',
                                    source_post_url=self.post_url
                                ))
                                found_new = True
                                progress.update(task, completed=len(self.likers))
                                
                                if len(self.likers) >= self.max_likers:
                                    break
                    
                    if not found_new:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
                    
                    # Scroll down
                    if len(self.likers) < self.max_likers:
                        self.scroll_actions.scroll_down()
                        time.sleep(0.5)
            
            # Go back to post
            self.device.press("back")
            time.sleep(1)
            
            console.print(f"[green]✅ Scraped {len(self.likers)} likers[/green]")
            
        except Exception as e:
            self.logger.error(f"Error scraping likers: {e}")
            console.print(f"[red]❌ Error scraping likers: {e}[/red]")

    def _scrape_comments(self):
        """Scrape comments from the post."""
        console.print(f"\n[cyan]💬 Scraping comments (max {self.max_comments})...[/cyan]")
        
        try:
            # Click comment button or count
            comment_btn = self.device.xpath(POST_SELECTORS.comment_button_selectors[1])
            if comment_btn.exists:
                comment_btn.click()
                time.sleep(2)
            else:
                # Try clicking comment count
                buttons = self.device.xpath('//android.widget.Button').all()
                for i, btn in enumerate(buttons):
                    if i > 0:
                        prev_info = buttons[i-1].info
                        if 'Comment' in prev_info.get('contentDescription', ''):
                            btn.click()
                            time.sleep(2)
                            break
            
            # Verify we're on comments page
            is_comments_open = any(
                self.device.xpath(s).exists for s in POST_SELECTORS.comments_view_indicators
            )
            if not is_comments_open:
                console.print("[yellow]⚠️ Could not open comments[/yellow]")
                return
            
            # Change sort if needed
            self._change_comment_sort()
            
            # Scrape comments
            seen_comments = set()
            scroll_attempts = 0
            max_scroll_attempts = 15
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Scraping comments...", total=self.max_comments)
                
                while len(self.comments) < self.max_comments and scroll_attempts < max_scroll_attempts:
                    found_new = False
                    
                    # Find comment containers
                    view_groups = self.device.xpath('//android.view.ViewGroup').all()
                    
                    for vg in view_groups:
                        try:
                            desc = vg.info.get('contentDescription', '')
                            
                            # Skip empty or non-comment elements
                            if not desc or len(desc) < 3:
                                continue
                            
                            # Check if this looks like a comment (username + content)
                            # Format: "username content" or "username   content"
                            if desc not in seen_comments:
                                # Try to find username button inside
                                username = None
                                
                                # Look for child buttons
                                children = vg.child('android.widget.Button')
                                if children.exists:
                                    for child in children.all() if hasattr(children, 'all') else [children]:
                                        text = child.get_text() if hasattr(child, 'get_text') else ''
                                        if text and ' ' not in text and len(text) <= 30:
                                            username = text
                                            break
                                
                                if username:
                                    # Extract comment content from desc
                                    content = desc.replace(username, '').strip()
                                    
                                    # Get likes from sibling button
                                    likes = 0
                                    like_btn = vg.sibling('android.widget.Button')
                                    if like_btn.exists:
                                        like_desc = like_btn.info.get('contentDescription', '')
                                        match = re.search(r'(\d+)\s*likes?', like_desc)
                                        if match:
                                            likes = int(match.group(1))
                                    
                                    seen_comments.add(desc)
                                    self.comments.append(CommentData(
                                        username=username,
                                        content=content,
                                        likes_count=likes
                                    ))
                                    found_new = True
                                    progress.update(task, completed=len(self.comments))
                                    
                                    if len(self.comments) >= self.max_comments:
                                        break
                        except:
                            continue
                    
                    # Check for "View X more reply" buttons
                    self._expand_replies()
                    
                    if not found_new:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
                    
                    # Scroll down
                    if len(self.comments) < self.max_comments:
                        self.scroll_actions.scroll_down()
                        time.sleep(0.5)
            
            # Go back to post
            self.device.press("back")
            time.sleep(1)
            
            console.print(f"[green]✅ Scraped {len(self.comments)} comments[/green]")
            
        except Exception as e:
            self.logger.error(f"Error scraping comments: {e}")
            console.print(f"[red]❌ Error scraping comments: {e}[/red]")

    def _change_comment_sort(self):
        """Change comment sorting if needed."""
        if self.comment_sort == 'for_you':
            return  # Default, no change needed
        
        try:
            # Click on sort button (e.g., "For you")
            sort_btn = self.device.xpath(POST_SELECTORS.comment_sort_button)
            if sort_btn.exists:
                sort_btn.click()
                time.sleep(1)
                
                # Select the desired sort option
                sort_map = {
                    'most_recent': 'Most recent',
                    'meta_verified': 'Meta Verified'
                }
                
                target = sort_map.get(self.comment_sort, 'Most recent')
                option = self.device.xpath(f'//*[@content-desc="{target}"]')
                if option.exists:
                    option.click()
                    time.sleep(1)
                    console.print(f"[dim]Sorted by: {target}[/dim]")
                else:
                    # Click outside to close menu
                    self.device.press("back")
                    
        except Exception as e:
            self.logger.warning(f"Could not change comment sort: {e}")

    def _expand_replies(self):
        """Click on 'View X more reply' buttons to expand replies."""
        try:
            # Find "View X more reply" elements
            reply_btns = self.device.xpath(POST_SELECTORS.expand_replies_selector)
            if reply_btns.exists:
                for btn in reply_btns.all()[:3]:  # Limit to avoid infinite loops
                    try:
                        btn.click()
                        time.sleep(0.5)
                    except:
                        pass
        except:
            pass
