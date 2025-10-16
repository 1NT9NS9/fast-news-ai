# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Documentation:** [Architecture](docs/ARCHITECTURE.md) | [Domain Model](docs/DOMAIN.md) | [API Spec](docs/API_SPEC.yaml)

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
- `ADMIN_CHAT_ID` - (Optional) Admin chat ID for channel owner forms (can be group/channel)
- `ADMIN_CHAT_ID_BACKUP` - (Optional) Admin chat ID for backup restoration and `/log` command access (must be personal chat)
- `ADMIN_CHAT_ID_LOG` - (Optional) Admin chat ID for receiving ERROR/CRITICAL log notifications via Telegram

**Run:**
```bash
python bot.py
```

## Architecture

**Modular structure** 

```
bot/
├── main.py              # Bot initialization and handlers registration
├── handlers/
│   ├── start.py        # /start, /help commands
│   ├── news.py         # /news command logic
│   ├── manage.py       # /manage command and folder operations
│   ├── log.py          # /log command (admin weekly statistics)
│   └── buttons.py      # Button callbacks (includes plan subscriptions)
├── services/
│   ├── storage.py      # File I/O and caching (StorageService)
│   ├── scraper.py      # Channel scraping (ScraperService)
│   ├── ai.py           # Gemini API interactions (AIService)
│   └── clustering.py   # Post clustering logic (ClusteringService)
├── models/
│   └── user_data.py    # Data structures and validation
└── utils/
    ├── config.py       # Constants and configuration
    └── logger.py       # Logging setup

bot.py                   # Backward compatibility wrapper (calls bot.main)
```

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

Constants in `bot/utils/config.py`:
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
- `plan_subscriptions.json` - Plan upgrade requests (Plus/Pro/Enterprise)
- `bot.log` - Application logs
- `bot_user.log` - User interaction logs (parsed by `/log` command for weekly statistics)

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
- gRPC verbosity suppressed via environment variables (`bot/utils/config.py`)
- Cache operations lock consistently for thread safety
- User data backups rotate with retention (debounced to prevent excessive I/O)
- Migration paths carry version metadata for future schema changes
- Auto-restore from newest valid backup if user data becomes corrupted
- **Telegram log notifications** - ERROR/CRITICAL messages sent to admin chat for remote monitoring (configured via `ADMIN_CHAT_ID_LOG`)

**Constraints:**
- Russian language only
- Public channels only (scrapes web preview from `https://t.me/s/{channel}`)
- Posts < 50 chars filtered out
- Channel names must start with `@`
- Non-Telegram URLs removed from summaries
- Rate limit: 5 `/news` per user per day (UTC)
- Max 10 channels per user (across all folders)
- Timestamps normalized to UTC; posts without timestamps are dropped

**Plan Subscriptions:**
- "✨ Start" button in main menu shows plan tiers (Free/Plus/Pro/Enterprise)
- Plan upgrade requests saved to `plan_subscriptions.json` with user_id, username, plan, timestamp
- Handlers: `bot/handlers/buttons.py:204-220` (start_plans), `367-379` (plan selection)

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