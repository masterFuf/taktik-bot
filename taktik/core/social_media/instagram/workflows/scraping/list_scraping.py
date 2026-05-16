"""List scraping, hashtag scraping, and post URL scraping for the Scraping workflow."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from ..common.post_navigation import open_likers_list

console = Console()


class ScrapingListMixin:
    """Mixin: generic list scraping, hashtag scraping, post URL scraping."""

    def _scrape_list(self, max_count: int, source_type: str, source_name: str, total_available: int = None, enrich_on_the_fly: bool = False) -> List[Dict[str, Any]]:
        """
        Scrape usernames from a visible list (followers, following, likers).
        
        Args:
            max_count: Maximum profiles to scrape
            source_type: Type of source (FOLLOWER, FOLLOWING, LIKER, etc.)
            source_name: Name of the source (target username, hashtag, etc.)
            total_available: Total profiles available (for accurate progress display)
            enrich_on_the_fly: If True, click on each profile to get detailed info (followers, following, posts, bio)
            
        Returns:
            List of scraped profile data
        """
        scraped = []
        scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
        seen_usernames = set()
        no_new_users_count = 0
        max_no_new_users = 5  # Stop after 5 consecutive scrolls with no new users
        
        # Use actual available count for progress bar if provided
        progress_total = min(max_count, total_available) if total_available else max_count
        
        # Description for progress bar
        action_desc = "Scraping enrichi" if enrich_on_the_fly else "Scraping"
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            # Show realistic progress info
            task = progress.add_task(
                f"[cyan]Scraping {source_type.lower()} (0/{progress_total:,})...", 
                total=progress_total
            )
            
            suggestions_check_count = 0  # Count consecutive suggestions detections
            min_profiles_before_suggestions_check = 50  # Don't check suggestions until we have some profiles
            
            while len(scraped) < max_count and self._should_continue():
                # Only check suggestions section after collecting some profiles
                # This prevents false positives when suggestions are visible but we haven't scrolled yet
                if len(scraped) >= min_profiles_before_suggestions_check:
                    if self.detection_actions.is_in_suggestions_section():
                        suggestions_check_count += 1
                        # Require 2 consecutive detections to confirm we're really in suggestions
                        if suggestions_check_count >= 2:
                            self.logger.info("📋 Reached suggestions section - end of real followers list")
                            progress.update(
                                task,
                                description=f"[green]Completed {source_type.lower()} ({len(scraped):,}/{len(scraped):,}) - end of list[/green]"
                            )
                            break
                    else:
                        suggestions_check_count = 0  # Reset if not in suggestions
                
                # Get visible usernames
                visible = self.detection_actions.get_visible_followers_with_elements()
                
                if not visible:
                    # Try scrolling - wait for Instagram to load
                    self.scroll_actions.scroll_followers_list_down()
                    time.sleep(1.5)
                    
                    if scroll_detector.is_the_end():
                        self.logger.info("Reached end of list")
                        break
                    continue
                
                new_count = 0
                for follower in visible:
                    username = follower.get('username')
                    element = follower.get('element')
                    if not username or username in seen_usernames:
                        continue
                    
                    seen_usernames.add(username)
                    
                    profile_data = {
                        'username': username,
                        'source_type': source_type,
                        'source_name': source_name,
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    # If enriching on the fly, click on profile to get details
                    if enrich_on_the_fly and element:
                        try:
                            # Click on the profile element to navigate
                            element.click()
                            time.sleep(1.5)
                            
                            # Use get_complete_profile_info with enrich=True for full data
                            enriched_data = self.profile_manager.get_complete_profile_info(
                                username=username,
                                navigate_if_needed=False,
                                enrich=True
                            )
                            
                            if enriched_data:
                                profile_data['followers_count'] = enriched_data.get('followers_count', 0)
                                profile_data['following_count'] = enriched_data.get('following_count', 0)
                                profile_data['posts_count'] = enriched_data.get('posts_count', 0)
                                profile_data['is_private'] = enriched_data.get('is_private', False)
                                profile_data['biography'] = enriched_data.get('biography', '')
                                profile_data['full_name'] = enriched_data.get('full_name', '')
                                profile_data['is_verified'] = enriched_data.get('is_verified', False)
                                profile_data['is_business'] = enriched_data.get('is_business', False)
                                profile_data['business_category'] = enriched_data.get('business_category', '')
                                profile_data['website'] = enriched_data.get('website', '')
                                profile_data['linked_accounts'] = enriched_data.get('linked_accounts', [])
                                profile_data['date_joined'] = enriched_data.get('date_joined', '')
                                profile_data['account_based_in'] = enriched_data.get('account_based_in', '')
                                
                                self.logger.debug(f"✅ Enriched @{username}: {profile_data['followers_count']} followers, category={profile_data.get('business_category')}")
                            else:
                                self.logger.warning(f"Could not get profile info for @{username}")

                            # Capture screenshot for AI vision analysis (while still on profile page)
                            if getattr(self, '_ai_service', None):
                                try:
                                    import tempfile as _tempfile, os as _os2
                                    _tmp_dir = _os2.path.join(_tempfile.gettempdir(), 'taktik_ai')
                                    _os2.makedirs(_tmp_dir, exist_ok=True)
                                    _screenshot_path = _os2.path.join(_tmp_dir, f'profile_{username}.png')
                                    self.device.screenshot().save(_screenshot_path, format='PNG')
                                    profile_data['_screenshot_path'] = _screenshot_path
                                except Exception as _e:
                                    self.logger.debug(f"AI screenshot capture failed for @{username}: {_e}")

                            # Go back to the list
                            self.device.press("back")
                            time.sleep(1)
                            
                            # Safety: if not back on the followers list, press back again
                            # (can happen if Instagram opened a nested screen, e.g. story → profile)
                            if not self.detection_actions.is_followers_list_open():
                                self.logger.debug("⚠️ Not on followers list after back press - pressing back once more")
                                self.device.press("back")
                                time.sleep(1)
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to enrich @{username}: {e}")
                            # Try to go back anyway
                            try:
                                self.device.press("back")
                                time.sleep(0.5)
                            except Exception:
                                pass
                    
                    scraped.append(profile_data)
                    self.scraped_profiles.append(profile_data)
                    profile_id = self._save_profile_immediately(profile_data)

                    # AI qualification (if enabled and profile was enriched with bio data)
                    if enrich_on_the_fly and profile_id and getattr(self, '_ai_service', None):
                        self._qualify_profile_ai(profile_data, profile_id)

                    new_count += 1
                    
                    # Update progress with current count
                    progress.update(
                        task, 
                        advance=1,
                        description=f"[cyan]{action_desc} {source_type.lower()} ({len(scraped):,}/{progress_total:,})..."
                    )
                    
                    if len(scraped) >= max_count:
                        break
                    
                    # When enriching on-the-fly, navigating away and back makes
                    # all remaining elements in `visible` stale (their cached bounds
                    # now point to the wrong UI nodes after the followers list reloads).
                    # Break so the outer while loop re-fetches fresh elements.
                    if enrich_on_the_fly:
                        break
                
                # Check if there are still unprocessed profiles in the current visible set.
                # In enrich_on_the_fly mode we process one profile per outer loop iteration
                # (break after each to avoid stale element refs). We must NOT scroll until
                # every currently visible profile has been processed.
                has_unprocessed_visible = any(
                    f.get('username') and f.get('username') not in seen_usernames
                    for f in visible
                )
                
                # Notify scroll detector
                scroll_detector.notify_new_page(list(seen_usernames))
                
                if new_count == 0:
                    # Check if there's a "See more" / "Load more" button before giving up
                    if self.scroll_actions.check_and_click_load_more():
                        self.logger.info("✅ Clicked 'See more' - waiting for new followers to load")
                        time.sleep(2.0)
                        continue  # Re-process without counting as a failed scroll

                    no_new_users_count += 1
                    self.logger.debug(f"No new users found ({no_new_users_count}/{max_no_new_users})")
                    
                    # Check suggestions only after collecting enough profiles
                    if len(scraped) >= min_profiles_before_suggestions_check:
                        if self.detection_actions.is_in_suggestions_section():
                            suggestions_check_count += 1
                            if suggestions_check_count >= 2:
                                self.logger.info("📋 Reached suggestions section - stopping")
                                break
                        else:
                            suggestions_check_count = 0
                    
                    if no_new_users_count >= max_no_new_users:
                        self.logger.info(f"🏁 No new users after {max_no_new_users} scrolls - assuming end of list")
                        break
                    
                    # Get current visible usernames before scroll
                    current_usernames = set(f.get('username') for f in visible if f.get('username'))
                    
                    # Scroll to find more
                    self.scroll_actions.scroll_followers_list_down()
                    
                    # Wait for content to actually change (not just a fixed delay)
                    max_wait_attempts = 5
                    for wait_attempt in range(max_wait_attempts):
                        time.sleep(1.0)  # Wait 1s between checks
                        new_visible = self.detection_actions.get_visible_followers_with_elements()
                        new_usernames = set(f.get('username') for f in new_visible if f.get('username'))
                        
                        # Check if we have new usernames (content loaded)
                        if new_usernames != current_usernames and len(new_usernames - seen_usernames) > 0:
                            self.logger.debug(f"✅ New content loaded after {wait_attempt + 1}s")
                            break
                        
                        if wait_attempt == max_wait_attempts - 1:
                            self.logger.debug(f"⏳ Content unchanged after {max_wait_attempts}s")
                    
                    if scroll_detector.is_the_end():
                        self.logger.info("Reached end of list")
                        break
                    
                    # Check for "And X others" indicator (limited list end)
                    if self.detection_actions.is_followers_list_end_reached():
                        self.logger.info("📋 Reached 'And X others' - end of accessible followers")
                        break
                    
                    # Check for suggestions section
                    if self.detection_actions.is_suggestions_section_visible():
                        self.logger.info("📋 Reached suggestions section - end of real followers")
                        break
                else:
                    # Reset counter when we find new users
                    no_new_users_count = 0
                    # Only scroll when all currently visible profiles have been processed.
                    # In enrich_on_the_fly mode we break after each profile and re-fetch,
                    # so visible may still contain unprocessed profiles — don't scroll yet.
                    if not has_unprocessed_visible:
                        # Scroll down to reveal more followers
                        self.scroll_actions.scroll_followers_list_down()
                        
                        # Wait for Instagram to finish loading (detect spinner)
                        max_loading_wait = 10  # Max 10 seconds waiting for loading
                        for _ in range(max_loading_wait):
                            time.sleep(1.0)
                            if not self.detection_actions.is_loading_spinner_visible():
                                self.logger.debug("✅ Loading complete, continuing...")
                                break
                        else:
                            self.logger.debug("⏳ Loading timeout, continuing anyway...")
        
        # Log final count vs expected
        if total_available and len(scraped) < total_available:
            self.logger.info(f"📊 Scraped {len(scraped)}/{total_available} ({len(scraped)*100//total_available}%) - some may be hidden/private")
        
        return scraped

    def _qualify_profile_ai(self, profile: dict, profile_id: int) -> None:
        """Classify profile using AI (vision model if screenshot available, text-based otherwise)."""
        import time as _time, json as _json, os as _os

        username = profile.get('username', '')
        screenshot_path = profile.get('_screenshot_path')

        # ── Vision-based classification (screenshot captured on profile page) ──────
        if screenshot_path and _os.path.exists(screenshot_path):
            result = {'success': False}
            try:
                result = self._ai_service.classify_profile_niche(
                    username=username,
                    screenshot_path=screenshot_path,
                    profile_context=profile,
                )
            except Exception as e:
                self.logger.warning(f"Vision classification failed for @{username}: {e}")
                if self._ipc:
                    self._ipc.ai_error(str(e), username)
            finally:
                try:
                    _os.remove(screenshot_path)
                except Exception:
                    pass

            if result.get('success'):
                c = result.get('classification', {})
                niche = c.get('niche', '')
                niche_category = c.get('niche_category', 'other')
                summary = c.get('summary', '')
                analysis = f"[{niche_category}] {niche}" + (f" · {summary}" if summary else "")
                self.logger.info(f"🤖 @{username}: {analysis}")
                # No score in scraping mode — store niche classification in ai_analysis
                self._update_scraped_profile_ai(profile_id, None, True, analysis)
                # Save cities extracted from bio
                cities_raw = c.get('cities', [])
                if isinstance(cities_raw, str):
                    cities_raw = [cities_raw] if cities_raw.strip() else []
                cities = [s.strip() for s in cities_raw if s.strip()]
                if cities:
                    city_str = ', '.join(cities)
                    try:
                        from taktik.core.database.local.service import get_local_database
                        get_local_database().update_profile_city(profile_id, city_str)
                        self.logger.info(f"📍 @{username}: cities={city_str}")
                    except Exception as e:
                        self.logger.debug(f"Could not save cities for @{username}: {e}")
            return

        # ── Text-based fallback (no screenshot available) ────────────────────────
        qualification_prompt = self.config.get('ai_qualification_prompt', '')
        if not qualification_prompt:
            return

        if self._ipc:
            self._ipc.ai_profile_analyzing(
                username,
                prompt=f"Qualifying @{username} for niche",
                model=getattr(self._ai_service, 'text_model', 'anthropic/claude-3.5-haiku'),
            )

        system_prompt = (
            "You are an Instagram profile qualification assistant.\n"
            "Score this profile from 0 to 10 based on how well it matches the criteria.\n"
            'Reply ONLY with valid JSON: {"score": 7, "qualified": true, "reason": "brief reason"}\n'
            "A profile is qualified if score >= 6."
        )
        user_prompt = (
            f"Qualification criteria:\n{qualification_prompt}\n\n"
            f"Profile:\n"
            f"- Username: @{username}\n"
            f"- Full name: {profile.get('full_name', '')}\n"
            f"- Bio: {profile.get('biography', 'N/A')}\n"
            f"- Category: {profile.get('business_category', 'N/A')}\n"
            f"- Followers: {profile.get('followers_count', 0)}\n"
            f"- Following: {profile.get('following_count', 0)}\n"
            f"- Posts: {profile.get('posts_count', 0)}\n"
            f"- Business account: {profile.get('is_business', False)}\n"
            f"- Verified: {profile.get('is_verified', False)}\n"
            f"- Account based in: {profile.get('account_based_in', 'N/A')}"
        )

        t0 = _time.time()
        result = self._ai_service.text_completion(system_prompt, user_prompt, temperature=0.2, max_tokens=150)
        duration_ms = int((_time.time() - t0) * 1000)

        if not result.get('success'):
            if self._ipc:
                self._ipc.ai_error(result.get('error', 'Qualification failed'), username)
            return

        try:
            text = result['text'].strip()
            if '```' in text:
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
            data = _json.loads(text.strip())
        except Exception as e:
            self.logger.warning(f"AI qualification JSON parse error for @{username}: {e}")
            if self._ipc:
                self._ipc.ai_error(f"Parse error: {e}", username)
            return

        score = int(data.get('score', 0))
        qualified = bool(data.get('qualified', score >= 6))
        reason = data.get('reason', '')

        result_text = f"Score {score}/10 — {'✅ Qualified' if qualified else '❌ Not qualified'}"
        if reason:
            result_text += f" · {reason}"

        if self._ipc:
            self._ipc.ai_profile_analyzed(
                username=username,
                result=result_text,
                duration_ms=duration_ms,
                model=result.get('model'),
                provider='openrouter',
                cost_usd=result.get('cost_usd'),
                classification={'score': score, 'qualified': qualified, 'reason': reason},
            )

        self.logger.info(f"🤖 AI @{username}: {result_text}")
        self._update_scraped_profile_ai(profile_id, score, qualified, reason)

    def _scrape_hashtag(self) -> Dict[str, Any]:
        """Scrape profiles from one or more hashtags."""
        # Support both hashtags list (new) and single hashtag (backward compat)
        hashtags = self.config.get('hashtags', [])
        if not hashtags:
            single = self.config.get('hashtag', '')
            if single:
                hashtags = [single]
        if not hashtags:
            return {"success": False, "error": "No hashtag provided"}

        scrape_type = self.config.get('scrape_type', 'authors')
        max_profiles = self.config.get('max_profiles', 200)
        max_posts = self.config.get('max_posts', 50)

        total_scraped = 0
        posts_checked_total = 0

        for hashtag in hashtags:
            if not self._should_continue():
                break
            if total_scraped >= max_profiles:
                break

            console.print(f"\n[cyan]📍 Navigating to #{hashtag}...[/cyan]")

            # Navigate to hashtag
            if not self.nav_actions.navigate_to_hashtag(hashtag):
                self.logger.error(f"Failed to navigate to #{hashtag}")
                continue

            time.sleep(2)

            posts_checked = 0
            remaining = max_profiles - total_scraped

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"[cyan]Scraping #{hashtag}...", total=remaining)

                while total_scraped < max_profiles and posts_checked < max_posts and self._should_continue():
                    # Click on a post
                    if not self._click_next_post():
                        self.logger.info("No more posts to check")
                        break

                    posts_checked += 1
                    time.sleep(1.5)

                    if scrape_type == 'authors':
                        # Get post author
                        author = self._get_post_author()
                        if author and author not in [p['username'] for p in self.scraped_profiles]:
                            profile_data = {
                                'username': author,
                                'source_type': 'HASHTAG_AUTHOR',
                                'source_name': hashtag,
                                'scraped_at': datetime.now().isoformat()
                            }
                            self.scraped_profiles.append(profile_data)
                            self._save_profile_immediately(profile_data)
                            total_scraped += 1
                            progress.update(task, advance=1)
                    else:
                        # Scrape likers
                        if self._open_likers_list():
                            time.sleep(1)
                            enrich_profiles = self.config.get('enrich_profiles', False)
                            likers = self._scrape_list(
                                max_count=min(20, max_profiles - total_scraped),
                                source_type='HASHTAG_LIKER',
                                source_name=hashtag,
                                enrich_on_the_fly=enrich_profiles
                            )
                            total_scraped += len(likers)
                            progress.update(task, advance=len(likers))
                            self.device.press("back")
                            time.sleep(0.5)

                    # Go back to hashtag grid
                    self.device.press("back")
                    time.sleep(1)

            posts_checked_total += posts_checked

        return {
            "success": True,
            "total_scraped": total_scraped,
            "posts_checked": posts_checked_total
        }

    def _scrape_post_url(self) -> Dict[str, Any]:
        """Scrape likers from one or more post URLs."""
        # Support both post_urls list (new) and single post_url (backward compat)
        post_urls = self.config.get('post_urls', [])
        if not post_urls:
            single = self.config.get('post_url', '')
            if single:
                post_urls = [single]
        if not post_urls:
            return {"success": False, "error": "No post URL provided"}

        max_profiles = self.config.get('max_profiles', 200)
        total_scraped = 0

        for post_url in post_urls:
            if not self._should_continue():
                break
            if total_scraped >= max_profiles:
                break

            # Extract post ID from URL
            import re
            match = re.search(r'/p/([^/]+)/', post_url)
            post_id = match.group(1) if match else 'unknown'

            console.print(f"\n[cyan]📍 Navigating to post...[/cyan]")

            # Navigate to post via deep link
            if not self.nav_actions.navigate_to_post_url(post_url):
                self.logger.error(f"Failed to navigate to post: {post_url}")
                continue

            time.sleep(2)

            # Extract post metadata (likes count)
            console.print(f"[dim]📊 Getting post info...[/dim]")
            likes_count = self.ui_extractors.extract_likes_count_from_ui()

            remaining = max_profiles - total_scraped
            target_count = remaining
            if likes_count:
                console.print(f"[green]✅ Post has {likes_count:,} likes[/green]")
                if likes_count < remaining:
                    console.print(f"[dim]   Adjusting target: {likes_count:,} (instead of {remaining:,})[/dim]")
                    target_count = likes_count

            # Detect if it's a Reel or regular post
            is_reel = self._is_reel_post()

            if is_reel:
                console.print("[cyan]📍 Reel detected - opening likers list...[/cyan]")
                likers = self._extract_likers_from_reel(target_count)
            else:
                console.print("[cyan]📍 Regular post - opening likers list...[/cyan]")
                likers = self._extract_likers_from_regular_post(target_count)

            if not likers:
                self.logger.error("Failed to extract likers")
                continue

            console.print(f"[cyan]📍 Processing {len(likers)} likers...[/cyan]")
            for username in likers[:target_count]:
                profile_data = {
                    'username': username,
                    'source_type': 'POST_LIKER',
                    'source_name': post_id,
                    'scraped_at': datetime.now().isoformat()
                }
                self.scraped_profiles.append(profile_data)
                self._save_profile_immediately(profile_data)
                total_scraped += 1

        return {
            "success": True,
            "total_scraped": total_scraped
        }

    def _open_likers_list(self) -> bool:
        """Open the likers list by clicking on like count (for hashtag scraping)."""
        return open_likers_list(self.device, self.ui_extractors, self.logger)
