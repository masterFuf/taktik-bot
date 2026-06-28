"""List scraping, hashtag scraping, and post URL scraping for the Scraping workflow."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
from taktik.core.shared.behavior.tap import tap_element_human
from ..common.post_navigation import open_likers_list
from ..common.detection import is_likers_popup_open
from .list_strategy import (
    ListScrapingStrategy,
    make_followers_strategy,
    make_commenters_strategy,
)
from .deep_qualify import DeepQualifyMixin

console = Console()


class ScrapingListMixin(DeepQualifyMixin):
    """Mixin: generic list scraping, hashtag scraping, post URL scraping."""

    def _get_profile_filter_reason(self, profile: Dict[str, Any]) -> Optional[str]:
        min_followers = self.config.get('minFollowers')
        max_followers = self.config.get('maxFollowers')
        min_following = self.config.get('minFollowing')
        max_following = self.config.get('maxFollowing')
        min_posts = self.config.get('minPosts')
        require_profile_picture = bool(self.config.get('requireProfilePicture', False))
        skip_private_profiles = bool(self.config.get('skipPrivateProfiles', True))

        followers_count = int(profile.get('followers_count') or 0)
        following_count = int(profile.get('following_count') or 0)
        posts_count = int(profile.get('posts_count') or 0)
        is_private = bool(profile.get('is_private', False))
        has_profile_picture = bool(profile.get('profile_pic_base64'))

        if skip_private_profiles and is_private:
            return 'private profile'
        if min_followers is not None and followers_count < int(min_followers):
            return f'followers < {int(min_followers)}'
        if max_followers is not None and followers_count > int(max_followers):
            return f'followers > {int(max_followers)}'
        if min_following is not None and following_count < int(min_following):
            return f'following < {int(min_following)}'
        if max_following is not None and following_count > int(max_following):
            return f'following > {int(max_following)}'
        if min_posts is not None and posts_count < int(min_posts):
            return f'posts < {int(min_posts)}'
        if require_profile_picture and not has_profile_picture:
            return 'missing profile picture'
        return None

    def _scrape_list(self, max_count: int, source_type: str, source_name: str,
                      total_available: int = None, enrich_on_the_fly: bool = False,
                      source_post_url: str = None,
                      strategy: ListScrapingStrategy = None) -> List[Dict[str, Any]]:
        """
        Scrape usernames from a visible list (followers, following, likers, commenters).

        The traversal logic — dedup, click-to-enrich, AI qualification, back-to-list
        retry, scroll-and-detect-end — is shared. UI specifics (how to enumerate
        visible rows, how to scroll, which popup we're on) are injected via
        `strategy` (see ``list_strategy.py``).

        Args:
            max_count: Maximum profiles to scrape
            source_type: Type of source (FOLLOWER, FOLLOWING, LIKER, POST_COMMENTER, etc.)
            source_name: Name of the source (target username, hashtag, etc.)
            total_available: Total profiles available (for accurate progress display)
            enrich_on_the_fly: If True, click on each profile to get detailed info
            source_post_url: Optional Instagram post URL from which these profiles are scraped
                             (used for likers/commenters from hashtag posts — enables dedup on next run).
            strategy: ListScrapingStrategy implementing the UI-specific extraction.
                      Defaults to ``make_followers_strategy(self)`` for backward compat
                      (followers / following / post likers).

        Returns:
            List of scraped profile data
        """
        if strategy is None:
            strategy = make_followers_strategy(self)
        scraped = []
        scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
        seen_usernames = set()
        no_new_users_count = 0

        # Dedup: skip profiles already known in DB — checked directly per username.
        # - rescrape_after_days = None (default)  → skip ALL known profiles (pure existence check)
        # - rescrape_after_days = N > 0           → skip only profiles created within N days
        # - rescrape_after_days = 0               → disabled (always re-scrape)
        rescrape_after_days: int | None = self.config.get('rescrape_after_days')
        _dedup_db = None
        if rescrape_after_days == 0:
            self.logger.info("🔄 Dedup disabled — always re-scrape mode")
        else:
            try:
                _dedup_db = self._local_db()
                if rescrape_after_days:
                    self.logger.info(
                        f"🔍 Dedup active (window {rescrape_after_days}d): "
                        f"profiles created < {rescrape_after_days}d ago will be skipped [db: {_dedup_db.db_path}]"
                    )
                else:
                    self.logger.info(
                        f"🔍 Dedup active (all known): existing profiles will be skipped [db: {_dedup_db.db_path}]"
                    )
            except Exception as _e:
                self.logger.warning(f"Could not initialize dedup DB: {_e}")
        max_no_new_users = 5  # Stop after 5 consecutive scrolls with no new users
        consecutive_empty_visible = 0  # Count consecutive scans returning 0 elements
        max_consecutive_empty = 3  # After this many, check if still on followers list

        # Deep qualify: open following list per profile + DB cross-reference
        deep_qualify: bool = bool(self.config.get('deep_qualify', False)) and enrich_on_the_fly
        deep_qualify_max_following: int = int(self.config.get('deep_qualify_max_following', 30))
        if deep_qualify:
            self.logger.info(
                f"🔬 Deep qualify ON — will collect up to {deep_qualify_max_following} "
                "followings per profile and cross-reference DB"
            )
        
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
                if strategy.enable_suggestions_check and len(scraped) >= min_profiles_before_suggestions_check:
                    if strategy.is_in_suggestions():
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
                visible = strategy.get_visible()
                
                if not visible:
                    consecutive_empty_visible += 1

                    # After a few consecutive empty scans, verify we're still on the
                    # list. If not (e.g. bot got stuck on a profile's posts grid after
                    # a failed back-navigation), attempt recovery.
                    if consecutive_empty_visible >= max_consecutive_empty:
                        if not strategy.is_on_list():
                            self.logger.warning(
                                f"⚠️ {consecutive_empty_visible} consecutive empty scans and not on "
                                f"target list — attempting recovery"
                            )
                            recovered = False
                            for _attempt in range(5):
                                self.device.press("back")
                                time.sleep(1.2)
                                if strategy.is_on_list():
                                    self.logger.info(f"✅ Recovered to target list after {_attempt + 1} back press(es)")
                                    consecutive_empty_visible = 0
                                    recovered = True
                                    break
                            if not recovered:
                                self.logger.error("❌ Could not recover to target list — stopping scraping")
                                break
                        else:
                            # We ARE on the list but it's empty — treat as end of list
                            consecutive_empty_visible = 0

                    # Try scrolling - wait for Instagram to load
                    strategy.scroll_down()
                    time.sleep(1.5)

                    if scroll_detector.is_the_end():
                        self.logger.info("Reached end of list")
                        break
                    continue

                # Successful scan — reset the empty-visible counter
                consecutive_empty_visible = 0

                new_count = 0
                new_visible_count = 0  # new usernames seen (including dedup-skipped) — used for end-of-list detection
                for follower in visible:
                    username = follower.get('username')
                    element = follower.get('element')
                    if not username or username in seen_usernames:
                        continue
                    
                    seen_usernames.add(username)
                    new_visible_count += 1  # counts even if dedup-skipped

                    # Skip profiles already scraped within the rescrape window — direct DB check
                    # Also track whether the profile pre-existed (used for ai_rescrape_mode below)
                    _profile_preexisted = False
                    if _dedup_db is not None:
                        try:
                            if _dedup_db.profile_exists_in_db(username, days=rescrape_after_days):
                                if rescrape_after_days:
                                    skip_reason = f"in DB, created < {rescrape_after_days}d ago"
                                else:
                                    skip_reason = "already in DB"
                                self.logger.info(f"⏭️  @{username} — skipped ({skip_reason})")
                                IPCEmitter.emit_profile_skipped(username, skip_reason)
                                continue
                            # Profile passed dedup: check if it pre-existed (for AI rescrape mode)
                            _profile_preexisted = _dedup_db.profile_exists_in_db(username, days=None)
                        except Exception as _dedup_err:
                            self.logger.debug(f"Dedup check failed for @{username}: {_dedup_err}")

                    profile_data = {
                        'username': username,
                        'source_type': source_type,
                        'source_name': source_name,
                        'scraped_at': datetime.now().isoformat()
                    }

                    # Emit visit event BEFORE clicking — card shows up in Agent panel immediately
                    IPCEmitter.emit_scraping_profile_visit(username, profile_data)

                    # If enriching on the fly, click on profile to get details
                    if enrich_on_the_fly and element:
                        try:
                            # Humanized tap within the profile element bounds (anti-detection) —
                            # this is the most frequent tap of the scrape. self.device is the raw
                            # u2 device here, so go through the shared helper; fallback to centre.
                            if not tap_element_human(self.device, element, logger=self.logger):
                                element.click()
                            time.sleep(1.5)
                            
                            # Use get_complete_profile_info with enrich=True for full data
                            # emit_ipc=False / save_to_db=False: list_scraping owns the IPC + save
                            enriched_data = self.profile_manager.get_complete_profile_info(
                                username=username,
                                navigate_if_needed=False,
                                enrich=True,
                                emit_ipc=False,
                                save_to_db=False
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
                                # Re-emit the visit with complete profile stats immediately,
                                # so the desktop live card updates before deep qualify starts.
                                IPCEmitter.emit_scraping_profile_visit(username, profile_data)
                            else:
                                self.logger.warning(f"Could not get profile info for @{username}")

                            # Also carry over profile_pic_base64 for the profile_captured event below
                            if enriched_data:
                                profile_data['profile_pic_base64'] = enriched_data.get('profile_pic_base64')

                            filter_reason = self._get_profile_filter_reason(profile_data) if enriched_data else None
                            if filter_reason:
                                self.logger.info(f"⏭️  @{username} — skipped ({filter_reason})")
                                IPCEmitter.emit_profile_skipped(username, filter_reason)
                                for _back_attempt in range(5):
                                    self.device.press("back")
                                    time.sleep(1.2)
                                    if strategy.is_on_list():
                                        break
                                continue

                            # Deep qualify: open following list, collect usernames, cross-ref DB
                            # Runs while still on the profile page, BEFORE taking the screenshot.
                            # Skip if the account is private — following list is inaccessible and
                            # attempting to open it desynchronises navigation (back-press loop).
                            if deep_qualify:
                                if profile_data.get('is_private'):
                                    self.logger.debug(f"⏭ @{username}: private account — skipping deep qualify")
                                else:
                                    _dq = self._deep_qualify_collect(
                                        username=username,
                                        max_following=deep_qualify_max_following,
                                    )
                                    profile_data.update(_dq)

                            # Capture screenshot for AI vision analysis (while still on profile page)
                            # Skip if ai_rescrape_mode = 'stats_only' and profile already existed in DB
                            _ai_rescrape_mode = self.config.get('ai_rescrape_mode', 'full')
                            _skip_ai_for_existing = _ai_rescrape_mode == 'stats_only' and _profile_preexisted
                            if getattr(self, '_ai_service', None) and not _skip_ai_for_existing:
                                try:
                                    import tempfile as _tempfile, os as _os2
                                    _tmp_dir = _os2.path.join(_tempfile.gettempdir(), 'taktik_ai')
                                    _os2.makedirs(_tmp_dir, exist_ok=True)
                                    _screenshot_path = _os2.path.join(_tmp_dir, f'profile_{username}.png')
                                    self.device.screenshot().save(_screenshot_path, format='PNG')
                                    profile_data['_screenshot_path'] = _screenshot_path
                                except Exception as _e:
                                    self.logger.debug(f"AI screenshot capture failed for @{username}: {_e}")

                            # Go back to the list — retry up to 5 times
                            # (Instagram can push extra screens: story preview, nested profile, etc.)
                            for _back_attempt in range(5):
                                self.device.press("back")
                                time.sleep(1.2)
                                if strategy.is_on_list():
                                    if _back_attempt > 0:
                                        self.logger.debug(f"✅ Back on list after {_back_attempt + 1} press(es)")
                                    break
                                self.logger.debug(f"⚠️ Not on target list after {_back_attempt + 1} back press(es), retrying...")
                            else:
                                self.logger.warning("⚠️ Could not return to target list after 5 back presses")
                            
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
                    profile_id = self._save_profile_immediately(profile_data, source_post_url=source_post_url)

                    # Signal Agent panel that this profile has been saved (completes the visit card)
                    _pic_b64 = profile_data.pop('profile_pic_base64', None)
                    IPCEmitter.emit_profile_captured(username, profile_data, profile_pic_base64=_pic_b64)

                    # AI qualification (if enabled and profile was enriched with bio data)
                    if enrich_on_the_fly and profile_id and getattr(self, '_ai_service', None) and not profile_data.get('is_private', False):
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
                
                if new_visible_count == 0:
                    # Check if there's a "See more" / "Load more" button before giving up
                    if strategy.check_load_more():
                        self.logger.info("✅ Clicked 'See more' - waiting for new profiles to load")
                        time.sleep(2.0)
                        continue  # Re-process without counting as a failed scroll

                    no_new_users_count += 1
                    self.logger.debug(f"No new users found ({no_new_users_count}/{max_no_new_users})")
                    
                    # Check suggestions only after collecting enough profiles
                    if strategy.enable_suggestions_check and len(scraped) >= min_profiles_before_suggestions_check:
                        if strategy.is_in_suggestions():
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
                    strategy.scroll_down()
                    
                    # Wait for content to actually change (not just a fixed delay)
                    max_wait_attempts = 5
                    for wait_attempt in range(max_wait_attempts):
                        time.sleep(1.0)  # Wait 1s between checks
                        new_visible = strategy.get_visible()
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
                    if strategy.is_end_reached():
                        self.logger.info("📋 Reached 'And X others' - end of accessible profiles")
                        break
                    
                    # Check for suggestions section
                    if strategy.enable_suggestions_check and strategy.is_suggestions_visible():
                        self.logger.info("📋 Reached suggestions section - end of real profiles")
                        break
                else:
                    # Reset counter when we find new users
                    no_new_users_count = 0
                    # Only scroll when all currently visible profiles have been processed.
                    # In enrich_on_the_fly mode we break after each profile and re-fetch,
                    # so visible may still contain unprocessed profiles — don't scroll yet.
                    if not has_unprocessed_visible:
                        # Scroll down to reveal more profiles
                        strategy.scroll_down()
                        
                        # Wait for Instagram to finish loading (detect spinner)
                        max_loading_wait = 10  # Max 10 seconds waiting for loading
                        for _ in range(max_loading_wait):
                            time.sleep(1.0)
                            if not strategy.is_loading():
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

        if profile.get('is_private', False):
            self.logger.debug(f"⏭ @{username}: private account — skipping AI classification")
            return

        # ── Vision-based classification (screenshot captured on profile page) ──────
        if screenshot_path and _os.path.exists(screenshot_path):
            result = {'success': False}
            try:
                result = self._ai_service.classify_profile_niche(
                    username=username,
                    screenshot_path=screenshot_path,
                    profile_context=profile,
                    response_language=self.config.get('response_language', 'en'),
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
                        self._local_db().update_profile_city(profile_id, city_str)
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

        scrape_likers = self.config.get('scrape_likers', True)
        scrape_commenters = self.config.get('scrape_commenters', False)
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
            scrape_mode = []
            if scrape_likers: scrape_mode.append('likers')
            if scrape_commenters: scrape_mode.append('commenters')
            console.print(f"[cyan]🔍 Scraping #{hashtag} ({'+'.join(scrape_mode) or 'none'}, max {remaining} profiles)...[/cyan]")

            # Track which post grid positions have already been clicked this hashtag
            # so we never re-open the same thumbnail after pressing back.
            seen_post_positions: set = set()
            no_new_posts_scrolls = 0  # consecutive scrolls that produced no new post to click
            max_no_new_posts_scrolls = 3

            while total_scraped < max_profiles and posts_checked < max_posts and self._should_continue():
                # Click the next unseen post thumbnail
                clicked = self._click_next_post(seen_post_positions)
                if not clicked:
                    # All currently visible posts have been processed — scroll the
                    # hashtag grid to load the next batch of thumbnails.
                    no_new_posts_scrolls += 1
                    if no_new_posts_scrolls >= max_no_new_posts_scrolls:
                        self.logger.info("No more new posts in hashtag grid after scrolling")
                        break
                    self.logger.debug(f"All visible posts processed, scrolling hashtag grid ({no_new_posts_scrolls}/{max_no_new_posts_scrolls})...")
                    self.scroll_actions.scroll_down()
                    time.sleep(1.5)
                    continue  # retry without incrementing posts_checked

                no_new_posts_scrolls = 0
                posts_checked += 1
                time.sleep(1.5)

                # Get post URL first for dedup and tracking (needed by both likers and commenters)
                post_url = self._get_post_url()
                if post_url:
                    self.logger.info(f"🔗 URL du post récupérée : {post_url}")
                    if self._ipc:
                        self._ipc.send("post_url_found", url=post_url, hashtag=hashtag)
                    try:
                        _db = self._local_db()
                        if _db.is_post_url_already_scraped(post_url):
                            self.logger.info(f"⏭️  Post already scraped: {post_url} — skipping")
                            self.device.press("back")
                            time.sleep(1)
                            continue
                    except Exception as _e:
                        self.logger.debug(f"Post URL dedup check failed: {_e}")
                else:
                    self.logger.debug("Could not retrieve post URL (share button unavailable)")

                enrich_profiles = self.config.get('enrich_profiles', False)

                if scrape_likers:
                    # Open likers popup and scrape
                    if self._open_likers_list():
                        time.sleep(1)
                        likers = self._scrape_list(
                            max_count=min(20, max_profiles - total_scraped),
                            source_type='HASHTAG_LIKER',
                            source_name=hashtag,
                            enrich_on_the_fly=enrich_profiles,
                            source_post_url=post_url,
                        )
                        total_scraped += len(likers)
                        # Close the likers popup. When the user has scrolled to the
                        # end of the list, Instagram expands the bottom sheet to
                        # full-screen. In that case, the first back press only
                        # collapses it (half-open); we detect this and press again.
                        self.device.press("back")
                        time.sleep(0.5)
                        if is_likers_popup_open(self.device, self.logger):
                            self.logger.debug("Likers popup still open after back (was fully expanded), closing again")
                            self.device.press("back")
                            time.sleep(0.5)

                if scrape_commenters and total_scraped < max_profiles:
                    # Open comments and scrape commenters
                    commenters = self._scrape_post_commenters(
                        max_count=min(20, max_profiles - total_scraped),
                        source_name=hashtag,
                        enrich_on_the_fly=enrich_profiles,
                        source_post_url=post_url,
                    )
                    total_scraped += len(commenters)

                # Go back to hashtag grid
                self.device.press("back")
                time.sleep(1)

            console.print(f"[green]✅ #{hashtag}: {total_scraped} profiles scraped ({posts_checked} posts checked)[/green]")

        return {
            "success": True,
            "total_scraped": total_scraped,
            "posts_checked": posts_checked_total
        }

    def _scrape_post_url(self) -> Dict[str, Any]:
        """Scrape likers and/or commenters from one or more post URLs."""
        # Support both post_urls list (new) and single post_url (backward compat)
        post_urls = self.config.get('post_urls', [])
        if not post_urls:
            single = self.config.get('post_url', '')
            if single:
                post_urls = [single]
        if not post_urls:
            return {"success": False, "error": "No post URL provided"}

        scrape_likers = self.config.get('scrape_likers', True)
        scrape_commenters = self.config.get('scrape_commenters', False)
        max_profiles = self.config.get('max_profiles', 200)
        enrich_profiles = self.config.get('enrich_profiles', False)
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

            if scrape_likers:
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

                if likers:
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
                else:
                    self.logger.error("Failed to extract likers")

            if scrape_commenters and total_scraped < max_profiles:
                console.print("[cyan]📍 Scraping commenters...[/cyan]")
                commenters = self._scrape_post_commenters(
                    max_count=max_profiles - total_scraped,
                    source_name=post_id,
                    enrich_on_the_fly=enrich_profiles,
                    source_post_url=post_url,
                )
                total_scraped += len(commenters)

        return {
            "success": True,
            "total_scraped": total_scraped
        }

    def _open_likers_list(self) -> bool:
        """Open the likers list by clicking on like count (for hashtag scraping)."""
        return open_likers_list(self.device, self.ui_extractors, self.logger)
