# Bot Module Structure

Modularized Telegram news aggregation bot (v2.0) - See `CLAUDE.md` for complete documentation.

**Documentation:** [Architecture](../docs/ARCHITECTURE.md) | [Domain Model](../docs/DOMAIN.md) | [API Spec](../docs/API_SPEC.yaml)

## Architecture

```
bot/
├── main.py              # Bot initialization and handler registration
├── handlers/            # User interaction layer
│   ├── start.py        # /start, /help, menu
│   ├── news.py         # /news workflow (scrape → embed → cluster → summarize)
│   ├── manage.py       # Channel/folder management, settings
│   └── buttons.py      # Button callbacks and forms
├── services/            # Business logic
│   ├── storage.py      # Data persistence, caching, backups (StorageService)
│   ├── scraper.py      # Channel web scraping (ScraperService)
│   ├── ai.py           # Gemini embeddings & summarization (AIService)
│   └── clustering.py   # DBSCAN post clustering (ClusteringService)
├── models/
│   └── user_data.py    # Validation and migration
└── utils/
    ├── config.py       # Environment vars and constants
    └── logger.py       # Logging setup
```

## Core Services

### StorageService (`services/storage.py`)
- In-memory caching with async locks
- Auto-recovery from corrupted data
- Debounced backups (max 1/minute, 20 backups, 7-day retention)
- Methods: `load_user_data()`, `save_user_data()`, `get_user_channels()`, `check_news_rate_limit()`

### ScraperService (`services/scraper.py`)
- Scrapes `t.me/s/{channel}` with `httpx.AsyncClient` pooling
- Parallel scraping via `asyncio.gather()`
- Filters posts < 50 chars, normalizes timestamps to UTC

### AIService (`services/ai.py`)
- Embeddings: `text-embedding-004` (batched, 100/batch)
- Summarization: `gemini-flash-lite-latest` (temp 0.3, 500 tokens max)
- Retry logic (3 attempts), rate limiting (4000 concurrent)

### ClusteringService (`services/clustering.py`)
- DBSCAN with cosine similarity (0.9 threshold)
- Groups similar posts, handles outliers

## Configuration (`utils/config.py`)

**Environment:**
- `TELEGRAM_BOT_API` - Bot token (required)
- `GEMINI_API` - Gemini key (required)
- `ADMIN_CHAT_ID` - Forms destination (optional)
- `ADMIN_CHAT_ID_BACKUP` - Backup restoration (optional)

**Key Limits:**
- `MAX_CHANNELS = 10` (per user)
- `MAX_POSTS_PER_CHANNEL = 20`
- `MAX_NEWS_REQUESTS_PER_DAY = 5`
- `SIMILARITY_THRESHOLD = 0.9`

## `/news` Workflow

1. Check rate limit (5/day) → 2. Get active folder channels → 3. Scrape (parallel) → 4. Embed (batched) → 5. Cluster (DBSCAN) → 6. Summarize (parallel) → 7. Format & send → 8. Increment counter

## Performance Optimizations

- **Caching**: User data, channel counts, AI models
- **Async I/O**: `aiofiles` for file operations, `httpx.AsyncClient` for scraping
- **Parallel processing**: `asyncio.gather()` for scraping/summarization
- **Button optimization**: Instant feedback (⏳), reduced data loads (1 vs 2-6)

## Development

**Debug Logging:**
```python
# bot/utils/logger.py
logging.basicConfig(level=logging.DEBUG)
```

**Check Backups:**
```python
storage = StorageService()
backups = storage.list_user_data_backups()
```

**Contributing:**
1. Add handlers to `handlers/`, export from `__init__.py`, register in `main.py`
2. Add services to `services/`, export from `__init__.py`
3. Update `utils/config.py` for new constants
4. Update `CLAUDE.md` and add docstrings

