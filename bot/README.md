# Bot Module Structure

Modularized Telegram news aggregation bot (v2.0) - see `CLAUDE.md` for complete documentation.

**Documentation:** [Architecture](../docs/ARCHITECTURE.md) | [Domain Model](../docs/DOMAIN.md) | [API Spec](../docs/API_SPEC.yaml) | [Rate Limiter](../docs/RATE_LIMITER.md) | [Security Notes (Phase 1)](../docs/SECURITY_NOTES_PHASE1.md)

## Architecture

```
bot/
- main.py              # Bot initialization and handler registration
- handlers/            # User interaction layer
  - start.py           # /start, /help, menu
  - news.py            # /news workflow (scrape -> embed -> cluster -> summarize)
  - manage.py          # Channel/folder management, settings
  - buttons.py         # Button callbacks and forms
- services/            # Business logic
  - storage.py         # Data persistence, caching, backups (StorageService)
  - scraper.py         # Channel web scraping (ScraperService)
  - ai.py              # Gemini embeddings & summarization (AIService)
  - clustering.py      # DBSCAN post clustering (ClusteringService)
- models/
  - user_data.py       # Validation and migration
- utils/
  - config.py          # Environment vars and constants
  - logger.py          # Logging setup and sanitization
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
- Embeddings: `gemini-embedding-001` via `google.genai.Client` (configurable 768/1536/3072 dims, 50 texts/batch default, RPM-governed with per-vector validation)
- Summarization: `gemini-flash-lite-latest` through `google-generativeai` (temperature 0.3, 500 tokens max)
- Separate semaphores, RPM limiter, and exponential backoff retries

### ClusteringService (`services/clustering.py`)
- DBSCAN with cosine similarity (0.9 threshold)
- Groups similar posts, handles outliers

## Configuration (`utils/config.py`)

**Environment:**
- `TELEGRAM_BOT_API` - Bot token (required)
- `GEMINI_API` - Gemini key (required)
- `ADMIN_CHAT_ID` - Forms destination (optional)
- `ADMIN_CHAT_ID_BACKUP` - Backup restoration (optional)
- `ADMIN_CHAT_ID_LOG` - Error/critical log notifications (optional)
- `GEMINI_EMBEDDING_MODEL` - Embedding model ID (`gemini-embedding-001` default)
- `EMBEDDING_OUTPUT_DIM` - Output dimensionality (default 768; supports 1536/3072)
- `EMBEDDING_TASK_TYPE` - Embedding task type (`retrieval_document` default)
- `EMBEDDING_TEXTS_PER_BATCH` - Texts per embedding batch (default 50)
- `EMBEDDING_RPM` - Embedding requests per minute cap (default 3000)
- `EMBEDDING_MAX_TOKENS` - Token budget per text before truncation (default 400)
- `GEMINI_EMBEDDING_CONCURRENT_LIMIT` - Semaphore limit for embedding calls (default 32)
- Copy `.env.example` to `.env` and fill in the required keys before running the bot.

**Key Limits:**
- `MAX_CHANNELS = 10` (per user)
- `MAX_POSTS_PER_CHANNEL = 20`
- `MAX_NEWS_REQUESTS_PER_DAY = 5`
- `SIMILARITY_THRESHOLD = 0.9`
- `MAX_SUMMARY_POSTS_LIMIT = 10`

## `/news` Workflow

1. Check rate limit (5/day)
2. Load active folder channels
3. Scrape channels in parallel
4. Embed batched posts (configurable model/output dim)
5. Cluster with DBSCAN and cosine similarity
6. Summarize clusters in parallel
7. Format and send digest to user
8. Increment request counter

## Performance Optimizations

- Cache user data, channel counts, and AI clients
- Async I/O via `aiofiles` and `httpx.AsyncClient`
- Batched embeddings and parallel summarization
- Immediate button feedback for snappy UX

## Security Operations

- Phase 1 rollout summary, operator guidance, and rollback steps live in `../docs/SECURITY_NOTES_PHASE1.md`.
- Rate limiter behavior and validation tooling documented in `../docs/RATE_LIMITER.md`.

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
