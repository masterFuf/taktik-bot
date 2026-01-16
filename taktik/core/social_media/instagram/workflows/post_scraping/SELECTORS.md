# Instagram Post Scraping - UI Selectors

## Page Post (Feed View)

### Header
- **Username** : `resource-id="com.instagram.android:id/row_feed_photo_profile_name"` → `text` attribute
- **Profile Picture** : `resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"`
- **Secondary Label** (music/location) : `resource-id="com.instagram.android:id/secondary_label"`
- **More Options** : `resource-id="com.instagram.android:id/media_option_button"` `content-desc="More actions for this post"`

### Media Info (from content-desc)
- **Carousel Info** : `resource-id="com.instagram.android:id/carousel_video_media_group"` → `content-desc="Photo 1 of 5 by Manychat, 625 likes, 508 comments"`

### Engagement Buttons
- **Like Button** : `resource-id="com.instagram.android:id/row_feed_button_like"` `content-desc="Like"`
- **Like Count** : Button with numeric `text` (e.g., "625") - sibling after like button
- **Comment Button** : `resource-id="com.instagram.android:id/row_feed_button_comment"` `content-desc="Comment"`
- **Comment Count** : Button with numeric `text` (e.g., "508") - sibling after comment button
- **Share Button** : `resource-id="com.instagram.android:id/row_feed_button_share"` `content-desc="Send Post"`
- **Share Count** : Button with numeric `text` (e.g., "16") - sibling after share area
- **Save Button** : `resource-id="com.instagram.android:id/row_feed_button_save"` `content-desc="Add to Saved"`
- **Save Count** : Button with numeric `text` (e.g., "293")

### Caption
- **Caption Container** : `class="com.instagram.ui.widget.textview.IgTextLayoutView"` → `text` attribute contains full caption with hashtags

---

## Comments Page (Bottom Sheet)

### Header
- **Title** : `resource-id="com.instagram.android:id/title_text_view"` `text="Comments"`
- **Drag Handle** : `resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"`

### Sort Selector
- **Current Sort** : Button with `text="For you"` and `content-desc="For you"` (clickable)
- **Sort Options Menu** :
  - `resource-id="com.instagram.android:id/context_menu_options_list"`
  - Items: `resource-id="com.instagram.android:id/context_menu_item"` with `content-desc="For you"`, `content-desc="Most recent"`, `content-desc="Meta Verified"`

### Comments List
- **List Container** : `resource-id="com.instagram.android:id/sticky_header_list"` (RecyclerView, scrollable)

### Comment Structure
Each comment is a ViewGroup containing:
- **Profile Picture** : ImageView with `content-desc="Go to {username}'s profile"` or `content-desc="View {username}'s story"`
- **Username** : Button with `text="{username}"` (clickable, navigates to profile)
- **Comment Content** : In parent ViewGroup's `content-desc` (e.g., `content-desc="pinksparrowsocial   "` includes comment text)
- **Like Count** : Button with `content-desc="{N} likes. Double-tap to like comment..."` - parse number from content-desc
- **Reply Button** : Button with `text="Reply"` `content-desc="Reply"`
- **See Translation** : Button with `text="See translation"` (optional)

### Reply Thread
- **Author Reply** : Indented comment with smaller profile picture, `content-desc="Go to {author}'s profile"`
- **View More Replies** : ViewGroup with `text="View 1 more reply"` `content-desc="View 1 more reply"` (clickable)
- **Hide Replies** : Button with `text="Hide Replies"` (after expanding)

### Comment Composer
- **Profile Picture** : `resource-id="com.instagram.android:id/comment_composer_left_image_view"`
- **Text Input** : `resource-id="com.instagram.android:id/layout_comment_thread_edittext"` `hint="Join the conversation…"`
- **Sticker Button** : `resource-id="com.instagram.android:id/comment_composer_animated_image_picker_button"`
- **Emoji Bar** : Multiple `resource-id="com.instagram.android:id/item_emoji"` with `content-desc` for each emoji

---

## Likers Page

### Navigation
- Click on like count button to open likers list
- **Back** : `resource-id="com.instagram.android:id/action_bar_button_back"` `content-desc="Back"`

### Likers List
- Similar structure to followers list
- Each liker has: profile picture, username button, follow button

---

## Profile Page (for enrichment)

### Key Elements
- **Username** : `resource-id="com.instagram.android:id/action_bar_title"` or in header
- **Bio** : Look for TextView with biography content
- **Website** : Button with URL text (clickable, external link)
- **Threads Badge** : Look for Threads icon/link
- **Stats** : 
  - Posts count
  - Followers count  
  - Following count
- **Business Category** : If business account, category label visible
- **Verified Badge** : Blue checkmark indicator

---

## Extraction Strategy

### Post Stats
1. Navigate to post
2. Extract from `content-desc` of carousel media: "Photo X of Y by {author}, {likes} likes, {comments} comments"
3. Or extract individual counts from buttons

### Likers
1. Click like count button
2. Scroll through likers list
3. For each liker, click to visit profile and extract info
4. Press back to return

### Comments
1. Click comment button or count
2. Change sort if needed (click "For you" → select "Most recent")
3. Scroll through comments
4. For each comment:
   - Extract username from Button text
   - Extract comment from parent content-desc
   - Extract like count from like button content-desc
   - Check for "View X more reply" and click to expand
5. For each commenter, optionally visit profile for enrichment

### Profile Enrichment
1. Click on username to navigate to profile
2. Extract: bio, website, threads, followers, following, posts, category
3. Press back to return
