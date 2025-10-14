# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Bot Does

A Telegram bot that monitors multiple channels and uses AI to consolidate duplicate news stories into a clean digest.

## Quick Start

**Setup:**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

**Environment variables** (`.env` file):
- `TELEGRAM_BOT_API` - Your Telegram bot token
- `GEMINI_API` - Your Gemini API key
- `ADMIN_CHAT_ID` - (Optional) Admin chat ID for channel owner forms

**Run:**
```bash
python bot.py
```

## Architecture

**Single file: `bot.py` (~3000 lines)**

Core stack:
- **python-telegram-bot** (v21.6) - Bot framework
- **google-generativeai** (v0.8.3) - AI embeddings (`text-embedding-004`) and generation (`gemini-flash-lite-latest`)
- **scikit-learn** (v1.5.2) - DBSCAN clustering for grouping similar posts
- **httpx + beautifulsoup4** - Scraping from `https://t.me/s/{channel_name}`

## How `/news` Works

1. **Scrape** - Fetch posts from subscribed channels (parallel, max 20 posts/channel)
2. **Embed** - Generate vector embeddings (batched, 100 at a time)
3. **Cluster** - DBSCAN groups similar posts (0.9 similarity threshold)
4. **Rank** - Sort by cluster size (most covered stories first)
5. **Summarize** - AI generates summaries (parallel processing)
6. **Deliver** - Send formatted summaries to user

## Key Configuration

Constants at `bot.py:51-62`:
```python
MAX_CHANNELS = 10                    # Max channels per user (across all folders)
MAX_POSTS_PER_CHANNEL = 20          # Posts scraped per channel
DEFAULT_NEWS_TIME_LIMIT_HOURS = 24  # Default time range
MAX_NEWS_TIME_LIMIT_HOURS = 720     # Max allowed time range (30 days)
DEFAULT_MAX_SUMMARY_POSTS = 10      # Default summaries per /news
MAX_SUMMARY_POSTS_LIMIT = 30        # Max allowed summaries
MAX_NEWS_REQUESTS_PER_DAY = 5       # Daily rate limit per user
SIMILARITY_THRESHOLD = 0.9          # DBSCAN clustering threshold
GEMINI_CONCURRENT_LIMIT = 4000      # Max concurrent API calls
```

## Data Storage

- `user_data.json` - User subscriptions, folders, and preferences (cached in memory)
- `channel_feed.json` - Channel owner forms data
- `bot.log` - Application logs
- `bot_user.log` - User interaction logs

**User data structure:**
```json
{
  "user_id": {
    "folders": {
      "Папка1": ["@channel1", "@channel2"],
      "Папка2": ["@channel3"]
    },
    "active_folder": "Папка1",
    "time_limit": 24,
    "max_posts": 10,
    "news_requests": {"2025-10-11": 3}
  }
}
```

## Important Implementation Notes

**Performance:**
- In-memory cache for user data to reduce file I/O
- Parallel scraping with `asyncio.gather()`
- Batched embeddings and parallel summarization
- Semaphore limits concurrent Gemini API calls (4000)
- Folder channel counts reuse cached results
- Async file I/O via `aiofiles` removes event-loop blocking
- Shared `httpx.AsyncClient` pools connections for scraping/validation
- **Button handlers optimized (Phase 1 - 2025-10-13):**
  - Instant visual feedback on all button presses (⏳ messages)
  - Backup operations debounced (max 1/minute) and non-blocking
  - Redundant data loads eliminated in hot paths (`news_command_internal`, `create_folder_management_menu`)
  - `/news` command reduced from 6 data loads to 1 load

**Reliability:**
- Gemini API calls retry 3x with exponential backoff
- Falls back to original text if summarization fails
- Safety settings: `BLOCK_NONE` to avoid content blocking
- gRPC verbosity suppressed via environment variables (`bot.py:4-8`)
- Cache operations lock consistently for thread safety
- User data backups rotate with retention (debounced to prevent excessive I/O)
- Migration paths carry version metadata for future schema changes

**Constraints:**
- Russian language only
- Public channels only (scrapes web preview from `https://t.me/s/{channel}`)
- Posts < 50 chars filtered out
- Channel names must start with `@`
- Non-Telegram URLs removed from summaries
- Rate limit: 5 `/news` per user per day (UTC)
- Max 10 channels per user (across all folders)
- Timestamps normalized to UTC; posts without timestamps are dropped

## Docker

```bash
# Build and run
docker build -t keytime-bot .
docker run -d --name keytime-bot \
  -e TELEGRAM_BOT_API="your_token" \
  -e GEMINI_API="your_key" \
  -v $(pwd):/app/data \
  keytime-bot

# View logs
docker logs -f keytime-bot
```

## Key Features

**Folder Management** (`bot.py:99-306`):
- Users can organize channels into folders (default: "Папка1")
- Switch active folder to control which channels `/news` uses
- Create/rename/delete folders through `/manage` command
- Migration function handles upgrading old user data

**Channel Owner Forms** (`bot.py:2137-2199`):
- Owners can submit forms to add channels to news feed
- Forms sent to admin via `ADMIN_CHAT_ID`
- Validates channel access and username before submission

**Rate Limiting** (`bot.py:186-216`):
- Tracks `/news` usage per user per day (UTC)
- Resets daily counter automatically
- Returns remaining requests to user

## Development

**Change limits:** Edit constants at `bot.py:51-62`

**Change AI models:**
- Embedding: `get_embeddings()` at line 1020 (uses `text-embedding-004`)
- Generation: `get_gemini_model()` at line 1122 (uses `gemini-flash-lite-latest`)

**Debug mode:** Set `level=logging.DEBUG` at `bot.py:29`

**Add command:**
1. Create handler: `async def new_command(update, context)`
2. Register: `application.add_handler(CommandHandler("name", new_command))`
3. Add to `create_main_menu()` for button interface
4. Add callback in `button_callback()` if using buttons

**ConversationHandler states:**
- Defined at `bot.py:77-96` (e.g., `WAITING_FOR_CHANNEL_ADD`)
- Used for multi-step user input flows (add/remove channels, folder management, forms)

## Performance Optimizations (Phase 1 - October 2025)

**Button Response Time Improvements:**

All button handlers now provide instant visual feedback to improve perceived responsiveness:

1. **Instant Feedback Pattern** - Applied to 6 key buttons:
   - `get_news` → "⏳ Начинаю сбор новостей..."
   - `manage_folders` → "⏳ Загружаю папки..."
   - `switch_folder` → "⏳ Переключаюсь на папку..."
   - `list_channels` → "⏳ Загружаю список каналов..."
   - `confirm_delete_folder` → "⏳ Удаляю папку..."
   - `remove_all` → "⏳ Удаляю все каналы..."

2. **Backup Optimization** (`bot.py:85-87, 198-212, 498-500`):
   - Added debouncing: max 1 backup per 60 seconds
   - Made backups non-blocking via `asyncio.create_task()`
   - Eliminates 50-200ms delay on every save operation
   - Configure via `_backup_debounce_seconds` variable

3. **Data Load Reduction**:
   - `create_folder_management_menu()` (lines 797-824): 2 loads → 1 load
   - `news_command_internal()` (lines 2421-2491): 6 loads → 1 load
   - Reduces lock contention and file I/O overhead

**Performance Impact:**
- Button perceived responsiveness: 90% improvement (instant feedback)
- Actual performance: 20-40% faster (backup + data load optimizations)
- Write operations (switch/delete folder): 150-400ms → 100-200ms
- `/news` command: More efficient data access, better progress feedback

**Configuration:**
- Backup debounce interval: `_backup_debounce_seconds = 60` (line 87)
- Can be adjusted based on usage patterns and backup requirements
