# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Documentation:** [Architecture](docs/ARCHITECTURE.md) | [Domain Model](docs/DOMAIN.md) | [API Spec](docs/API_SPEC.yaml) | [Rate Limiter](docs/RATE_LIMITER.md) | [Security Notes (Phase 1)](docs/SECURITY_NOTES_PHASE1.md)

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
- `TELEGRAM_BOT_API` - Telegram bot token (required)
- `GEMINI_API` - Gemini API key (required)
- `ADMIN_CHAT_ID` - Optional admin chat ID for forms (group or channel)
- `ADMIN_CHAT_ID_BACKUP` - Optional admin chat ID for backup restoration and `/log`
- `ADMIN_CHAT_ID_LOG` - Optional admin chat ID for ERROR/CRITICAL log notifications
- `GEMINI_EMBEDDING_MODEL` - Embedding model ID (`gemini-embedding-001` default)
- `EMBEDDING_OUTPUT_DIM` - Embedding vector dimensionality (default 768; supports 1536/3072)
- `EMBEDDING_TASK_TYPE` - Embedding task type (`retrieval_document` default)
- `EMBEDDING_TEXTS_PER_BATCH` - Max texts per embedding batch (default 50)
- `EMBEDDING_RPM` - Embedding requests per minute cap (default 3000)
- `EMBEDDING_MAX_TOKENS` - Approx token budget before truncation (default 400)
- `GEMINI_EMBEDDING_CONCURRENT_LIMIT` - Semaphore limit for embedding calls (default 32)

**Run:**
```bash
python bot.py
```

## Architecture

```
bot/
- main.py              # Bot initialization and handler registration
- handlers/
  - start.py           # /start, /help commands
  - news.py            # /news command logic
  - manage.py          # /manage command and folder operations
  - log.py             # /log command (admin weekly statistics)
  - buttons.py         # Button callbacks (includes plan subscriptions)
- services/
  - storage.py         # File I/O and caching (StorageService)
  - scraper.py         # Channel scraping (ScraperService)
  - ai.py              # Gemini API interactions (AIService)
  - clustering.py      # Post clustering logic (ClusteringService)
- models/
  - user_data.py       # Data structures and validation
- utils/
  - config.py          # Constants and configuration
  - logger.py          # Logging setup

bot.py                 # Backward compatibility wrapper (calls bot.main)
```

Core stack:
- `python-telegram-bot` (21.6) - Telegram interface
- `google-genai` (0.3.0) - Embedding client for `gemini-embedding-001`
- `google-generativeai` (0.8.3) - Text generation (`gemini-flash-lite-latest`)
- `scikit-learn` (1.5.2) - DBSCAN clustering and cosine similarity
- `httpx` + `beautifulsoup4` - Scraping `https://t.me/s/{channel_name}`
- `aiofiles`, `numpy`, `python-dotenv` - Async persistence, vector math, env loading

## How `/news` Works

1. Scrape - Fetch posts from subscribed channels (parallel, max 20 posts/channel)
2. Embed - Batch texts via `google.genai.Client` (configurable batch size and dimensions)
3. Cluster - DBSCAN groups similar posts (0.9 similarity threshold)
4. Rank - Sort clusters by size (most sources first)
5. Summarize - Gemini Flash Lite summarizes clusters in parallel
6. Deliver - Format and send digest to the user

## Key Configuration

Constants in `bot/utils/config.py`:
```python
MAX_CHANNELS = 10
MAX_POSTS_PER_CHANNEL = 20
DEFAULT_NEWS_TIME_LIMIT_HOURS = 24
MAX_NEWS_TIME_LIMIT_HOURS = 720
DEFAULT_MAX_SUMMARY_POSTS = 10
MAX_SUMMARY_POSTS_LIMIT = 10
MAX_NEWS_REQUESTS_PER_DAY = 5
SIMILARITY_THRESHOLD = 0.9
GEMINI_CONCURRENT_LIMIT = 4000
GEMINI_EMBEDDING_CONCURRENT_LIMIT = 32
EMBEDDING_TEXTS_PER_BATCH = 50
EMBEDDING_RPM = 3000
EMBEDDING_MAX_TOKENS = 400
```

AIService pulls model IDs (`GEMINI_EMBEDDING_MODEL`, `gemini-embedding-001` default) and output dimensions from config, truncates inputs using a 3 chars/token heuristic, and enforces RPM/semaphore limits per embedding call.

## Security Notes

- Phase 1 rollout details, operator guidance, and rollback steps live in `docs/SECURITY_NOTES_PHASE1.md`.

## Data Storage

- `user_data.json` - User subscriptions, folders, preferences (cached in memory)
- `channel_feed.json` - Channel owner form submissions
- `plan_subscriptions.json` - Plan upgrade requests (Plus/Pro/Enterprise)
- `bot.log` - Application logs
- `bot_user.log` - User interaction logs (parsed by `/log`)

User data snapshot:
```json
{
  "123456": {
    "folders": {
      "default": ["@channel1", "@channel2"],
      "work": ["@channel3"]
    },
    "active_folder": "default",
    "time_limit": 24,
    "max_posts": 10,
    "news_requests": {"2025-10-11": 3}
  }
}
```

## Implementation Notes

**Performance**
- Async scraping and summarization via `asyncio.gather`
- Batched embeddings (configurable size) to reduce API calls
- In-memory caching for user data, channel counts, and AI client instances
- Shared `httpx.AsyncClient` for connection pooling
- Debounced backups (60s) and limited to 20 snapshots

**Reliability**
- Embedding calls use RPM limiter + exponential backoff with server hint support
- Summaries retry 3x; fall back to original text on failure
- Safety settings configured to avoid blocking legitimate news
- Auto-restore latest valid backup on JSON corruption
- Admin log notifications via Telegram (if `ADMIN_CHAT_ID_LOG` set)

**Constraints**
- Russian-language focus
- Public channels only (scrapes `https://t.me/s/{channel}`)
- Posts shorter than 50 characters skipped
- Channel IDs must start with `@`
- Non-Telegram URLs removed from summaries
- Rate limit: 5 `/news` requests per user per day (UTC)
- Max 10 channels per user across all folders

## Plan Subscriptions

- "Start" menu includes plan tiers (Free/Plus/Pro/Enterprise)
- Selections recorded in `plan_subscriptions.json` with user info and timestamp
- Handled in `bot/handlers/buttons.py` (start_plans + plan selections)

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
## Completed Rate Limiter Rollout Tasks

- All Telegram outbound sends route through bot/services/messenger.py, which wraps the RateLimiter queue.
- bot/services/rate_limiter.py tracks global (30 msg/s) and per-chat (1s) pacing, retries transient errors (up to 3x), and emits typing indicators when delays exceed 3s.
- /log (admin) now reports queue depth, average/max delay, and worst per-chat delay via get_queue_metrics().
- Rollout flag ENABLE_RATE_LIMITED_QUEUE (see README.md) toggles between queued + direct-send modes; messenger falls back automatically when disabled.
- Manual validation script (scripts/validate_rate_limiter.py) stress-tests the queue and prints pacing metrics.
- Automated tests: 	tests/ 
