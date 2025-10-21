<div align="center">
  <img src="logo/logo.png" alt="Taktik Logo" width="600"/>
</div>

<div align="center">
  <h3><a href="https://taktik-bot.com/">🌐 taktik-bot.com</a></h3>
</div>

<div align="right">
  <strong>🇬🇧 English</strong> | <a href="./README.fr.md">🇫🇷 Français</a>
</div>

# 🎯 Taktik - Instagram Automation Framework

**Version 1.0.0** | Advanced automation with human-like behavior and anti-detection mechanisms.

> Professional Instagram automation framework with 3 powerful workflows, smart filtering, and comprehensive analytics.

---

## ✨ Key Features

### 🚀 3 Automation Workflows

#### 1. **Follower Workflow** - Target Your Audience
Interact with followers of specific accounts to grow your community.

```bash
taktik
# Select: Interact with followers
# Enter target username: @competitor
# Configure: likes, comments, follows
```

**Features:**
- ✅ Extract followers from any public account
- ✅ Smart filtering (followers count, business accounts, verified)
- ✅ Like posts (1-3 per profile)
- ✅ Post comments with templates or custom messages
- ✅ Follow users with configurable probability
- ✅ Watch and like stories

#### 2. **Hashtag Workflow** - Discover New Content
Engage with posts from specific hashtags to increase visibility.

```bash
taktik
# Select: Interact with hashtag posts
# Enter hashtag: fitness
# Configure: max interactions, filters
```

**Features:**
- ✅ Explore posts by hashtag
- ✅ Like posts with smart probability
- ✅ Comment on engaging content (10% default)
- ✅ Profile filtering (min/max followers)
- ✅ Skip already processed accounts

#### 3. **Post URL Workflow** - Engage with Specific Content
Interact with users who liked a specific post or reel.

```bash
taktik
# Select: Interact with post likers
# Enter post URL: https://instagram.com/p/ABC123
# Configure: interactions, comments
```

**Features:**
- ✅ Extract likers from any public post/reel
- ✅ Navigate to each liker's profile
- ✅ Like their content
- ✅ Comment with personalized messages (5% default)
- ✅ Optional follow

---

## 🎨 Interaction Capabilities

### Content Actions
- ✅ **Like Posts** - Standard posts, carousels, and reels
- ✅ **Comment** - Template-based or custom messages with emojis
- ✅ **Follow/Unfollow** - Smart following with configurable limits
- ✅ **Watch Stories** - View and like stories

### Smart Features
- 🧠 **Human-like Behavior** - Random delays, natural scrolling
- 🎯 **Advanced Filtering** - Followers count, account type, language
- 📊 **Session Analytics** - Real-time stats and detailed reports
- 🔒 **Anti-Detection** - Randomized patterns, quota management
- 💾 **Database Tracking** - Never interact with the same account twice

---

## 💬 Comment System

### Template Categories
```python
# Generic
"Amazing! 🔥", "Love this! ❤️", "So cool! 😎"

# Engagement
"Great content! 👏", "Keep it up! 💪"

# Short
"🔥🔥🔥", "❤️", "😍"
```

### Custom Comments
```bash
# Via CLI
taktik
# Enter custom comments when prompted
# Or use default templates
```

### Configuration
- **Max comments per profile:** 1 (default)
- **Comment probability:** Configurable per workflow
- **Auto-close popup:** Smart swipe detection
- **Quota tracking:** Integrated with license system

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Android device/emulator** with USB debugging enabled
- **ADB** installed and configured
- **Instagram app** installed on device

### Installation

```bash
# Clone repository
git clone https://github.com/your-username/taktik-bot.git
cd taktik-bot

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -e .
```

### First Run

```bash
# Launch CLI
python -m taktik

# Follow the interactive prompts:
# 1. Select workflow (Followers/Hashtag/Post URL)
# 2. Enter target (username/hashtag/URL)
# 3. Configure interactions
# 4. Start automation
```

---

## ⚙️ Configuration

### Workflow Settings

**Follower Workflow:**
```json
{
  "max_interactions_per_session": 5,
  "like_probability": 1.0,
  "comment_probability": 1.0,
  "follow_probability": 0.05,
  "max_likes_per_profile": 3,
  "max_comments_per_profile": 1
}
```

**Hashtag Workflow:**
```json
{
  "max_interactions": 10,
  "like_probability": 0.8,
  "comment_probability": 0.1,
  "min_followers": 100,
  "max_followers": 50000
}
```

**Post URL Workflow:**
```json
{
  "max_likers_to_extract": 30,
  "like_probability": 0.7,
  "comment_probability": 0.05,
  "follow_probability": 0.1
}
```

### Filters

```json
{
  "filters": {
    "min_followers": 100,
    "max_followers": 10000,
    "skip_business_accounts": false,
    "skip_verified_accounts": false,
    "skip_private_accounts": true
  }
}
```

---

## 📊 Session Analytics

### Real-time Stats
```
📈 Session Progress:
├─ Profiles visited: 15/20
├─ Likes performed: 32
├─ Comments posted: 8
├─ Follows performed: 2
└─ Success rate: 94.2%
```

### Database Tracking
- ✅ All interactions saved to SQLite database
- ✅ Duplicate prevention (never interact twice)
- ✅ Session history and analytics
- ✅ Export capabilities

---

## 🛠️ Technical Architecture

### Modular Design
```
taktik/
├── actions/
│   ├── atomic/          # Low-level UI actions
│   ├── business/        # High-level workflows
│   └── core/            # Base classes
├── workflows/           # 3 main workflows
├── ui/                  # Selectors & extractors
└── database/            # SQLite integration
```

### Key Technologies
- **uiautomator2** - Android UI automation
- **ADB** - Device communication
- **SQLite** - Local database
- **Loguru** - Advanced logging

---

## 📚 Documentation

For complete documentation, visit **[taktik-bot.com/en/docs](https://taktik-bot.com/en/docs)**

---

## 🔒 Legal Notice

**Educational purposes only.** This project is for learning automation concepts. Users must comply with Instagram's Terms of Service. The developers are not responsible for misuse.

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

<div align="center">
  <strong>Made with ❤️ for automation enthusiasts</strong>
</div>
