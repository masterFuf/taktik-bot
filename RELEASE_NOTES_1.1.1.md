# TAKTIK Bot - Release Notes v1.1.1

**Release Date**: November 26, 2025

## 🎯 What's New

### Multi-Target Follower Extraction
Extract followers from multiple Instagram profiles in a single session! Simply enter comma-separated usernames when prompted:
```
Target username: user1,user2,user3
```

The bot will:
- Extract followers from each target sequentially
- Accumulate all followers into a single list
- Automatically switch to the next target when needed
- Continue until the interaction limit is reached

### Intelligent Scrolling
No more infinite scrolling on profiles with few followers! The bot now:
- Detects the total follower count of each profile
- Stops scrolling when ~95% of followers have been seen
- Automatically switches to the next target
- Saves time and reduces unnecessary API calls

### Automatic Popup Handling
The bot now automatically detects and closes blocking popups:
- "Mute notifications" popup
- Other Instagram bottom sheets
- Resolution-independent implementation (works on all screen sizes)
- Seamless navigation without manual intervention

## 📊 Performance Improvements

- **Faster follower extraction**: Reduced scrolling time by up to 60% on small profiles
- **Better navigation reliability**: Automatic popup closure prevents navigation failures
- **Smarter resource usage**: No wasted time on exhausted follower lists

## 🔧 Technical Highlights

- Resolution-agnostic popup detection using dynamic element bounds
- Enhanced `ProblematicPageDetector` with improved swipe handling
- Integrated popup detection into navigation workflow
- Multi-target support in CLI and workflow runner

## 📈 Session Statistics (Example)

From a real test session:
```
⏱️  Session duration: 02:33:05
❤️  Likes performed: 150 (58.9/h)
👥 Follows performed: 18 (7.1/h)
👤 Profiles visited: 111 (43.6/h)
🚫 Profiles filtered: 82
⏭️  Profiles skipped: 38
```

## 🚀 Upgrade Instructions

1. Pull the latest changes:
   ```bash
   git pull origin main
   ```

2. Reinstall the package:
   ```bash
   pip install -e .
   ```

3. Run the bot as usual:
   ```bash
   taktik-instagram
   ```

## 🐛 Bug Fixes

- Fixed infinite scrolling on profiles with limited followers
- Fixed navigation failures caused by "Mute notifications" popup
- Fixed follower extraction stopping prematurely when switching targets

## 📝 Notes

- All popup handling is automatic and requires no configuration
- Multi-target feature is backward compatible (single target still works)
- The bot adapts to all screen resolutions automatically

---

**Full Changelog**: See [CHANGELOG.md](CHANGELOG.md) for detailed changes.
