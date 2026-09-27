<div align="center">
  <h1>Social Media Automation Platform</h1>

  <p><strong>Instagram, TikTok, YouTube, Threads and Gmail automation on real Android devices. Likes, follows, DMs, scraping, publishing, hashtag targeting, AI comments and profile qualification. Built with Python, uiautomator2 and ADB.</strong></p>

  [![GitHub stars](https://img.shields.io/github/stars/masterFuf/taktik-bot?style=social)](https://github.com/masterFuf/taktik-bot/stargazers)
  [![GitHub forks](https://img.shields.io/github/forks/masterFuf/taktik-bot?style=social)](https://github.com/masterFuf/taktik-bot/network/members)
  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
  [![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289da?logo=discord&logoColor=white)](https://discord.com/invite/6tTBRTMhBj)

  <br/>

  <a href="https://taktik-bot.com/">Website</a> •
  <a href="https://taktik-bot.com/en/docs">Documentation</a> •
  <a href="https://www.youtube.com/@taktik-bot">YouTube</a> •
  <a href="https://discord.com/invite/6tTBRTMhBj">Discord</a> •
  <a href="./README.fr.md">Français</a>
</div>

---

<div align="center">

  [![TAKTIK Demo](https://img.youtube.com/vi/mFh0iv3Hzck/maxresdefault.jpg)](https://www.youtube.com/watch?v=mFh0iv3Hzck)

  **Desktop app access details are available on the website**

  <a href="https://taktik-bot.com/en">**See current access details** →</a>

  <br/><br/>

</div>

---

## What is TAKTIK?

**TAKTIK** automates Instagram, TikTok, YouTube, Threads and Gmail on real Android phones. It has two
halves:

- **The engine (this repository, GPLv3).** A Python bot that drives the phone through ADB and
  uiautomator2, with a command line (`taktik`). Every workflow in the list below runs from the
  command line, with no licence limit.
- **The desktop app (commercial).** A graphical interface that launches the same engine, and adds
  what is listed under [What needs the desktop app](#what-needs-the-desktop-app).

The command line and the app run the same workflows with the same settings (changing the IP before
a run excepted, which is the app's): the app launches the engine's own launchers, it does not have a
second copy of them.

---

## Features

Every row runs from the command line (`taktik workflows run <id>`) unless it says otherwise.
`taktik workflows list` prints every id.

### Instagram

| Feature | Workflow ids / command |
|---------|------------------------|
| **Followers or following of target accounts** | `instagram.automation.target_followers`, `target_following` |
| **A list of target profiles** | `instagram.automation.target_profiles` |
| **Hashtags** | `instagram.automation.hashtags` |
| **Likers of a post** | `instagram.automation.post_url` |
| **Home feed** | `instagram.automation.feed` |
| **Unfollow** | `instagram.automation.unfollow` |
| **Sync of the following and followers lists** | `instagram.automation.sync_following`, `sync_followers_following` |
| **Scraping**: followers or following of an account, a hashtag, the likers and commenters of a post, a list of usernames, the posts of accounts | `instagram.scraping.target`, `hashtag`, `post_url`, `usernames`, `profile_posts` |
| **Cold DM**: a list of accounts, fixed messages or one message written by AI per recipient | `instagram.engagement.coldDm` |
| **DM inbox**: read the inbox or the requests folder, reply in a conversation | `instagram.engagement.dm_read`, `dm_send` |
| **Notifications**: scan the activity feed, accept follow requests, like, follow back, reply, batches | `instagram.engagement.notifications` |
| **Story relay**: re-share a source account's stories | `instagram.task.story_relay` |
| **Publishing**: post, carousel, reel, story | `taktik publish post\|carousel\|reel\|story` |
| **Accounts**: login, signup, logout, switch account, list accounts, change the app language | `instagram.account.*` |

> Details: [Instagram automation](https://taktik-bot.com/en/features/instagram-automation) and
> [Instagram AI DMs](https://taktik-bot.com/en/features/instagram-ai-dm) on the website.

### TikTok

| Feature | Workflow ids |
|---------|--------------|
| **For You feed** | `tiktok.automation.for_you` |
| **Hashtags, account search** | `tiktok.automation.hashtag`, `search` |
| **Followers of target accounts, a list of target profiles** | `tiktok.automation.followers`, `target_profiles` |
| **Commenters of a video** | `tiktok.automation.post_url` |
| **Sync of the following and followers lists** | `tiktok.automation.sync_lists`, `sync_following`, `sync_followers` |
| **DM**: read and send | `tiktok.automation.dm_read`, `dm_send` |
| **Inbox**: new followers (with an AI welcome pass), unanswered conversations, message requests, activity | `tiktok.automation.new_followers`, `dm_unreplied`, `dm_requests`, `dm_activity` |
| **Notifications** | `tiktok.automation.notifications` |
| **Cold DM**: fixed messages or one written by AI per recipient | `tiktok.standalone.tiktok_dm_outreach` |
| **Unfollow** | `tiktok.standalone.tiktok_unfollow` |
| **Scraping**: followers of an account, a hashtag, the commenters of a video, a sound, the posts of accounts | `tiktok.standalone.tiktok_scraping` |
| **Publishing**: a video, or a text post | `tiktok.standalone.upload_post` |
| **Accounts**: login, signup, logout, change the app language | `tiktok.account.*` |

> Details: [TikTok automation](https://taktik-bot.com/en/features/tiktok-automation) on the website.

### YouTube, Threads, Gmail

| Feature | Workflow ids |
|---------|--------------|
| **YouTube**: login, logout; upload a Short or a video with its title, description and visibility | `youtube.account.login`, `logout`, `youtube.publish.upload_post` |
| **Threads**: follow accounts found by a search, engage with the feed | `threads.automation.follow`, `feed` |
| **Gmail**: add and remove an account, read the latest code, list the accounts on the phone | `gmail.account.login`, `logout`, `read_otp`, `scan_accounts` |

### AI in the engine

These run from the command line with your own [OpenRouter](https://openrouter.ai) key (asked for
at launch when a run uses AI; a manual run needs no key).

| Feature | Where |
|---------|-------|
| **AI comments**: a comment written for the post it goes under | the `ai` block of an automation run |
| **Profile qualification**: a vision model reads a visited profile, gives its niche and a relevance score | the `ai` block of an automation or scraping run |
| **Cold DM written by AI**, one message per recipient | `messageMode: "ai"` (Instagram and TikTok) |
| **TikTok welcome pass**: new followers qualified, the relevant ones followed back | `tiktok.automation.new_followers` with `ai.newFollowers` |
| **Taktik Agent**: an autonomous Instagram session where a vision model decides each like, comment, profile visit and follow | `taktik agent run` |

---

## What needs the desktop app

| Feature | Without the app |
|---------|-----------------|
| **Graphical interface**, live panels, session history, analytics dashboards | The command line prints logs and the final result. |
| **Scheduler** (visual workflow builder, day and period plans, AI-generated plans), **autonomous campaigns** | A cron job can chain CLI commands. |
| **Change the IP before a run** (mobile data or airplane mode), network pools, one phone at a time on a shared connection | The command line never changes the IP. |
| **Warmup curve**: caps computed from the account's age and intensity (`warmupPolicy`) | You may write `warmupPolicy` in a run's JSON yourself; the engine applies those caps. |
| **Account persona**: the operated account analysed (profile, posts, writing style) to guide what the AI writes (`ai.accountProfile`) | You may write `ai.accountProfile` yourself. |
| **Niche taxonomy** (categories, sub-niches, aliases) used by AI qualification (`ai.nicheTaxonomy`) | Qualification is free-form, or you write `ai.nicheTaxonomy` yourself. |
| **Decision mode**: the app plans the actions on each profile | The engine refuses to act without the app's plan. |
| **AI replies to DMs**, AI-written welcome messages on Instagram, AI replies to comments | Replies are typed at the terminal. |
| **AI content for publishing**: images, captions, hashtags | Publishing takes your own media and text. |
| **Target Search** (explore the local database), world map, audience insights, CSV/XLSX export | The database is a local SQLite file you can query yourself. |
| **Cartography Lab** (test bench of atomic actions), screen mirroring, device wall, device groups | - |
| **Multi-PC sync** | - |

The number of phones the app drives depends on its subscription. The engine has no such limit: run
one command per phone.

> Full catalog: [all features](https://taktik-bot.com/en/features), including the
> [scheduler](https://taktik-bot.com/en/features/app-scheduler), the
> [analytics](https://taktik-bot.com/en/features/app-sessions-analytics) and
> [target search](https://taktik-bot.com/en/features/app-target-search).

---

## Quick start

### Desktop app

1. **Sign up** at [taktik-bot.com](https://taktik-bot.com/en/pricing)
2. **Download** the desktop app for Windows
3. **Connect** your Android device via ADB
4. **Launch** a workflow from the interface

### Command line

```bash
git clone https://github.com/masterFuf/taktik-bot.git
cd taktik-bot
pip install -r requirements.txt

python -m taktik                         # interactive menu
python -m taktik workflows list          # every workflow id
python -m taktik workflows run instagram.automation.feed --dry-run
```

At startup the command line says which database it writes to. Without `TAKTIK_DB_PATH` it is the
desktop app's own database (`%APPDATA%/taktik-desktop/taktik-data.db` on Windows); set
`TAKTIK_DB_PATH` to use another file.

The command line reference (parameters, AI key, one example per workflow) is in the documentation.

### Requirements

- An **Android** device reachable by **ADB**
- **Instagram** and/or **TikTok** installed, in a version listed in [COMPATIBILITY.md](COMPATIBILITY.md)
- **Python 3.10+** for the command line

### Supported app versions and languages

The Instagram and TikTok versions TAKTIK supports, per CPU architecture, with a link to download
the original APK of each, are listed in **[COMPATIBILITY.md](COMPATIBILITY.md)**. That file is
generated from the bot's own selector data (`python scripts/audit_compatibility_file.py --write`)
and checked by the same script, so it always matches the code.

The apps may be in **English or French**: the bot reads the app's language at the start of a run
and uses the matching labels. The command line itself speaks English and French (`--lang en|fr`).

### Development tests

```bash
python -m pytest
```

The tests live under `tests/unit` (database, command line, the bot/app contract, one folder per
platform). Local POC and device smoke scripts belong under `tests/poc/` and `tests/smoke/`; they are
ignored by git because they may contain dumps, screenshots or device-specific experiments.

---

## Commercial access

The Python engine in this repository is open source.

The desktop application, premium tooling and commercial access terms evolve separately from the codebase. For current availability, onboarding and commercial details, refer to the official website:

- [taktik-bot.com](https://taktik-bot.com/en)
- [Contact us](https://taktik-bot.com/en/contact)

---

## Documentation

Full documentation available at **[taktik-bot.com/en/docs](https://taktik-bot.com/en/docs)**.

---

## Contributing

Issues are welcome: bug reports, a version of Instagram or TikTok that breaks a workflow, questions.
Pull requests from outside the project are not accepted for now. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Community and support

- **[Discord Server](https://discord.com/invite/6tTBRTMhBj)**: help and tips
- **[GitHub Issues](https://github.com/masterFuf/taktik-bot/issues)**: bugs and feature requests
- **[Contact Form](https://taktik-bot.com/en/contact)**: business inquiries

---

## Keywords

`instagram bot` `instagram automation` `tiktok bot` `tiktok automation` `social media automation` `instagram growth` `instagram scraper` `instagram dm bot` `cold dm` `instagram marketing` `social media manager` `instagram followers` `engagement bot` `python instagram bot` `open source bot`

---

## License

This project is licensed under **GNU General Public License v3.0**: see [LICENSE](LICENSE).

One data file is under another licence: `taktik/core/app/ai/data/agreement_fr.tsv` derives from
Lexique 3.83 and is distributed under CC BY-SA 4.0. See [NOTICE](NOTICE).

The desktop application is a commercial product with separate access terms published on the official website.

---

## Disclaimer

**For educational and research purposes only.**

This software is provided as-is. Users must comply with Instagram's and TikTok's Terms of Service. The developers are not responsible for any account restrictions or bans. Use responsibly and at your own risk.

---

<div align="center">

  **Star this repo to support the project!**

  <br/>

  Made with care by <a href="https://github.com/masterFuf">masterFuf</a>

  <br/>

  <a href="https://taktik-bot.com">taktik-bot.com</a> • <a href="https://discord.com/invite/6tTBRTMhBj">Discord</a>

</div>
