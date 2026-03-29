# Selector Cleanup Backup — 2026-03-07
# Based on compat report: instagram v417.0.0.54.77 target_followers (score 27.3%)
#
# This file documents all selectors removed or commented out during cleanup.
# If any workflow breaks, check here first to restore the selector.

## 1. detection.py — liked_button_indicators (removed redundant variants)

Kept:
- '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and @selected="true"]'  ← UNIVERSAL, language-independent
- '//*[contains(@content-desc, "Unlike")]'  ← EN fallback
- '//*[contains(@content-desc, "Ne plus aimer")]'  ← FR fallback

Removed (redundant with the above — same check done via resource-id+content-desc combo):
- '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "déjà")]'
  → "déjà" is part of "J'aime déjà", but @selected=true already catches this state
- '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Ne plus aimer")]'
  → Already covered by generic '//*[contains(@content-desc, "Ne plus aimer")]'
- '//*[contains(@content-desc, "J\'aime déjà")]'
  → Already covered by @selected=true
- '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Unlike")]'
  → Already covered by generic '//*[contains(@content-desc, "Unlike")]'
- '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Liked")]'
  → Never found on v417 (0/48), and "Liked" content-desc doesn't exist on this version
- '//*[@resource-id="com.instagram.android:id/row_feed_button_like"][@selected="true"]'
  → Exact same check as method 1 but different XPath syntax (redundant)

## 2. detection.py — reel_indicators (removed obsolete clips_* IDs)

Kept:
- '//*[contains(@content-desc, "Reel de")]'  ← FR
- '//*[contains(@content-desc, "Reel by")]'  ← EN (21/51 found on v417)

Removed (all 0 found on v417, resource-ids no longer exist):
- '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]'  (0/30)
- '//*[@resource-id="com.instagram.android:id/clips_viewer_video_layout"]'  (0/30)
- '//*[@resource-id="com.instagram.android:id/clips_video_container"]'  (0/30)
- '//*[@resource-id="com.instagram.android:id/clips_video_player"]'  (0/30)

## 3. post.py — reel_indicators (same cleanup)

Kept:
- '//*[contains(@content-desc, "Reel de")]'
- '//*[contains(@content-desc, "Reel by")]'

Removed:
- '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]'
- '//*[@resource-id="com.instagram.android:id/clips_viewer_video_layout"]'
- '//*[@resource-id="com.instagram.android:id/clips_video_container"]'
- '//*[@resource-id="com.instagram.android:id/clips_video_player"]'

## 4. post.py — reel_indicators_like_business (removed obsolete clips_*)

Kept:
- '//*[contains(@content-desc, "Reel")]'
- '//*[contains(@content-desc, "reel")]'

Removed:
- '//*[@resource-id="com.instagram.android:id/clips_video_container"]'
- '//*[@resource-id="com.instagram.android:id/video_container"]'

## 5. detection.py — post_screen_indicators (removed obsolete clips_single_media_component)

Removed:
- '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]'
  → Never found. content-desc "Like"/"Comment" already detects both reels and posts.

## 6. detection.py — followers_list_indicators (removed never-found fallbacks)

Kept:
- '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]'  (15/30 found)

Removed:
- '//*[@resource-id="com.instagram.android:id/unified_follow_list_view_pager"]'  (0/15 found)
- '//android.widget.Button[contains(@text, "mutual")]'  (0/15 found)
- '//android.widget.Button[contains(@text, "followers")]'  (0/12 found)

## 7. followers_list.py — list_indicators (same cleanup)

Kept:
- '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]'

Removed:
- '//*[@resource-id="com.instagram.android:id/unified_follow_list_view_pager"]'
- '//android.widget.Button[contains(@text, "mutual")]'

## 8. feed.py — reel_indicators (removed obsolete clips_*)

Kept:
- '//*[contains(@content-desc, "Reel")]'

Removed:
- '//*[@resource-id="com.instagram.android:id/clips_video_container"]'
- '//*[@resource-id="com.instagram.android:id/clips_viewer_view_pager"]'
- '//*[@resource-id="com.instagram.android:id/clips_audio_attribution_button"]'

---

# Phase 2 — 2026-03-07 (post second run, score 40.3%)

## 9. scroll.py + detection.py — load_more_selectors (consolidated 12 → 5)

Before (12 selectors, many type-specific duplicates):
- "//android.widget.TextView[contains(@text, 'Voir plus')]"
- "//android.widget.Button[contains(@text, 'Voir plus')]"
- "//*[contains(@content-desc, 'Voir plus')]"
- "//android.widget.TextView[contains(@text, 'voir plus')]"
- "//android.widget.TextView[contains(@text, 'See more')]"
- "//android.widget.Button[contains(@text, 'See more')]"
- "//*[contains(@content-desc, 'See more')]"
- "//android.widget.TextView[contains(@text, 'see more')]"
- '//*[@text="Load more" or @text="Show more" or @text="See more"]'
- '//*[contains(@text, "Load") and contains(@text, "more")]'
- '//*[@content-desc="Load more" or @content-desc="Show more"]'
- '//android.widget.Button[contains(@text, "more")]'

After (5 selectors using //* to cover all element types):
- '//*[contains(@text, "Voir plus") or contains(@text, "voir plus")]'
- '//*[contains(@text, "See more") or contains(@text, "see more")]'
- '//*[contains(@content-desc, "Voir plus") or contains(@content-desc, "See more")]'
- '//*[contains(@text, "Load more") or contains(@text, "Show more")]'
- '//*[@content-desc="Load more" or @content-desc="Show more"]'

## 10. scroll.py + detection.py — end_of_list_indicators (consolidated 6-7 → 4)

Before (6-7 selectors with duplicates):
- '//*[@resource-id="com.instagram.android:id/see_all_button"]'
- '//*[@text="See all suggestions"]'  ← redundant with contains below
- '//*[contains(@text, "See all suggestions")]'
- '//*[@text="You\'re all caught up" or @text="No more suggestions"]'  ← redundant
- '//*[contains(@text, "caught up") or contains(@text, "End of list")]'
- '//*[contains(@text, "No more") or contains(@text, "That\'s all")]'
- '//*[contains(@text, "Aucun autre") or contains(@text, "Fin de")]'  (detection.py only)

After (4 selectors):
- '//*[@resource-id="com.instagram.android:id/see_all_button"]'
- '//*[contains(@text, "See all suggestions") or contains(@text, "Voir toutes les suggestions")]'
- '//*[contains(@text, "caught up") or contains(@text, "No more suggestions") or contains(@text, "End of list")]'
- '//*[contains(@text, "No more") or contains(@text, "That\'s all") or contains(@text, "Aucun autre")]'

## 11. extractors.py — is_reel hint optimization (code change, not selector removal)

Problem: reel_like_count_selector (0/31) and reel_comment_count_selector (0/31) always tried first,
even on regular posts where they can never be found. ~62 wasted XPath calls per session.

Fix: Added `is_reel` parameter to `extract_likes_count_from_ui()` and `extract_comments_count_from_ui()`.
When caller passes `is_reel=False`, the broken reel-specific selector is skipped entirely.

Updated callers:
- orchestration.py: _like_posts_on_profile loop (detect reel first, pass to extractors)
- hashtag/workflow.py: post metadata extraction
- hashtag/mixins/post_finder.py: _extract_post_metadata
- feed/post_actions.py: _extract_post_metadata
- post_url/workflow.py: post metadata extraction

Expected savings: ~30s per target_followers session (62 calls × ~475ms avg)

---

## NOT REMOVED (legitimate even if 0 found on target_followers):
- like_count / comment_count → used for post signature deduplication + other workflows
- Load more / See more / End of list → consolidated but kept (scroll guard)
- Popup detectors (before following, Account based in, etc.) → safety, very low cost
- Suggestions section indicators → necessary to avoid interacting with suggestions
- already_liked_indicators in feed.py → different code path than detection.py, used in feed workflow
- Unlike detection → needed for liked_button_indicators fallback (26 calls normal behavior)
