# Changelog

All notable changes to TAKTIK Instagram Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.6] - 2025-12-10

### Added
- **DM Bridge**: Unified Python bridge for reading and sending Instagram DMs
  - Read conversations with full message history (sent + received)
  - Send messages with human-like typing simulation
  - Emoji and special character support
  - Integration with TAKTIK Desktop app

- **Media Capture Service**: Intercept Instagram CDN media using mitmproxy
  - Capture stories, reels, and posts media URLs
  - Real-time media interception during browsing
  - Export captured media for analysis

- **Frida SSL Bypass**: Certificate pinning bypass for Instagram Android
  - `frida_ssl_bypass.js` script for SSL unpinning
  - Works with mitmproxy for HTTPS traffic inspection
  - Compatible with Instagram app versions 300+

- **Enhanced Followers Tracking**: Insomniac-style position verification
  - Loop detection to prevent infinite scrolling
  - Position-based duplicate detection
  - Improved extraction reliability on large accounts

- **Multi-Target Diagnostics**: Better debugging for follower extraction
  - Detailed logging of extraction progress
  - Target switching diagnostics
  - Performance metrics per target

### Improved
- **Target Workflow**: More reliable follower extraction with better termination conditions
- **DM Reading**: Now captures both sent and received messages for full conversation context
- **Human-like Behavior**: Optimized typing delays (faster but still natural)

### Technical
- Unified `dm_bridge.py` replaces `dm_bridge_desktop.py` and `dm_send_bridge.py`
- New `media_capture/` service module with mitmproxy integration
- Frida scripts in `frida/` directory for SSL bypass

---

## [1.1.5] - 2025-12-05

### Added
- **Post URL Scraping Workflow**: Extract and interact with users who liked specific posts
- Various bug fixes and stability improvements

---

## [1.1.3] - 2025-12-02

### Refactored
- **Centralized number parsing**: All number parsing logic now uses `parse_number_from_text` from `extractors.py`
  - Eliminated code duplication in `like.py`, `utils.py`, and `profile.py`
  - Fixed follower count parsing for large accounts with space before K/M suffix (e.g., "166 K" → 166,000)
  - All parsing improvements now apply automatically across the entire codebase

- **Centralized problematic page selectors**: Created `ProblematicPageSelectors` class in `selectors.py`
  - Moved hardcoded selectors from `problematic_page.py` to centralized location
  - Improved maintainability and consistency of UI selectors
  - All problematic page detection and closing now uses centralized selectors

### Fixed
- **Follower count parsing for large accounts**: Fixed parsing of follower counts with space before K/M suffix (e.g., "166 K" for 166,000 followers)
  - Instagram displays large numbers with a space before the suffix on some devices/locales
  - Previously, "166 K" was incorrectly parsed as 166 instead of 166,000
  - This caused premature termination of follower scraping on accounts with thousands of followers

---

## [1.1.1] - 2025-11-26

### Added
- **Multi-target follower extraction**: Support for extracting followers from multiple target profiles in a single session
  - CLI now accepts comma-separated usernames (e.g., `user1,user2,user3`)
  - Automatic switching between targets when extraction limits are reached
  - Accumulated follower list across all targets for interaction
  
- **Intelligent end-of-list detection**: Prevents infinite scrolling on profiles with limited followers
  - Uses profile's total follower count to detect when ~95% of followers have been seen
  - Automatically switches to next target when current profile is exhausted
  - Significantly reduces wasted scrolling time
  
- **Automatic popup detection and closure**: Enhanced problematic page detector
  - New pattern for "Mute notifications" popup (`mute_notifications_popup`)
  - Improved `swipe_down_handle` method with dynamic element targeting
  - Resolution-agnostic implementation using element bounds instead of fixed coordinates
  - Automatic detection and closure after profile navigation

### Improved
- **Navigation reliability**: Integrated problematic page detector into navigation flow
  - Automatic popup closure after each profile navigation
  - Reduced navigation failures due to blocking popups
  
- **Follower extraction efficiency**: 
  - Smarter extraction limits based on profile follower count
  - Better handling of profiles with few followers
  - Reduced unnecessary scrolling attempts

### Fixed
- Infinite scrolling issue on profiles with limited followers
- Navigation failures caused by "Mute notifications" popup
- Follower extraction stopping prematurely when switching targets

### Technical Details
- Enhanced `ProblematicPageDetector` with resolution-independent element targeting
- Modified `NavigationActions` to include automatic popup detection
- Updated `interact_with_target_followers` to support multi-target workflow
- Improved `_extract_followers_with_scroll` with intelligent termination conditions

---

## [1.1.0] - Previous Release

### Features
- Core Instagram automation functionality
- Follower/following interaction workflows
- Hashtag-based targeting
- Post URL interaction
- Session management and limits
- Database integration for tracking processed profiles
- License system integration

---

## Version History

- **1.1.6** (2025-12-10): DM Bridge, Media Capture, Frida SSL Bypass, Enhanced Tracking
- **1.1.5** (2025-12-05): Post URL scraping workflow
- **1.1.3** (2025-12-02): Centralized number parsing and UI selectors
- **1.1.2** (2025-12-02): Fix follower count parsing for large accounts (K/M with space)
- **1.1.1** (2025-11-26): Multi-target support, intelligent scrolling, automatic popup handling
- **1.1.0**: Core automation features and workflows
