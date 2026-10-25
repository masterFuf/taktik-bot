import random
import re
import time
from typing import Callable, Optional, List, Any, Dict, Tuple
from loguru import logger
from taktik.core.shared.device.screen import screen_size_of
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.actions.utils import ActionUtils, normalise_number_spaces
from taktik.core.shared.behavior.gesture_primitives import human_drag_between_raw
from taktik.core.social_media.instagram.ui.labels import is_ui_label
from taktik.core.social_media.instagram.ui.detectors.scroll_end import likers_list_end_detector

log = logger.bind(module="instagram-ui-extractors")

#: A drag of the likers sheet starts this far under its first liker row...
LIKERS_DRAG_BELOW_FIRST_ROW_PX = 100
#: ...and goes up this far, but never above this fraction of the screen height.
LIKERS_DRAG_UP_PX = 400
LIKERS_DRAG_HIGHEST = 0.35
#: The shortest drag of the sheet, as a fraction of the screen height: a shorter one hardly moves
#: the list, and two of them would read as its end.
LIKERS_DRAG_MIN_TRAVEL = 0.15
#: The drag without a usable first row: from 70 % to 45 % of the screen height.
LIKERS_DRAG_PROPORTIONAL = (0.70, 0.45)


def likers_drag_path(first_row_y: Optional[int], screen_height: int) -> Tuple[int, int]:
    """(start Y, end Y) of the drag that scrolls the likers sheet up.

    From under the first liker row (`first_row_y`, its centre) when that drag goes up far enough;
    otherwise, or without a row, the proportional drag. A first row high on the screen (a sheet
    pulled up to full height) would give a short drag, or one going down."""
    proportional = (int(screen_height * LIKERS_DRAG_PROPORTIONAL[0]), int(screen_height * LIKERS_DRAG_PROPORTIONAL[1]))
    if first_row_y is None:
        return proportional
    start_y = first_row_y + LIKERS_DRAG_BELOW_FIRST_ROW_PX
    end_y = max(first_row_y - LIKERS_DRAG_UP_PX, int(screen_height * LIKERS_DRAG_HIGHEST))
    if start_y - end_y < int(screen_height * LIKERS_DRAG_MIN_TRAVEL):
        return proportional
    return start_y, end_y


class InstagramUIExtractors:
    def __init__(self, device, framed_post=None):
        """`framed_post`: the reader of the framed post of a list of posts, the scroll owner built on
        the same device (`PostReadingMixin.framed_post_like_target`, the reading the like uses). It
        says which button row is the framed post's; without it no like counter is taken on a list."""
        self.device = device
        self.framed_post = framed_post

        from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS, POPUP_SELECTORS, DETECTION_SELECTORS
        self.post_selectors = POST_SELECTORS
        self.popup_selectors = POPUP_SELECTORS
        self.detection_selectors = DETECTION_SELECTORS
    
    def extract_post_stats_atomic(self) -> Dict[str, int]:
        """
        Extract likes and comments counts atomically from the same carousel element.
        This prevents timing issues during scrolling where likes and comments 
        might be read from different posts.
        
        Returns:
            dict: {'likes': int, 'comments': int} or None if extraction failed
        """
        try:
            # The media label is the atomic source on IG 442: one string carries BOTH counts
            # ("Reel de X, 96 J<U+2019>aime, 9 commentaires, 9 aout"), which is exactly what this
            # method exists to read. Without it no carousel selector matched on a French phone
            # -- the only generic one wants the English "likes"/"comment" -- so the atomic path
            # always failed and callers fell back to reading the two counts SEPARATELY, which on
            # a screen showing two posts takes them from different ones.
            sources = list(self.detection_selectors.carousel_selectors)
            sources.append(self.post_selectors.photo_imageview_selector)
            for selector in sources:
                try:
                    elements = self.device.xpath(selector).all()
                    for element in elements:
                        element_info = element.info
                        content_desc = element_info.get('contentDescription', '')
                        
                        if not content_desc:
                            continue
                        
                        counts = post_counts_from_media_label(content_desc)
                        if counts is not None:
                            likes_count, comments_count = counts
                            log.debug(f"✅ Post stats extracted atomically from carousel: {likes_count} likes, {comments_count} comments")
                            log.debug(f"   Source content-desc: {content_desc[:100]}...")
                            return {
                                'likes': likes_count,
                                'comments': comments_count
                            }

                except Exception as e:
                    log.debug(f"Error with carousel selector {selector}: {e}")
                    continue
            
            log.debug("⚠️ Could not extract post stats atomically, falling back to separate extraction")
            return None
            
        except Exception as e:
            log.error(f"Error in atomic extraction: {e}")
            return None
    
    def parse_instagram_number(self, text: str) -> int:
        """Parse Instagram number - delegates to parse_number_from_text"""
        return parse_number_from_text(text)
    
    def is_like_count_text(self, text: str) -> bool:
        if not text:
            return False
        
        cleaned_text = re.sub(r'[\s,.\u00A0\u2000-\u200F\u2028-\u202F\u205F\u3000]+', '', text)
        
        if cleaned_text.endswith('K') or cleaned_text.endswith('k'):
            try:
                number = float(cleaned_text[:-1])
                return number > 0
            except ValueError:
                return False
        elif cleaned_text.endswith('M') or cleaned_text.endswith('m'):
            try:
                number = float(cleaned_text[:-1])
                return number > 0
            except ValueError:
                return False
        
        try:
            count = int(cleaned_text)
            return count > 0
        except ValueError:
            return False
    
    def extract_likes_count_from_ui(self, is_reel: bool = None) -> int:
        try:
            # Try Reel like count selector first (skip if caller confirmed not a reel)
            if is_reel is not False:
                try:
                    element = self.device.xpath(self.detection_selectors.reel_like_count_selector)
                    if element.exists:
                        info = element.info
                        # content-desc AND text carry the same label on this surface; some
                        # builds fill only one of the two.
                        label = info.get('contentDescription') or info.get('text') or ''
                        likes_count = count_from_counter_label(label)
                        if likes_count is not None:
                            log.debug(f"✅ Likes extracted from Reel counter: {likes_count}")
                            return likes_count
                except Exception as e:
                    log.debug(f"Reel like selector not found or error: {e}")
            
            all_photo_elements = self.device.xpath(self.post_selectors.photo_imageview_selector).all()
            
            for i, element in enumerate(all_photo_elements):
                try:
                    element_info = element.info
                    content_desc = element_info.get('contentDescription', '')
                    
                    likes_count = likes_from_media_label(content_desc)
                    if likes_count is not None:
                        log.debug(f"✅ Likes extracted from content-desc: {likes_count}")
                        return likes_count
                except Exception as e:
                    log.debug(f"Error with photo element {i+1}: {e}")
                    continue
            
            for selector in self.post_selectors.button_like_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    max_likes = 0
                    max_text = ""
                    
                    for element in elements:
                        element_info = element.info
                        text = element_info.get('text', '')
                        if text and self.is_like_count_text(text):
                            likes_count = self.parse_instagram_number(text)
                            if likes_count > max_likes:
                                max_likes = likes_count
                                max_text = text
                    
                    if max_likes > 0:
                        log.debug(f"✅ Likes extracted from button: {max_likes} (text: '{max_text}')")
                        return max_likes
                        
                except Exception as e:
                    log.debug(f"Error with button selector {selector}: {e}")
                    continue
            
            log.debug("⚠️ Like count not found")
            return 0
            
        except Exception as e:
            log.error(f"Error extracting likes: {e}")
            return 0
    
    def extract_comments_count_from_ui(self, is_reel: bool = None) -> int:
        try:
            # Try Reel comment count selector first (skip if caller confirmed not a reel)
            if is_reel is not False:
                try:
                    element = self.device.xpath(self.detection_selectors.reel_comment_count_selector)
                    if element.exists:
                        info = element.info
                        label = info.get('contentDescription') or info.get('text') or ''
                        comments_count = count_from_counter_label(label)
                        if comments_count is not None:
                            log.debug(f"✅ Comments extracted from Reel counter: {comments_count}")
                            return comments_count
                except Exception as e:
                    log.debug(f"Reel comment selector not found or error: {e}")
            
            all_photo_elements = self.device.xpath(self.post_selectors.photo_imageview_selector).all()
            
            for i, element in enumerate(all_photo_elements):
                try:
                    element_info = element.info
                    content_desc = element_info.get('contentDescription', '')
                    
                    comments_count = comments_from_media_label(content_desc)
                    if comments_count is not None:
                        log.debug(f"✅ Comments extracted from content-desc: {comments_count}")
                        return comments_count
                except Exception as e:
                    log.debug(f"Error with photo element {i+1}: {e}")
                    continue
            
            for selector in self.post_selectors.button_like_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    numeric_buttons = []
                    for element in elements:
                        element_info = element.info
                        text = element_info.get('text', '')
                        if text and self.is_like_count_text(text):
                            parsed_number = self.parse_instagram_number(text)
                            if parsed_number >= 0:
                                numeric_buttons.append((parsed_number, text))
                    
                    if len(numeric_buttons) >= 2:
                        numeric_buttons.sort(reverse=True, key=lambda x: x[0])
                        comments_count, comments_text = numeric_buttons[1]
                        log.debug(f"✅ Comments extracted from buttons: {comments_count}")
                        return comments_count
                    elif len(numeric_buttons) == 1:
                        return 0
                        
                except Exception as e:
                    log.debug(f"Error with button selector {selector}: {e}")
                    continue
            
            log.debug("⚠️ Comment count not found")
            return 0
            
        except Exception as e:
            log.error(f"Error extracting comments: {e}")
            return 0
    
    
    def find_like_count_element(self, logger_instance=None):
        """The like counter that opens the likers of the post the screen frames; None when the
        screen shows none.

        On a list of posts (the home feed, a hashtag's or a profile's posts), only the framed
        post's own button row counts: the row at the top of the screen is often the post above's.
        When that row runs under the bottom, it is brought up first (one short drag, the like's).
        In that row the counter is the button just after the heart (`like_count_selectors`); a post
        that hides its likes has none there, and the first number of its row is its comment count.
        Off a list (the full-screen Reel viewer), the viewer's own counter.
        """
        logger_to_use = logger_instance if logger_instance else log
        candidates = self._framed_post_row_elements(
            self.post_selectors.like_count_selectors, "like counter", logger_to_use)
        if candidates is None:
            return None

        for selector, element in candidates:
            try:
                text = None
                if hasattr(element, 'text'):
                    text = element.text
                elif hasattr(element, 'get_text'):
                    text = element.get_text()
                elif hasattr(element, 'attrib') and 'text' in element.attrib:
                    text = element.attrib['text']

                content_desc = None
                try:
                    element_info = element.info
                    content_desc = element_info.get('contentDescription', '')
                except Exception as exc:
                    logger_to_use.debug(f"Counter description unreadable, its text read alone: {exc}")

                logger_to_use.debug(f"Checking element - text: '{text}', content-desc: '{content_desc}' (clickable: {element.attrib.get('clickable', 'unknown')})")

                # Case 1: the label IS the number, on regular posts.
                if text and self.is_like_count_text(text):
                    logger_to_use.info(f"✅ Valid like counter found (post): {selector} (text: '{text}')")
                    return element

                # Case 2: on reels the number is embedded in a sentence. The SELECTOR
                # already points at the like counter, so all that is left is checking
                # that it carries a NUMBER — a check that must not be written in one
                # language, or the element is found and then rejected.
                label = content_desc or text
                count = count_from_counter_label(label) if label else None
                if count:  # 0 behaves like None: nothing to open here either
                    logger_to_use.info(f"✅ Valid like counter found ({count} likes): {selector} (label: '{label}')")
                    return element
            except Exception as e:
                logger_to_use.debug(f"Error checking element: {e}")
                continue

        logger_to_use.warning("❌ No like counter found with all selectors")
        return None

    def framed_post_element(self, selectors, what: str, logger_instance=None):
        """The first element `selectors` find on the post the screen frames; None when the screen
        shows none. `what` names it in the log ("comment button", "share button").

        The gestures of a post's button row (comment, share) go through it: on a list of posts (the
        home feed, a hashtag's or a profile's posts) the first button of the screen is often the
        post above's, and a comment typed after tapping it is published under that post. So only
        the framed post's own button row counts, as for its like counter, brought up first when it
        runs under the bottom; off a list (the full-screen Reel viewer), the viewer's own button."""
        logger_to_use = logger_instance if logger_instance else log
        candidates = self._framed_post_row_elements(selectors, what, logger_to_use)
        if candidates is None:
            return None
        for selector, element in candidates:
            logger_to_use.debug(f"The framed post's {what}: {selector}")
            return element
        logger_to_use.warning(f"No {what} on the framed post")
        return None

    def _framed_post_row_elements(self, selectors, what: str, logger_to_use):
        """(selector, element) for each element `selectors` find on the post the screen frames, in
        selector order; None when that post cannot be told on this screen.

        On a list of posts, only what lies in the framed post's own button row, which the framed
        post's reader gives (`PostReadingMixin.framed_post_like_target`, the reading the like
        uses). When that row runs under the bottom of the list, the reader brings it up first and
        checks the post is still the same (`PostReadingMixin.show_framed_post_row_of`, the like's
        own short drag): None when it cannot. Off a list, every element found."""
        target = self._framed_post_target(logger_to_use, what)
        if target is None:
            return None
        on_a_list, framed_row = target["list"], target.get("row")
        if on_a_list and framed_row is None:
            logger_to_use.debug(f"The framed post's button row is not on screen: shown first for its {what}")
            reader = self.framed_post  # set: `_framed_post_target` read the target through it
            shown = reader.show_framed_post_row_of(target.get("identity"), what) if reader is not None else None
            if shown is None:
                return None
            framed_row = shown["row"]
        return self._elements_in_row(selectors, framed_row if on_a_list else None, what, logger_to_use)

    def _elements_in_row(self, selectors, row, what: str, logger_to_use):
        """(selector, element) for each element `selectors` find, those outside `row` left out (row
        None: none left out). Lazy: the next selector is asked only when the caller wants more, one
        screen read per selector asked."""
        for selector in selectors:
            try:
                elements = self.device.xpath(selector).all()
            except Exception as e:
                logger_to_use.debug(f"Error with selector {selector}: {e}")
                continue
            logger_to_use.debug(f"Selector '{selector}' found {len(elements)} elements")
            for element in elements:
                try:
                    in_row = row is None or _in_row(element.bounds, row)
                except Exception as e:
                    logger_to_use.debug(f"{what.capitalize()} without bounds skipped ({selector}): {e}")
                    continue
                if not in_row:
                    logger_to_use.debug(f"{what.capitalize()} of another post's row skipped: {element.bounds}")
                    continue
                yield selector, element

    def _framed_post_target(self, logger_to_use, what: str) -> Optional[Dict[str, Any]]:
        """What the framed post's reader says of the screen: a list of posts and the framed post's
        button row, or no list at all. None when it cannot be told."""
        if self.framed_post is None:
            logger_to_use.error(f"No reader of the framed post: its {what} cannot be told from another post's")
            return None
        target = self.framed_post.framed_post_like_target()
        if target is None:
            logger_to_use.warning(f"Screen unreadable: no {what}")
        return target

    def extract_usernames_from_likers_popup(
        self,
        max_interactions: int = None,
        automation=None,
        logger_instance=None,
        add_initial_sleep: bool = False,
        current_max_interactions_attr: Any = None,
        keep_going: Optional[Callable[[], bool]] = None,
    ) -> List[str]:
        """The eligible likers of the open likers sheet, read screen after screen until the target,
        the end of the list or `max_scrolls`.

        The end of the list is the one `likers_list_end_detector` tells from the likers SHOWN on
        each screen, eligible or not: two scrolls in a row that change nothing. Every reading here
        follows a scroll but the first. A list whose first likers were all handled before still
        moves, and the reading goes on.

        With `automation` (the run), a liker is eligible when the account the run acts as has not
        handled it before, and is not that account itself (`automation.active_username`): a run
        that liked the post is among its likers. Without `automation`, every liker shown is kept
        (the scraping's reading). `keep_going`, when given, is asked before each screen: the
        scraping's session clock stops the reading too."""

        logger_to_use = logger_instance if logger_instance else log
        account_id = getattr(automation, 'active_account_id', None) if automation else None
        acting_username = getattr(automation, 'active_username', None) if automation else None

        usernames = []
        
        if max_interactions is not None:
            target_count = max_interactions
        elif current_max_interactions_attr is not None:
            target_count = current_max_interactions_attr
        else:
            target_count = 30
        
        max_scrolls = min(200, target_count * 2)
        scroll_count = 0
        list_end = likers_list_end_detector()
        
        logger_to_use.info(f"🔄 Optimized extraction for {target_count} users")
        
        if add_initial_sleep:
            logger_to_use.debug("⏳ Waiting for usernames to load (2s)...")
            time.sleep(2.0)
        
        try:
            while scroll_count < max_scrolls and len(usernames) < target_count:
                if keep_going is not None and not keep_going():
                    logger_to_use.info(f"⏹️ Stop: the session ends, after {scroll_count} scroll(s)")
                    break
                users_before = len(usernames)
                
                new_users = self.extract_visible_usernames(logger_instance=logger_to_use)
                list_end.notify_new_page(new_users)
                end_reason = list_end.end_reason()
                if end_reason is not None:
                    logger_to_use.info(f"🏁 Stop: end of the likers list after {scroll_count} scroll(s), {end_reason}")
                    break
                
                for username in new_users:
                    if username not in usernames and len(usernames) < target_count:
                        if automation:
                            if ActionUtils.same_username(username, acting_username):
                                logger_to_use.debug(f"⏭️ @{username} is the account the run acts as: not eligible")
                                continue
                            if InstagramWorkflowStateService.is_profile_already_processed(username, account_id):
                                continue
                        
                        usernames.append(username)
                        logger_to_use.debug(f"✅ Eligible user: @{username} ({len(usernames)}/{target_count})")
                        
                        if len(usernames) >= target_count:
                            logger_to_use.info(f"🎯 Target reached! {len(usernames)} users collected")
                            break
                
                if len(usernames) >= target_count:
                    logger_to_use.info(f"🏁 Optimized stop: target of {target_count} users reached")
                    break
                
                if len(usernames) == users_before:
                    logger_to_use.debug(f"⚠️ No new eligible user on this screen ({len(new_users)} shown)")
                else:
                    gained = len(usernames) - users_before
                    logger_to_use.info(f"📈 Scroll #{scroll_count + 1}: +{gained} eligible users (total: {len(usernames)}/{target_count})")
                
                scroll_success = self.scroll_likers_popup_up(logger_instance=logger_to_use)
                if not scroll_success:
                    logger_to_use.warning("⚠️ Scroll failed - popup closed or not detected")
                    break
                
                scroll_count += 1
                time.sleep(0.6)
            
            if scroll_count >= max_scrolls and len(usernames) < target_count:
                logger_to_use.info(f"🛑 Stop: {max_scrolls} scrolls, the most a reading of {target_count} users makes")
            logger_to_use.info(f"🎯 Extraction completed: {len(usernames)} users in {scroll_count} scrolls")
            return usernames
            
        except Exception as e:
            logger_to_use.error(f"❌ Error extracting users from popup: {e}")
            return []
    
    def extract_visible_usernames(self, logger_instance=None) -> List[str]:
        logger_to_use = logger_instance if logger_instance else log
        usernames = []
        
        for selector in self.popup_selectors.username_in_popup_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        username = self.extract_username_from_element(element, logger_instance=logger_to_use)
                        if username and username not in usernames:
                            usernames.append(username)
            except Exception as e:
                logger_to_use.debug(f"Error with selector {selector}: {e}")
                continue
        
        return usernames
    
    def extract_username_from_element(self, element, logger_instance=None) -> Optional[str]:

        logger_to_use = logger_instance if logger_instance else log
        
        try:
            text = None
            if hasattr(element, 'get_text'):
                text = element.get_text()
            elif hasattr(element, 'text'):
                text = element.text
            
            if not text:
                return None
            
            username = text.strip().replace('@', '')
            
            if self.is_valid_username(username):
                return username
            
            return None
            
        except Exception as e:
            logger_to_use.debug(f"Error extracting username: {e}")
            return None
    
    def is_valid_username(self, username: str) -> bool:
        """True when `username` is a plausible handle and not an interface label.

        Shape is delegated to the shared validator (Instagram bounds 1-30) so this
        extractor cannot drift from the rest of the bot: the local copy used to reject
        handles legitimately starting with `_` or `.` and to accept the `..` sequence
        Instagram forbids.

        The label guard goes through `is_ui_label`, which compares against the locale
        catalogues with both sides folded. The list used to live here as raw text with an
        ASCII apostrophe, so "j'aime" never matched the "J'aime" the phone renders (U+2019)
        and the label sailed through as a username — silently, and only in French.
        """
        if not ActionUtils.is_valid_username(username, min_length=1, max_length=30):
            return False
        return not is_ui_label(username)
    
    def scroll_likers_popup_up(
        self,
        logger_instance=None,
        is_likers_popup_open_checker=None,
        verbose_logs: bool = True
    ) -> bool:

        logger_to_use = logger_instance if logger_instance else log
        
        try:
            if is_likers_popup_open_checker and not is_likers_popup_open_checker():
                if verbose_logs:
                    logger_to_use.warning("⚠️ Likers popup not detected - cannot scroll")
                return False
            
            screen_width, screen_height = screen_size_of(self.device)

            if verbose_logs:
                logger_to_use.debug(f"📱 Resolution detected: {screen_width}x{screen_height}")
            
            # Reduced wait time for faster extraction (was 0.8s)
            time.sleep(0.3)

            first_row_y = self._first_liker_row_y(logger_to_use)
            start_y, end_y = likers_drag_path(first_row_y, screen_height)
            if first_row_y is None:
                logger_to_use.debug("⚠️ No liker row on screen, proportional drag")
            elif start_y == first_row_y + LIKERS_DRAG_BELOW_FIRST_ROW_PX:
                logger_to_use.debug(f"✅ First liker at Y={first_row_y}: drag {start_y} → {end_y}")
            else:
                logger_to_use.debug(f"⚠️ First liker at Y={first_row_y}, too high for a drag from it: proportional drag")

            # start_y/end_y are ADAPTIVE (from the first username's Y, so the next page resumes
            # where extraction left off): the gesture must travel exactly that far, which a
            # sampled scroll does not. The shared drag between two given points does, lifting at
            # near-zero speed so the list does not coast past unread rows. It takes the facade a
            # Lab action holds as well as the raw device a run holds: `self.device.swipe(...,
            # duration=)` only existed on the raw device, and on the facade (direction-based
            # `swipe`) every scroll raised, the popup read as closed and "0 liker(s)" came back.
            x = int(screen_width * random.uniform(0.4, 0.6))
            drift = int(screen_width * random.uniform(-0.02, 0.02))
            duration = random.uniform(0.45, 0.65)
            if not human_drag_between_raw(self.device, (x, start_y), (x + drift, end_y), duration, logger_to_use):
                return False

            if verbose_logs:
                logger_to_use.debug(f"📜 Adaptive scroll in likers popup: ({x},{start_y}) → ({x + drift},{end_y}) in {duration:.2f}s")

            time.sleep(0.2)
            return True
            
        except Exception as e:
            logger_to_use.error(f"❌ Error scrolling popup: {e}")
            return False

    def _first_liker_row_y(self, logger_to_use) -> Optional[int]:
        """The centre Y of the highest liker row of the sheet, found as the reading finds its rows
        (`username_in_popup_selectors`); None when no row shows."""
        for selector in self.popup_selectors.username_in_popup_selectors:
            tops = []
            for element in self.device.xpath(selector).all():
                bounds = element.info.get('bounds') or {}
                if bounds:
                    tops.append((bounds.get('top', 0) + bounds.get('bottom', 0)) // 2)
            if tops:
                return min(tops)
        logger_to_use.debug("No liker row found by any likers selector")
        return None
    
    def is_reel_post(self, logger_instance=None) -> bool:
        logger_to_use = logger_instance if logger_instance else log
        
        try:
            for indicator in self.post_selectors.reel_indicators:
                try:
                    if self.device.xpath(indicator).exists:
                        logger_to_use.debug(f"🎬 Reel detected with: {indicator}")
                        return True
                except Exception as e:
                    logger_to_use.debug(f"Error testing Reel indicator {indicator}: {e}")
                    continue
            
            logger_to_use.debug("📷 Classic post detected")
            return False
            
        except Exception as e:
            logger_to_use.debug(f"Error detecting Reel: {e}")
            return False



def parse_instagram_number(text: str) -> int:
    """Parse Instagram number - delegates to parse_number_from_text"""
    return parse_number_from_text(text)


def _in_row(bounds, row) -> bool:
    """An element of a post's button row lies between the row's top and bottom, as the framed
    post's reader keeps the counters and the heart of its row (`PostReadingMixin._framed_window`)."""
    return row[1] <= bounds[1] and bounds[3] <= row[3]


# One count as Instagram writes it in a label, whatever the language, once the label went through
# `normalise_number_spaces`: thousands grouped by a space, a comma or a dot ("14 260", "14,260",
# "14.260"), or a decimal before a K/M/B suffix ("14,2 K", "46.4K"). A group of exactly three
# digits is what tells a thousands separator from a decimal comma. The suffix only counts when no
# letter follows it, so a German "12 Kommentare" is not read as 12 000. It never starts right after
# a digit, so it never begins inside another number.
#
# The ONE reading of a count in a label: the counter labels (`count_from_counter_label`) and the
# media label of a post (`post_counts_from_media_label`) both go through it. The media label had
# its own, `\d+(?:[,.]\d+)?`, which stopped at the first thousands separator: "14 260 J'aime" was
# saved as 260 likes.
_COUNT_TOKEN = r'(?<!\d)(?:\d{1,3}(?:[ ,.]\d{3})+(?!\d)|\d+(?:[.,]\d+)?)(?: ?[KkMmBb](?![^\W\d_]))?'
_COUNTER_VALUE = re.compile(_COUNT_TOKEN)

# The two counts of a post's media label: "Photo de X, 14 260 J'aime, 190 commentaires",
# "Photo by X, 11,100,590 likes, 46.4K comments". The apostrophe is TYPOGRAPHIC on the device
# (U+2019, sometimes U+02BC): the ASCII one alone never matched a French phone.
_MEDIA_LABEL_LIKES = re.compile(rf'({_COUNT_TOKEN})\s*(?:like|(?:j[\x27\u2019\u02bc`]?)?aime)', re.IGNORECASE)
_MEDIA_LABEL_COMMENTS = re.compile(rf'({_COUNT_TOKEN})\s*(?:comment|commentaire)', re.IGNORECASE)


def count_from_counter_label(label: Optional[str]) -> Optional[int]:
    """The number carried by a counter label, WHATEVER the app language.

    Instagram labels its reel counters in the phone's language: "Nombre de J'aime : 14.
    Voir les J'aime" (fr), "Like number is16. View likes" (en). The element itself is found
    by resource-id, which is language-neutral — but the value used to be read with an
    English sentence pattern, so on a French device every reel reported ZERO likes. A whole
    hashtag run was then filtered out as "too few likes" whatever threshold the operator set,
    and nothing in the logs pointed at the language.

    We therefore read the FIRST number of the label and ignore the words around it. Taking
    the first token matters: a label that also mentions comments or reshares would otherwise
    have its digits concatenated into one absurd number.

    `None` = no number in the label (unreadable), which is NOT the same as zero.
    """
    if not label:
        return None
    match = _COUNTER_VALUE.search(normalise_number_spaces(label))
    if not match:
        return None
    return parse_number_from_text(match.group(0))


def likes_from_media_label(label: Optional[str]) -> Optional[int]:
    """The like count of a post's media label; `None` when the label carries none (not zero)."""
    match = _MEDIA_LABEL_LIKES.search(normalise_number_spaces(label)) if label else None
    return parse_number_from_text(match.group(1)) if match else None


def comments_from_media_label(label: Optional[str]) -> Optional[int]:
    """The comment count of a post's media label; `None` when the label carries none (not zero)."""
    match = _MEDIA_LABEL_COMMENTS.search(normalise_number_spaces(label)) if label else None
    return parse_number_from_text(match.group(1)) if match else None


def post_counts_from_media_label(label: Optional[str]) -> Optional[tuple]:
    """(likes, comments) carried by the media label of a post, WHATEVER the app language.

    Both counts come from the same string, which is what makes the read atomic: on a list of
    posts, two elements can belong to two posts. `None` when the label does not carry both:
    half a pair would make the caller take the other half elsewhere.
    """
    likes = likes_from_media_label(label)
    comments = comments_from_media_label(label)
    if likes is None or comments is None:
        return None
    return likes, comments


def parse_number_from_text(text: str) -> int:
    """Parse a number from text, handling formats like '166 K', '1.2M', '1,234', etc."""
    if not text:
        return 0
    
    try:
        text_str = str(text).strip()
        
        # Normalize: remove non-breaking spaces and extra whitespace
        text_str = text_str.replace('\xa0', ' ').strip()
        
        multipliers = {
            'K': 1000, 'k': 1000,
            'M': 1000000, 'm': 1000000,
            'B': 1000000000, 'b': 1000000000
        }
        
        # Check for suffix with or without space (e.g., "166K", "166 K", "1.2 M")
        for suffix, multiplier in multipliers.items():
            # Handle "166 K" format (space before suffix)
            if text_str.endswith(f' {suffix}') or text_str.endswith(f' {suffix.lower()}'):
                try:
                    number_part = text_str[:-2].strip().replace(',', '.')
                    return int(float(number_part) * multiplier)
                except (ValueError, AttributeError):
                    continue
            # Handle "166K" format (no space)
            elif text_str.endswith(suffix):
                try:
                    number_part = text_str[:-1].strip().replace(',', '.')
                    return int(float(number_part) * multiplier)
                except (ValueError, AttributeError):
                    continue
        
        # No suffix found - extract digits only
        number_str = ''.join(c for c in text_str if c.isdigit() or c in ',. ')
        
        number_str = number_str.replace(' ', '').replace(',', '').replace('.', '')
        
        return int(number_str) if number_str else 0
        
    except (ValueError, AttributeError):
        return 0


# "Reel by <username>. Double-tap…" — two words of label, then the username, then whatever
# closes it. The username is matched lazily and must be followed by a dot AND a space, a comma,
# or the string end, so a dot INSIDE a username is never read as the terminator.
#
# The comma is not decoration: IG 442 appends the counters to the same label — "Reel de
# demo_studio, 96 J’aime, 9 commentaires, 9 août" — so a rule that only accepted a
# closing dot found no author at all on that build, and the hashtag workflow's 7-day dedup,
# which keys on the author, went quietly back to processing the same reels.
_MEDIA_LABEL_AUTHOR = re.compile(r'^\S+\s+\S+\s+([A-Za-z0-9._]+?)(?:\.\s|,|\.?$)')


def username_from_media_label(label: Optional[str]) -> Optional[str]:
    """The account behind a reel, WHATEVER the app language.

    Same trap as the counters: this label is translated ("Reel de X" in French, "Reel by X"
    in English) and the code only knew the English form, so on a French phone a reel had no
    author at all — which silently disabled the 7-day "already processed" dedup of the
    hashtag workflow, since it keys on the author.
    """
    if not label:
        return None
    match = _MEDIA_LABEL_AUTHOR.search(label.strip())
    if not match:
        return None
    username = match.group(1).strip('.').lower()
    return username or None


def username_from_author_header(text: Optional[str]) -> Optional[str]:
    """The account behind a post, from the author line of its header; None if it names none.

    A post in COLLABORATION names several accounts on that line, in the app's language:
    "abelstudios.au et mark.kobakian", "studioalldaylong and ab.buxton", "meta   and 2 others",
    "lequartiergenial et 3 autres personnes" (Lab dumps, 2026-06 to 2026-09). The line
    was taken whole: a like was filed under "@abelstudios.au et mark.kobakian", a profile that
    does not exist; the Feed's cleaner even glued it into one plausible handle.

    A handle has no space, so the first word of the line is the first author whatever the
    language and its conjunction: no "et" / "and" to know, hence none written here. The word
    must be a handle as it stands (not one a cleaner made up by removing characters) and not an
    interface label.
    """
    if not text or not text.strip():
        return None
    first = text.strip().split()[0].lstrip('@').lower()
    if first != ActionUtils.clean_username(first):
        return None
    if not ActionUtils.is_valid_username(first, min_length=1, max_length=30) or is_ui_label(first):
        return None
    return first


def post_signature(likes: Optional[int], comments: Optional[int], is_reel: bool) -> str:
    """Cheap identity of the post on screen: like count + comment count + reel flag.

    Instagram exposes no post id in the UI tree, so this triplet is what the bot uses to
    answer "am I still on the same post?" — after a scroll, after reading a caption, after
    a navigation that may not have moved. It lives here, next to the extractors that read
    those counters, because two places were about to spell the same convention themselves:
    the profile post sequence (`services/like/orchestration.py`) and the hashtag post viewer. Two
    spellings would mean two answers to the same question the day one of them is changed.
    """
    return f"{likes}_{comments}_{is_reel}"


def get_text_from_element(element) -> str:

    try:
        if hasattr(element, 'get_text'):
            text = element.get_text()
            return str(text) if text is not None else ""
        elif hasattr(element, 'text'):
            text = element.text
            return str(text) if text is not None else ""
        return str(element) if element is not None else ""
    except Exception:
        return ""
