# Baseline Functionality - bot.py v1.0

**Date:** 2025-10-14
**Source:** bot.py.backup (commit 7c43bef)
**Status:** ✓ Syntax validated

---

## Core Features

### 1. User Commands

**`/start`**
- Displays welcome message
- Shows main menu with buttons:
  - 📰 Получить новости (Get News)
  - 📁 Управление папками (Manage Folders)
  - ⚙️ Настройки (Settings)
  - 📢 Заполнить форму владельца канала (Channel Owner Form)

**`/manage`**
- Folder management interface
- Shows current active folder
- Displays all folders with channel counts
- Buttons for:
  - Create folder
  - Rename folder
  - Delete folder
  - Switch active folder
  - Add channel
  - Remove channel
  - List channels

**`/news`**
- Scrapes posts from channels in active folder
- Generates AI embeddings using Gemini (text-embedding-004)
- Clusters similar posts using DBSCAN
- Generates summaries using Gemini (gemini-flash-lite-latest)
- Sends formatted summaries to user
- Rate limited: 5 requests per day per user
- Default: last 24 hours, 10 summaries max

---

## Technical Features

### Data Storage
- `user_data.json` - User subscriptions and settings
- `channel_feed.json` - Channel owner forms
- Folder-based channel organization
- In-memory caching for performance
- Automatic backups with rotation (max 20, 7-day retention)

### AI Integration
- **Gemini API**
  - Embeddings: text-embedding-004
  - Generation: gemini-flash-lite-latest
  - Concurrent limit: 4000 requests
  - Retry logic with exponential backoff

### Scraping
- Public Telegram channels via `https://t.me/s/{channel}`
- BeautifulSoup + httpx
- Shared HTTP client with connection pooling
- Max 20 posts per channel

### Clustering
- DBSCAN algorithm (sklearn)
- Similarity threshold: 0.9
- Groups duplicate/similar news stories

### Performance Optimizations
- Button instant feedback (⏳ messages)
- Backup debouncing (max 1/minute)
- Async file I/O (aiofiles)
- Parallel scraping and summarization
- Cache-based channel counting

---

## User Settings

- **Time limit:** 1-720 hours (default: 24)
- **Max summaries:** 1-30 posts (default: 10)
- **Rate limiting:** 5 /news requests per day

---

## Constraints

- Max 10 channels per user (across all folders)
- Russian language only
- Public channels only
- Channel names must start with `@`
- Posts < 50 chars filtered out

---

## Known Behavior

### File Structure
```
user_data.json - User data with folders
channel_feed.json - Channel owner forms
bot.log - Application logs
bot_user.log - User interaction logs
backups/user_data/ - Timestamped backups
```

### Migration
- Automatic migration from old format (single channel list) to folders
- Default folder: "Папка1"

### Validation
- User data validation on load
- Auto-restore from backup on corruption
- Channel name validation (@-prefix required)

---

## Dependencies

```
python-telegram-bot==21.6
google-generativeai==0.8.3
scikit-learn==1.5.2
httpx
beautifulsoup4
aiofiles
python-dotenv
numpy
```

---

## Environment Variables Required

```
TELEGRAM_BOT_API - Bot token
GEMINI_API - Gemini API key
ADMIN_CHAT_ID - (Optional) Admin chat ID for forms
```

---

## Expected Test Results (Phase 7)

When testing in Phase 7, the following should work:

1. ✓ `/start` displays main menu
2. ✓ `/manage` shows folder management
3. ✓ Creating folders (up to user-defined limit)
4. ✓ Renaming folders
5. ✓ Deleting folders
6. ✓ Switching active folder
7. ✓ Adding channels (@channel format)
8. ✓ Removing channels
9. ✓ Listing channels in folder
10. ✓ `/news` command scrapes, clusters, summarizes
11. ✓ Rate limiting enforces 5/day limit
12. ✓ Settings adjust time limit and max posts
13. ✓ Button responses are instant (⏳ feedback)
14. ✓ Backup debouncing prevents spam
15. ✓ Channel owner forms submit to admin
16. ✓ User data persists across restarts
17. ✓ Migration from old format works
18. ✓ Validation catches corrupted data

---

## Validation Status

- [x] bot.py.backup compiles successfully
- [x] bot.py (current) compiles successfully
- [ ] Full integration test (deferred to Phase 7)
- [ ] API keys configured (not tested)
- [ ] Bot actually runs (deferred to Phase 7)

---

**Note:** Since we have valid backups and syntax is correct, we can safely proceed with Phase 4 refactoring. Full functional testing will occur in Phase 7 (Integration & Testing).
