# AGENTS.md

Guidance for any AI coding agent working in this repository.

## Project Snapshot

Telegram bot that monitors multiple channels, clusters overlapping news, and sends a clean digest back to the user. Entire implementation lives in `bot.py` (~3000 lines).

Core stack:
- python-telegram-bot v21.6 for bot framework
- google-generativeai v0.8.3 using `text-embedding-004` + `gemini-flash-lite-latest`
- scikit-learn v1.5.2 (DBSCAN) for similarity clustering
- httpx + beautifulsoup4 for scraping `https://t.me/s/{channel_name}`

## Local Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` with:
- `TELEGRAM_BOT_API`: Telegram bot token
- `GEMINI_API`: Gemini API key
- `ADMIN_CHAT_ID` (optional): receiver for channel owner forms

Start the bot:
```bash
python bot.py
```

## `/news` Pipeline

1. Scrape up to 20 posts per subscribed channel (async); normalize naive Telegram timestamps to UTC and drop posts that arrive without any timestamp so time windows stay accurate.
2. Batch embeddings (100 at a time).
3. DBSCAN groups posts using `SIMILARITY_THRESHOLD = 0.9`.
4. Rank clusters by size.
5. Summaries generated in parallel; fallback to source text on failure.
6. Formatted digest delivered to the user.

## Configuration Touchpoints (`bot.py:51-62`)

```
MAX_CHANNELS = 10
MAX_POSTS_PER_CHANNEL = 20
DEFAULT_NEWS_TIME_LIMIT_HOURS = 24
MAX_NEWS_TIME_LIMIT_HOURS = 720
DEFAULT_MAX_SUMMARY_POSTS = 10
MAX_SUMMARY_POSTS_LIMIT = 30
MAX_NEWS_REQUESTS_PER_DAY = 5
SIMILARITY_THRESHOLD = 0.9
GEMINI_CONCURRENT_LIMIT = 4000
```

## Persistent Data

- `user_data.json`: per-user folders, preferences, usage counters (cached in memory)
- `channel_feed.json`: channel owner submissions
- `bot.log` / `bot_user.log`: application and user interaction logs

Sample `user_data.json` entry:
```json
{
  "user_id": {
    "folders": {
      "Folder1": ["@channel1", "@channel2"],
      "Folder2": ["@channel3"]
    },
    "active_folder": "Folder1",
    "time_limit": 24,
    "max_posts": 10,
    "news_requests": {"2025-10-11": 3}
  }
}
```

## Performance & Reliability Notes

## Completed Remediation Tasks

- **Data management (4.md):** Cache operations now lock consistently, user data backups rotate with retention, and migration paths carry version metadata for future schema changes.
- **Performance (5.md):** Folder channel counts reuse cached results, async file I/O via `aiofiles` removes event-loop blocking, and a shared `httpx.AsyncClient` pools connections for scraping/validation.

- User data cached to minimize file I/O.
- `asyncio.gather()` handles parallel scraping and summarization.
- Semaphore caps concurrent Gemini calls at 4000.
- Gemini API retries up to 3 times with exponential backoff.
- Safety settings set to `BLOCK_NONE`; falls back to original text on summarization failure.
- gRPC verbosity suppressed via env variables near top of `bot.py`.

## Behavioral Constraints

- Designed for Russian-language content.
- Only public Telegram channels; scrapes web previews.
- Filters out posts under 50 characters; channel names must begin with `@`.
- Removes non-Telegram URLs from summaries.
- Enforces per-user limits: 5 `/news` requests per UTC day; max 10 channels across folders.
- Single-channel digest requests surface `This channel has no news for your time period.` when nothing lands inside the selected interval.

## Docker Workflow

```bash
docker build -t keytime-bot .
docker run -d --name keytime-bot ^
  -e TELEGRAM_BOT_API="your_token" ^
  -e GEMINI_API="your_key" ^
  -v %cd%:/app/data ^
  keytime-bot

docker logs -f keytime-bot
```

(Replace PowerShell `^` with `\` on Unix shells.)

## Feature Highlights

- Folder Management (`bot.py:99-306`): create/rename/delete folders, track active folder, migrate older stored data.
- Channel Owner Forms (`bot.py:2137-2199`): validates submissions, routes to `ADMIN_CHAT_ID`.
- Rate Limiting (`bot.py:186-216`): UTC-based daily counters, communicates remaining quota.

## Development Hooks

- Tweak core limits via the constants block above.
- Embedding model lives in `get_embeddings()` around line 1020; generation model via `get_gemini_model()` around line 1122.
- Enable verbose logging by setting `level=logging.DEBUG` near `bot.py:29`.
- Adding commands: define async handler, register with `CommandHandler`, expose through `create_main_menu()` and `button_callback()` as needed.
- Conversation states enumerated at `bot.py:77-96` and power multi-step flows for channels, folders, and forms.
- `/news` interval selection is covered by stubbed end-to-end checks; keep those stubs aligned when adjusting scraping or filtering logic.
