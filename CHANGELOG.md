# Changelog

All notable changes to TAKTIK Instagram Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- **1.1.1** (2025-11-26): Multi-target support, intelligent scrolling, automatic popup handling
- **1.1.0**: Core automation features and workflows
