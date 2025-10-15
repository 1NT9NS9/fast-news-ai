# Bot Module Structure

This directory contains the modularized Telegram news aggregation bot (v2.0).

## Architecture Overview

```
bot/
├── main.py              # Application entry point
├── handlers/            # User interaction handlers
│   ├── __init__.py     # Exports all handlers and conversation states
│   ├── start.py        # /start, /help commands
│   ├── news.py         # /news command workflow
│   ├── manage.py       # Channel/folder management
│   └── buttons.py      # Button callbacks and forms
├── services/            # Business logic layer
│   ├── __init__.py     # Exports all service classes
│   ├── storage.py      # Data persistence and caching
│   ├── scraper.py      # Channel web scraping
│   ├── ai.py           # Gemini AI integration
│   └── clustering.py   # Post clustering (DBSCAN)
├── models/              # Data structures
│   ├── __init__.py
│   └── user_data.py    # Validation and migration
└── utils/               # Shared utilities
    ├── __init__.py
    ├── config.py       # Configuration constants
    └── logger.py       # Logging setup
```

---

## Module Responsibilities

### `main.py` - Application Entry Point
**Purpose:** Bot initialization and handler registration

**Key Functions:**
- `create_application()`: Creates Telegram Application with all handlers
- `main()`: Starts bot polling

**Dependencies:** All handlers, services

---

### `handlers/` - User Interaction Layer

#### `start.py` - Welcome & Menu
**Handlers:**
- `start_command()`: Initialize new users with default folder (Папка1)
- `help_command()`: Display help text
- `handle_return_to_menu()`: Persistent keyboard handler

**UI Components:**
- `create_main_menu()`: Inline keyboard with all actions
- `create_persistent_keyboard()`: "Return to menu" button

#### `news.py` - News Aggregation
**Handlers:**
- `news_command()`: Entry point for /news command
- `news_command_internal()`: Full workflow implementation

**Workflow:**
1. Check rate limit (5 requests/day)
2. Scrape channels (ScraperService)
3. Generate embeddings (AIService)
4. Cluster similar posts (ClusteringService)
5. Generate summaries (AIService)
6. Format and send to user

**Rate Limiting:**
- 5 requests per user per day (UTC)
- Remaining requests shown to user

#### `manage.py` - Channel & Folder Management
**Command Handlers:**
- `/add`: Add channel to active folder
- `/remove`: Remove channel from active folder
- `/remove_all`: Remove all channels
- `/list`: List channels in active folder
- `/time`: Set news time range
- `/posts`: Set max summaries count
- `/restore_backup`: Restore user data from backup (admin only)

**Conversation Handlers:**
- `handle_add_channel_input()`: Validates and adds channel
- `handle_remove_channel_input()`: Removes specified channel
- `handle_time_interval_input()`: Sets time range (1-720 hours)
- `handle_news_count_input()`: Sets max posts (1-30)
- `handle_new_folder_name()`: Creates new folder

**Folder Operations:**
- Create/rename/delete folders
- Switch active folder
- Channel count validation (max 10 across all folders)

#### `buttons.py` - Button Callbacks
**Main Dispatcher:**
- `button_callback()`: Routes all button presses to appropriate handlers

**Channel Owner Forms:**
- Add channel to feed (with description)
- Remove channel from feed (with reason)
- Restrict channel access (with reason)
- Forms sent to `ADMIN_CHAT_ID`

**Folder Management:**
- Switch folder callback
- Create folder callback
- Delete folder callback with confirmation

**Settings:**
- Time interval adjustment
- News count adjustment

---

### `services/` - Business Logic Layer

#### `storage.py` - Data Persistence
**Class:** `StorageService`

**Core Operations:**
- `load_user_data()`: Load with caching and auto-recovery
- `save_user_data()`: Save with validation and backup
- `get_user_data_cached()`: Fast cached access

**Channel Operations:**
- `get_user_channels()`: Channels in active folder
- `set_user_channels()`: Update active folder channels
- `get_all_user_channels()`: All channels across folders (cached)

**Folder Operations:**
- `get_user_folders()`: All folders for user
- `create_folder()`: Create new folder
- `delete_folder()`: Delete folder (with safety checks)
- `switch_active_folder()`: Change active folder

**Rate Limiting:**
- `check_news_rate_limit()`: Check if user can request news
- `increment_news_request()`: Increment daily counter

**Backup Management:**
- `backup_user_data()`: Create timestamped backup (debounced)
- `restore_user_data_from_backup()`: Manual restore
- `_attempt_auto_restore_user_data()`: Auto-restore on corruption
- Rotation: max 20 backups, 7-day retention

**Features:**
- In-memory caching with async locks
- Debounced backups (max 1/minute)
- Auto-recovery from corruption
- Channel count caching for performance

#### `scraper.py` - Web Scraping
**Class:** `ScraperService`

**Methods:**
- `extract_channel_username()`: Parse @username from various formats
- `get_channel_posts()`: Scrape posts from `t.me/s/{channel}`
- `scrape_all_channels()`: Parallel scraping with `asyncio.gather()`
- `validate_channel_access()`: Check if channel is accessible

**Features:**
- Shared `httpx.AsyncClient` for connection pooling
- HTML parsing with BeautifulSoup
- UTC timestamp normalization
- Filters posts < 50 chars
- Parallel processing for multiple channels

#### `ai.py` - AI Integration
**Class:** `AIService`

**Embedding:**
- `get_embeddings()`: Generate embeddings with `text-embedding-004`
- Batched processing (100 texts per batch)
- Thread pool execution to avoid blocking

**Summarization:**
- `summarize_cluster()`: Generate headline and summary
- Retry logic with exponential backoff (3 attempts)
- Rate limiting with semaphore (4000 concurrent)
- Safety settings: `BLOCK_NONE` to avoid blocking news

**Configuration:**
- Embedding model: `text-embedding-004`
- Generation model: `gemini-flash-lite-latest`
- Temperature: 0.3, Max tokens: 500

#### `clustering.py` - Post Clustering
**Class:** `ClusteringService`

**Methods:**
- `cluster_posts()`: DBSCAN clustering on embeddings
- Groups similar posts (0.9 similarity threshold)
- Handles outliers (noise points)

**Algorithm:**
- DBSCAN with cosine similarity
- Epsilon: 0.1 (1 - 0.9 threshold)
- Min samples: 1

---

### `models/` - Data Structures

#### `user_data.py` - Validation & Migration
**Functions:**
- `migrate_user_data_to_folders()`: Migrate old format to folder structure
- `validate_user_data()`: Comprehensive data validation

**Validation Checks:**
- Folder structure integrity
- Active folder exists
- Channel format (@username)
- Time limit bounds (1-720 hours)
- Max posts bounds (1-30)
- News requests format (date: count)

---

### `utils/` - Shared Utilities

#### `config.py` - Configuration
**Environment Variables:**
- `TELEGRAM_BOT_API`: Bot token (required)
- `GEMINI_API`: Gemini API key (required)
- `ADMIN_CHAT_ID`: Admin chat for forms (optional)
- `ADMIN_CHAT_ID_BACKUP`: Admin chat for backups (optional)

**Constants:**
- `MAX_CHANNELS = 10`: Channel limit per user
- `MAX_POSTS_PER_CHANNEL = 20`: Posts scraped per channel
- `DEFAULT_NEWS_TIME_LIMIT_HOURS = 24`: Default time range
- `MAX_NEWS_TIME_LIMIT_HOURS = 720`: Max time range (30 days)
- `DEFAULT_MAX_SUMMARY_POSTS = 10`: Default summaries
- `MAX_SUMMARY_POSTS_LIMIT = 30`: Max summaries
- `MAX_NEWS_REQUESTS_PER_DAY = 5`: Rate limit
- `SIMILARITY_THRESHOLD = 0.9`: Clustering threshold
- `GEMINI_CONCURRENT_LIMIT = 4000`: API rate limit

**File Paths:**
- `USER_DATA_FILE = 'user_data.json'`
- `CHANNEL_FEED_FILE = 'channel_feed.json'`
- `USER_DATA_BACKUP_DIR = 'backups/user_data'`

#### `logger.py` - Logging Setup
**Function:** `setup_logging()`

**Returns:** `(logger, user_logger)`
- `logger`: General application logging → `bot.log`
- `user_logger`: User interactions → `bot_user.log`

---

## Data Flow Example: `/news` Command

```
User presses "📰 Получить новости" button
    ↓
button_callback() in buttons.py
    ↓
news_command_internal() in news.py
    ↓
┌─────────────────────────────────────────┐
│ 1. StorageService.check_news_rate_limit │
│    → Check if user has requests left    │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 2. StorageService.get_user_channels     │
│    → Get channels from active folder    │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 3. ScraperService.scrape_all_channels   │
│    → Parallel scraping (asyncio.gather) │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 4. AIService.get_embeddings             │
│    → Batch embeddings (100 per batch)   │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 5. ClusteringService.cluster_posts      │
│    → DBSCAN clustering                  │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 6. AIService.summarize_cluster (×N)     │
│    → Parallel summarization             │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 7. Format and send summaries to user    │
│    → MarkdownV2 with fallback           │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 8. StorageService.increment_news_request│
│    → Update rate limit counter          │
└─────────────────────────────────────────┘
```

---

## Conversation States

Defined in `handlers/__init__.py`:

```python
WAITING_FOR_CHANNEL_ADD              # User adding channel
WAITING_FOR_CHANNEL_REMOVE           # User removing channel
WAITING_FOR_TIME_INTERVAL            # User setting time range
WAITING_FOR_NEWS_COUNT               # User setting max posts
WAITING_FOR_NEW_FOLDER_NAME          # User creating folder
WAITING_FOR_ADD_TO_FEED_CHANNEL      # Form: add to feed
WAITING_FOR_ADD_TO_FEED_HASHTAG      # Form: hashtag selection
WAITING_FOR_ADD_TO_FEED_DESCRIPTION  # Form: description
WAITING_FOR_REMOVE_FROM_FEED_CHANNEL # Form: remove from feed
WAITING_FOR_REMOVE_FROM_FEED_REASON  # Form: reason
WAITING_FOR_RESTRICT_ACCESS_CHANNEL  # Form: restrict access
WAITING_FOR_RESTRICT_ACCESS_REASON   # Form: reason
```

---

## Performance Optimizations

### Caching Strategy
1. **User data cache**: In-memory dict with async lock
2. **Channel count cache**: Avoids recalculating across folders
3. **Gemini model cache**: Single model instance reused

### Async Operations
- File I/O: `aiofiles` for non-blocking reads/writes
- Scraping: `httpx.AsyncClient` with connection pooling
- AI calls: Thread pool execution for sync library
- Parallel processing: `asyncio.gather()` for scraping and summarization

### Backup Optimization
- **Debouncing**: Max 1 backup per 60 seconds
- **Synchronous await**: Prevents race condition (fixed empty backups)
- **Rotation**: Limits backups to 20 newest + 7-day retention

### Button Optimization
- **Instant feedback**: ⏳ messages before long operations
- **Reduced loads**: 1 data load instead of 2-6 in hot paths
- **Lock efficiency**: Minimal time spent holding locks

---

## Testing

### Unit Tests
Individual service test files (Phase 4):
- `test_storage.py`: StorageService caching and I/O
- `test_ai.py`: AIService model initialization
- `test_scraper.py`: ScraperService HTTP client
- `test_clustering.py`: ClusteringService DBSCAN

### Integration Tests
See `PHASE7_TEST_RESULTS.md` for comprehensive test plan

### Manual Testing
All manual tests completed (see `implementation_plan.md` Phase 7.4)

---

## Debugging

### Enable Debug Logging
Edit `bot/utils/logger.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    ...
)
```

### Check Diagnostics
```python
from bot.services import StorageService

storage = StorageService()
data = await storage.load_user_data()
is_valid, errors = validate_user_data(data)
if not is_valid:
    print('\n'.join(errors))
```

### View Backups
```python
storage = StorageService()
backups = storage.list_user_data_backups()
for backup in backups:
    print(f"{backup['name']}: {backup['mtime']}")
```

---

## Migration from v1.0

All changes are backward compatible:
- `bot.py` wrapper maintains old entry point
- User data automatically migrated to folder structure
- All existing commands work as before

New features:
- Folder management
- Separate admin ID for backups
- Channel input normalization
- Auto-restore from backup

---

## Contributing

When adding new features:

1. **New Handler:**
   - Add to appropriate file in `handlers/`
   - Export from `handlers/__init__.py`
   - Register in `main.py::create_application()`

2. **New Service:**
   - Create class in `services/`
   - Export from `services/__init__.py`
   - Add docstrings and type hints

3. **New Configuration:**
   - Add to `utils/config.py`
   - Update `.env.example` if environment variable

4. **Documentation:**
   - Update `CLAUDE.md` with new functionality
   - Add docstrings to all public methods
   - Update this README if architecture changes

---

## License

This bot is for internal use. See parent directory for license information.
