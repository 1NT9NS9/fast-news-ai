# Architecture

## Modular structure

```
bot/
├── main.py              # Bot initialization and handlers registration
├── handlers/
│   ├── start.py        # /start, /help commands
│   ├── news.py         # /news command logic
│   ├── manage.py       # /manage command and folder operations
│   ├── log.py          # /log command (admin weekly statistics)
│   └── buttons.py      # Button callback handlers
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


## System Purpose

A Telegram bot that aggregates news from multiple channels using AI-powered clustering and summarization to eliminate duplicate stories.

## Architectural Principles

1. **Separation of Concerns**: Clear boundaries between handlers (presentation), services (business logic), and models (data)
2. **Async-First**: All I/O operations (file, network, API) are non-blocking
3. **Performance via Caching**: In-memory cache for user data with file-backed persistence
4. **Reliability**: Graceful degradation with retries, fallbacks, and auto-recovery
5. **Rate Limiting**: User quotas and API concurrency controls

## Core Layers

### 1. Presentation Layer (`handlers/`)
**Responsibility**: User interaction and Telegram bot interface

- **start.py** - Command handlers (`/start`, `/help`)
- **news.py** - News digest workflow (`/news`)
- **manage.py** - Channel and folder management (`/manage`)
- **log.py** - Admin statistics from `bot_user.log` (`/log`, weekly metrics)
- **buttons.py** - Inline button callbacks and forms

**Key Pattern**: Handlers orchestrate services, never contain business logic.

### 2. Business Logic Layer (`services/`)
**Responsibility**: Core functionality implementation

- **StorageService** (`storage.py`) - Data persistence with in-memory caching, backup management
- **ScraperService** (`scraper.py`) - Web scraping from `t.me/s/{channel}`
- **AIService** (`ai.py`) - Gemini API interactions (embeddings, summarization)
- **ClusteringService** (`clustering.py`) - DBSCAN-based similarity grouping

**Key Pattern**: Services are stateless, reusable, and testable in isolation.

### 3. Data Layer (`models/`)
**Responsibility**: Data structures and validation

- **user_data.py** - Schema validation, migration logic

### 4. Infrastructure Layer (`utils/`)
**Responsibility**: Cross-cutting concerns

- **config.py** - Environment variables, constants, limits
- **logger.py** - Logging configuration

## Critical Interfaces

### Service Dependencies

```
handlers
    ├─> StorageService (load/save user data)
    ├─> ScraperService (fetch posts)
    ├─> AIService (embeddings, summaries)
    └─> ClusteringService (group posts)

AIService
    └─> google.generativeai (Gemini API)

ScraperService
    └─> httpx.AsyncClient (HTTP requests)

StorageService
    └─> aiofiles (async file I/O)
```

### Data Flow: `/news` Command

```
User → Handler (news.py)
    ↓
1. StorageService.check_rate_limit()
2. StorageService.get_user_channels()
3. ScraperService.scrape_channels() [parallel]
4. AIService.get_embeddings() [batched]
5. ClusteringService.cluster_posts()
6. AIService.generate_summary() [parallel]
7. Format → Send to user
8. StorageService.increment_news_counter()
```

### Storage Interface

**Key Methods**:
- `load_user_data() -> Dict` - Retrieve from cache or file
- `save_user_data(data: Dict)` - Update cache and persist to disk
- `get_user_channels(user_id: str) -> List[str]` - Extract channels for active folder
- `check_news_rate_limit(user_id: str) -> Tuple[bool, int]` - Validate daily quota

**State Management**: Thread-safe via `asyncio.Lock`, auto-recovery from corruption.

### AI Interface

**Key Methods**:
- `get_embeddings(texts: List[str]) -> List[List[float]]` - Batch embeddings (max 100/batch)
- `generate_summary(posts: List[str]) -> str` - Parallel summarization with retry

**Rate Limiting**: Semaphore enforces `GEMINI_CONCURRENT_LIMIT` (4000).

**Embedding Baseline**:
- Embeddings migrate to the `google.genai.Client` while summarization remains on `google-generativeai`.
- Model ID is `gemini-embedding-001` without a `models/` prefix.
- Supported output dimensionalities are 768, 1536, and 3072 (configurable via `EMBEDDING_OUTPUT_DIM`, default 768).
- Batches use `batch_embed_contents` when available with a semaphore + RPM gate; SDKs without the new method fall back to `embed_content`.
- Each response vector is validated for dimensionality and missing values before entering clustering.
- Dependencies include the new `google-genai` package (pinned in `requirements.txt`) alongside `google-generativeai`.

## Configuration

**Environment Variables** (`.env`; copy from `.env.example`):
- `TELEGRAM_BOT_API` - Bot token (required)
- `GEMINI_API` - Gemini key (required)
- `ADMIN_CHAT_ID` - Admin notifications (optional)
- `ADMIN_CHAT_ID_BACKUP` - Backup restoration + `/log` access (optional)
- `ADMIN_CHAT_ID_LOG` - ERROR/CRITICAL log notifications (optional)
- `GEMINI_EMBEDDING_MODEL` - Embedding model ID (`gemini-embedding-001`)
- `EMBEDDING_OUTPUT_DIM` - Output dimensionality (768 default; supports 1536, 3072)
- `EMBEDDING_TASK_TYPE` - Embedding task type (`retrieval_document` default)
- `EMBEDDING_TEXTS_PER_BATCH` - Max texts per embedding batch (default 50)
- `EMBEDDING_RPM` - Requests per minute cap for embedding calls (default 3000)
- `EMBEDDING_MAX_TOKENS` - Max tokens per text before truncation (default 400)
- `GEMINI_EMBEDDING_CONCURRENT_LIMIT` - Async semaphore limit for embeddings (default 32)

**Key Constants** (`bot/utils/config.py`):
- `MAX_CHANNELS = 10` - Channels per user
- `MAX_NEWS_REQUESTS_PER_DAY = 5` - Rate limit
- `SIMILARITY_THRESHOLD = 0.9` - Clustering sensitivity
- `GEMINI_CONCURRENT_LIMIT = 4000` - API concurrency

## Performance Strategy

1. **Caching**: User data cached in memory, invalidated on write
2. **Batching**: Embeddings processed in batches of 50
3. **Parallelism**: `asyncio.gather()` for scraping and summarization
4. **Connection Pooling**: Shared `httpx.AsyncClient` reuses connections
5. **Debouncing**: Backups limited to 1/minute to reduce I/O

## Reliability Mechanisms

- **Retry Logic**: Gemini API calls retry 3x with exponential backoff
- **Fallback**: Failed summaries return original text
- **Auto-Recovery**: Corrupted `user_data.json` restores from latest valid backup
- **Backup Rotation**: 20 backups retained with 7-day expiry
