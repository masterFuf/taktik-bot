"""Comments scraping for the Discovery workflow."""

import re
import time
from typing import Dict, Any, Optional
from rich.console import Console

from taktik.core.database.local.service import get_local_database
from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS
from .models import ScrapedProfile

console = Console()


class DiscoveryCommentsScrapingMixin:
    """Mixin: scrape comments from posts with optional on-the-fly enrichment."""

    def _scrape_post_comments(self, post_url: str, source_type: str, source_value: str,
                             progress, max_count: int):
        """Scrape comments from current post with optional on-the-fly enrichment."""
        enrich_mode = "with enrichment" if self.enrich_profiles else "usernames only"
        console.print(f"[dim]    💬 Scraping comments ({enrich_mode})...[/dim]")
        self.logger.info(f"Starting comments scraping - max: {max_count}, enrich: {self.enrich_profiles}")
        
        # Open comments
        if not self._open_comments():
            console.print(f"[yellow]    ⚠️ Could not open comments[/yellow]")
            return
        
        time.sleep(1.5)
        
        # Change sort if needed
        self._change_comment_sort()
        
        seen_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 20
        start_count = progress.comments_scraped
        enriched_count = 0
        
        while progress.comments_scraped < max_count and scroll_attempts < max_scroll_attempts:
            # Find comment author usernames from the comments list
            # Structure: sticky_header_list > ViewGroup > ViewGroup > ViewGroup (with username as text) > Button (username)
            # The username Button is the first child of a ViewGroup that has the username as text attribute
            username_selectors = POST_SELECTORS.comment_username_selectors
            
            found_new = False
            total_elements_found = 0
            for selector in username_selectors:
                elements = self.device.xpath(selector).all()
                total_elements_found += len(elements)
                for elem in elements:
                    try:
                        # Get username from text attribute (primary) or content-desc (fallback)
                        username = elem.text or elem.attrib.get('text', '') or ''
                        
                        # Skip non-username buttons (Reply, See translation, For you, etc.)
                        skip_texts = ['Reply', 'See translation', 'For you', 'View', 'likes', 'like']
                        if any(skip in username for skip in skip_texts):
                            continue
                        
                        # Clean username
                        username = username.strip().lstrip('@')
                        
                        # Validate username format (alphanumeric, dots, underscores, max 30 chars)
                        if not username or username in seen_usernames:
                            continue
                        if len(username) > 30 or ' ' in username:
                            continue
                        # Skip if it looks like a resource ID (numeric)
                        if username.isdigit():
                            continue
                        
                        # Try to extract comment text and detect if it's a reply
                        comment_text = ''
                        is_reply = False
                        try:
                            # The comment text is in the parent ViewGroup's content-desc
                            # Format: "username comment text"
                            parent = elem.get_parent()
                            if parent:
                                parent_desc = parent.attrib.get('content-desc', '')
                                if parent_desc and username in parent_desc:
                                    # Remove username from the beginning to get comment text
                                    comment_text = parent_desc.replace(username, '', 1).strip()
                                
                                # Detect if this is a reply based on indentation (bounds)
                                # Replies start around x=100-105, main comments start at x=23
                                bounds = elem.attrib.get('bounds', '')
                                if bounds:
                                    # Parse bounds format: [x1,y1][x2,y2]
                                    bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                                    if bounds_match:
                                        x1 = int(bounds_match.group(1))
                                        # If x1 > 80, it's likely a reply (indented comment)
                                        is_reply = x1 > 80
                        except:
                            pass
                        
                        seen_usernames.add(username)
                        
                        # Check if already scraped recently (to skip enrichment, not the profile itself)
                        already_scraped = self._is_profile_recently_scraped(username)
                        
                        # Create profile object (always record the interaction)
                        profile = ScrapedProfile(
                            username=username,
                            source_type=source_type,
                            source_value=source_value,
                            interaction_type='commenter',
                            post_url=post_url
                        )
                        
                        # Save comment to database (with text if extracted)
                        try:
                            db = get_local_database()
                            db.save_scraped_comment(
                                username=username,
                                content=comment_text,
                                target_username=source_value,
                                post_url=post_url,
                                scraping_session_id=self._scraping_session_id if hasattr(self, '_scraping_session_id') else None,
                                is_reply=is_reply
                            )
                        except Exception as e:
                            self.logger.debug(f"Could not save comment: {e}")
                        
                        # If already scraped, skip enrichment but still record the interaction
                        if already_scraped:
                            self._skipped_already_scraped += 1
                            self.logger.info(f"⏭️ SKIP @{username} | reason=already_scraped | days={self.skip_recently_scraped_days}")
                            # Still add to scraped profiles to track the interaction
                            self.scraped_profiles.append(profile)
                            progress.comments_scraped += 1
                            found_new = True
                            if progress.comments_scraped >= max_count:
                                break
                            continue
                        
                        # Log for Live Panel with comment content
                        reply_tag = " [REPLY]" if is_reply else ""
                        comment_preview = f" | comment={comment_text[:100]}" if comment_text else ""
                        self.logger.info(f"💬 COMMENT @{username}{reply_tag}{comment_preview}")
                        
                        # Enrich on-the-fly if enabled (only for new profiles)
                        if self.enrich_profiles and enriched_count < self.max_profiles_to_enrich:
                            try:
                                console.print(f"[dim]      → Enriching @{username}...[/dim]")
                                # Click on username to navigate to profile
                                elem.click()
                                time.sleep(1.5)
                                
                                # Get enriched profile data
                                info = self.profile_manager.get_complete_profile_info(
                                    username=username,
                                    navigate_if_needed=False,
                                    enrich=True
                                )
                                
                                if info:
                                    profile.bio = info.get('biography', '')
                                    profile.website = info.get('website', '')
                                    profile.followers_count = info.get('followers_count', 0)
                                    profile.following_count = info.get('following_count', 0)
                                    profile.posts_count = info.get('posts_count', 0)
                                    profile.is_private = info.get('is_private', False)
                                    profile.is_verified = info.get('is_verified', False)
                                    profile.is_business = info.get('is_business', False)
                                    profile.category = info.get('business_category', '')
                                    
                                    # Extract linked accounts
                                    linked = info.get('linked_accounts', [])
                                    for account in linked:
                                        if 'thread' in account.get('name', '').lower():
                                            profile.threads_username = account.get('name', '')
                                    
                                    enriched_count += 1
                                    # Log in parsable format for Live Panel
                                    bio_escaped = (profile.bio or '').replace('\n', '\\n')[:500]
                                    self.logger.info(f"✅ PROFILE @{username} | followers={profile.followers_count} | posts={profile.posts_count} | following={profile.following_count} | category={profile.category or ''} | website={profile.website or ''} | bio={bio_escaped} | private={profile.is_private} | verified={profile.is_verified} | business={profile.is_business}")
                                    console.print(f"[dim]      ✅ {profile.followers_count} followers, {profile.posts_count} posts[/dim]")
                                
                                # Go back to comments
                                self.device.press("back")
                                time.sleep(1)
                                
                            except Exception as e:
                                self.logger.warning(f"Failed to enrich @{username}: {e}")
                                try:
                                    self.device.press("back")
                                    time.sleep(0.5)
                                except:
                                    pass
                        
                        self.scraped_profiles.append(profile)
                        progress.comments_scraped += 1
                        found_new = True
                        
                        if progress.comments_scraped >= max_count:
                            break
                    except:
                        continue
                if progress.comments_scraped >= max_count:
                    break
            
            if not found_new:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            
            # Log progress with element count for debugging
            self.logger.debug(f"Comments progress: {progress.comments_scraped}/{max_count} (seen: {len(seen_usernames)}, enriched: {enriched_count}, elements: {total_elements_found})")
            
            # Scroll to load more comments (use comments-specific scroll)
            if progress.comments_scraped < max_count:
                self.scroll_actions.scroll_comments_down()
                time.sleep(1)
        
        # Go back
        self.device.press("back")
        time.sleep(1)
        
        scraped = progress.comments_scraped - start_count
        self.logger.info(f"Comments scraping complete: {scraped} scraped, {enriched_count} enriched")
        console.print(f"[dim]    ✅ {scraped} comments scraped ({enriched_count} enriched)[/dim]")

    def _open_comments(self) -> bool:
        """Open comments section."""
        try:
            # Try all comment button selectors (centralized)
            comment_selectors = POST_SELECTORS.comment_button_selectors
            
            for selector in comment_selectors:
                try:
                    elem = self.device.xpath(selector)
                    if elem.exists:
                        elem.click()
                        time.sleep(1.5)
                        if self._is_comments_view_open():
                            self.logger.debug(f"Comments opened via {selector}")
                            return True
                except:
                    continue
            
            self.logger.warning("Could not open comments")
            return False
        except Exception as e:
            self.logger.error(f"Error opening comments: {e}")
            return False

    def _is_comments_view_open(self) -> bool:
        """Check if comments view is open."""
        try:
            indicators = POST_SELECTORS.comments_view_indicators
            for selector in indicators:
                if self.device.xpath(selector).exists:
                    return True
        except:
            pass
        return False

    def _change_comment_sort(self):
        """Change comment sorting."""
        if self.comment_sort == 'for_you':
            return
        
        try:
            sort_btn = self.device.xpath(POST_SELECTORS.comment_sort_button)
            if sort_btn.exists:
                sort_btn.click()
                time.sleep(1)
                
                sort_map = {
                    'most_recent': 'Most recent',
                    'meta_verified': 'Meta Verified'
                }
                target = sort_map.get(self.comment_sort, 'Most recent')
                option = self.device.xpath(f'//*[@content-desc="{target}"]')  # Dynamic, can't centralize
                if option.exists:
                    option.click()
                    time.sleep(1)
                else:
                    self.device.press("back")
        except:
            pass

    def _expand_all_replies(self):
        """Click on all 'View X more reply' buttons."""
        try:
            reply_btns = self.device.xpath(POST_SELECTORS.expand_replies_selector)
            if reply_btns.exists:
                for btn in reply_btns.all()[:5]:
                    try:
                        btn.click()
                        time.sleep(0.3)
                    except:
                        pass
        except:
            pass
