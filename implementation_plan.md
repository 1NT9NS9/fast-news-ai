# Implementation Plan: Bot.py Modularization

**Goal:** Split `bot.py` (2,577 lines) into a modular structure as defined in `ph_3.md`

**Estimated Time:** 4-6 hours
**Risk Level:** High (major refactoring with no test coverage)
**Date:** 2025-10-13

---

## Target Structure

```
bot/
├── main.py              # Bot initialization and handlers registration
├── handlers/
│   ├── __init__.py
│   ├── start.py        # /start command
│   ├── news.py         # /news command logic
│   ├── manage.py       # /manage command and folder operations
│   └── buttons.py      # Button callback handlers
├── services/
│   ├── __init__.py
│   ├── storage.py      # File I/O and caching
│   ├── scraper.py      # Channel scraping
│   ├── ai.py           # Gemini API interactions
│   └── clustering.py   # Post clustering logic
├── models/
│   ├── __init__.py
│   └── user_data.py    # Data structures and validation
└── utils/
    ├── __init__.py
    ├── config.py       # Constants and configuration
    └── logger.py       # Logging setup
```

---

## Phase 1: Preparation (30 minutes) ✅ COMPLETED

### 1.1 Backup and Safety
- [x] Create git branch: `refactor/modularization`
- [x] Backup current `bot.py` to `bot.py.backup`
- [ ] Ensure bot is working before starting (run and test `/start`, `/news`, `/manage`)
- [ ] Document current functionality for regression testing

### 1.2 Create Directory Structure
- [x] Create `bot/` directory
- [x] Create subdirectories: `handlers/`, `services/`, `models/`, `utils/`
- [x] Create all `__init__.py` files

---

## Phase 2: Extract Utilities & Configuration (45 minutes) ✅ COMPLETED

**Goal:** Move non-dependent code first to reduce complexity

### 2.1 Extract Configuration (`utils/config.py`)
Lines to move from `bot.py:51-62`:
- [x] All constant definitions (MAX_CHANNELS, MAX_POSTS_PER_CHANNEL, etc.)
- [x] Environment variable loading logic (TELEGRAM_BOT_API, GEMINI_API, ADMIN_CHAT_ID)
- [x] gRPC environment variables (lines 4-8)
- [x] Add type hints for all constants

**Dependencies:** None

### 2.2 Extract Logging Setup (`utils/logger.py`)
Lines to move from `bot.py:15-42`:
- [x] Logger initialization for `bot.log`
- [x] Logger initialization for `bot_user.log`
- [x] Log formatting configuration
- [x] Function: `setup_logging() -> Tuple[Logger, Logger]`

**Dependencies:** None

### 2.3 Test Phase 2
- [x] Import `config` and `logger` modules
- [x] Verify constants accessible
- [x] Verify logging works

---

## Phase 3: Extract Models (30 minutes) ✅ COMPLETED

### 3.1 Create Data Models (`models/user_data.py`)
- [x] Define `UserData` dataclass/TypedDict (user_id, folders, active_folder, time_limit, max_posts, news_requests)
- [ ] Define `ChannelFeedData` dataclass
- [ ] Add validation methods (e.g., `validate_channel_name()`)
- [x] Extract migration logic (lines 265-352: `migrate_user_data_to_folders()`, `validate_user_data()`)
- [ ] Add helper methods for data manipulation

**Dependencies:** `utils/config`

### 3.2 Test Phase 3
- [x] Verify data structures instantiate correctly
- [x] Test migration function with sample data

---

## Phase 4: Extract Services (2-3 hours)

**This is the most complex phase - proceed carefully**

### 4.1 Extract Storage Service (`services/storage.py`)

**Lines to move:**
- Lines 64-83: Cache initialization (`_user_data_cache`, `_cache_lock`, backup tracking)
- Lines 186-306: All storage functions
  - `load_user_data()`
  - `save_user_data()`
  - `get_user_data_cached()`
  - `invalidate_user_cache()`
  - `create_user_data_backup()`
  - `load_channel_feed()`
  - `save_channel_feed()`

**Class structure:**
```python
class StorageService:
    def __init__(self):
        self._user_data_cache = {}
        self._cache_lock = asyncio.Lock()
        # ... backup tracking

    async def load_user_data(self) -> dict
    async def save_user_data(self, data: dict) -> None
    async def get_user_data_cached(self, user_id: str) -> dict
    # ... other methods
```

**Dependencies:** `utils/config`, `utils/logger`, `models/user_data`

### 4.2 Extract AI Service (`services/ai.py`)

**Lines to move:**
- Lines 1020-1067: `get_embeddings()` and batching logic
- Lines 1122-1143: `get_gemini_model()`
- Lines 1144-1199: `generate_ai_summary()` with retry logic
- Lines 1200-1279: `generate_summaries_parallel()`
- Gemini API configuration and safety settings

**Class structure:**
```python
class AIService:
    def __init__(self):
        self.embedding_model = "text-embedding-004"
        self.generation_model = "gemini-flash-lite-latest"
        self.semaphore = asyncio.Semaphore(GEMINI_CONCURRENT_LIMIT)

    async def get_embeddings(self, texts: List[str]) -> List
    def get_gemini_model(self)
    async def generate_ai_summary(self, posts: List[str]) -> str
    async def generate_summaries_parallel(self, clusters: List) -> List
```

**Dependencies:** `utils/config`, `utils/logger`

### 4.3 Extract Scraper Service (`services/scraper.py`)

**Lines to move:**
- Lines 308-386: `extract_channel_username()`
- Lines 388-533: `get_channel_posts()` and scraping logic
- Lines 535-613: `scrape_all_channels()`
- Lines 615-640: `validate_channel_access()`
- Shared `httpx.AsyncClient` pool

**Class structure:**
```python
class ScraperService:
    def __init__(self):
        self.client = httpx.AsyncClient(...)

    def extract_channel_username(self, channel: str) -> Optional[str]
    async def get_channel_posts(self, channel: str, hours: int) -> List
    async def scrape_all_channels(self, channels: List[str], hours: int) -> List
    async def validate_channel_access(self, channel: str) -> Tuple[bool, str]

    async def close(self):
        await self.client.aclose()
```

**Dependencies:** `utils/config`, `utils/logger`

### 4.4 Extract Clustering Service (`services/clustering.py`)

**Lines to move:**
- Lines 1068-1120: `cluster_posts()` with DBSCAN logic
- Clustering helper functions

**Class structure:**
```python
class ClusteringService:
    def __init__(self):
        self.similarity_threshold = SIMILARITY_THRESHOLD

    def cluster_posts(self, embeddings: List, posts: List) -> List[List]
```

**Dependencies:** `utils/config`, `utils/logger`

### 4.5 Test Phase 4
- [ ] Test each service independently with sample data
- [ ] Verify service initialization
- [ ] Test error handling and retries
- [ ] Verify async operations work correctly

---

## Phase 5: Extract Handlers (1-2 hours)

**Important:** Handlers depend on services, so services must be complete first

### 5.1 Extract Start Handler (`handlers/start.py`)

**Lines to move:**
- Lines 642-667: `start_command()`
- Lines 669-708: `create_main_menu()`

**Dependencies:** `utils/logger`, `services/storage`

### 5.2 Extract Manage Handler (`handlers/manage.py`)

**Lines to move:**
- Lines 710-742: `manage_command()`
- Lines 744-824: `create_folder_management_menu()`
- Lines 1474-1571: Folder creation handlers
- Lines 1573-1667: Folder deletion handlers
- Lines 1669-1792: Folder rename handlers
- Lines 1794-1880: Channel add handlers
- Lines 1882-1966: Channel remove handlers
- Lines 1968-2011: Remove all channels handlers
- Lines 2013-2050: List channels handler
- Lines 2052-2093: Folder switch handlers

**Dependencies:** `utils/config`, `utils/logger`, `services/storage`, `models/user_data`

### 5.3 Extract News Handler (`handlers/news.py`)

**Lines to move:**
- Lines 2421-2491: `news_command()` (wrapper)
- Lines 1280-1410: `news_command_internal()` (main logic)
- Lines 1412-1472: `format_summaries_for_telegram()`
- Rate limiting logic (lines 826-861)

**Dependencies:** All services (storage, scraper, ai, clustering)

### 5.4 Extract Button Handler (`handlers/buttons.py`)

**Lines to move:**
- Lines 863-1280: `button_callback()` and all button logic
- Lines 2095-2135: Settings handlers
- Button state management

**Dependencies:** All other handlers, services

### 5.5 Test Phase 5
- [ ] Test each command independently
- [ ] Verify ConversationHandler states work
- [ ] Test button callbacks
- [ ] Verify folder operations
- [ ] Test `/news` end-to-end

---

## Phase 6: Create Main Entry Point (30 minutes)

### 6.1 Create `bot/main.py`

**Lines to move:**
- Lines 2493-2577: Main bot initialization
- Application setup
- Handler registration
- Bot startup logic

**Structure:**
```python
from handlers import start, news, manage, buttons
from services import storage, scraper, ai, clustering
from utils import config, logger

def create_application():
    # Initialize services
    storage_service = storage.StorageService()
    scraper_service = scraper.ScraperService()
    ai_service = ai.AIService()
    clustering_service = clustering.ClusteringService()

    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_API).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start.start_command))
    application.add_handler(CommandHandler("news", news.news_command))
    # ... etc

    return application

if __name__ == "__main__":
    app = create_application()
    app.run_polling()
```

### 6.2 Update Root Directory
- [ ] Keep `bot.py` for backward compatibility (imports from `bot/main.py`)
- [ ] Update `requirements.txt` if needed
- [ ] Update `Dockerfile` to use new structure
- [ ] Update `CLAUDE.md` with new architecture

---

## Phase 7: Integration & Testing (1-2 hours)

### 7.1 Smoke Testing
- [ ] Run bot: `python bot/main.py`
- [ ] Test `/start` command
- [ ] Test main menu buttons
- [ ] Test `/manage` - create folder
- [ ] Test `/manage` - add channel
- [ ] Test `/manage` - switch folder
- [ ] Test `/news` command (full flow)
- [ ] Test channel owner form submission
- [ ] Test settings (time limit, max posts)

### 7.2 Error Handling
- [ ] Verify all error messages still display
- [ ] Test rate limiting
- [ ] Test invalid channel handling
- [ ] Test API failures (Gemini timeout/error)

### 7.3 Performance Validation
- [ ] Verify button response times (instant feedback still works)
- [ ] Verify backup debouncing still works
- [ ] Check memory usage
- [ ] Verify parallel processing still works

### 7.4 Data Migration
- [ ] Test with existing `user_data.json`
- [ ] Verify old user data still loads
- [ ] Test migration function

---

## Phase 8: Cleanup & Documentation (30 minutes)

### 8.1 Code Cleanup
- [ ] Remove unused imports
- [ ] Add type hints throughout
- [ ] Add docstrings to all public methods
- [ ] Format code with black/autopep8

### 8.2 Documentation
- [ ] Update `CLAUDE.md` with new structure
- [ ] Add module-level docstrings
- [ ] Create `bot/README.md` explaining module responsibilities
- [ ] Document any breaking changes

### 8.3 Final Verification
- [ ] Run bot for 10 minutes in production
- [ ] Monitor logs for errors
- [ ] Verify Docker build works
- [ ] Create git tag: `v2.0-modular`

---

## Rollback Plan

If critical issues arise:

1. **Immediate rollback:**
   ```bash
   git checkout main
   python bot.py.backup
   ```

2. **Identify issue:**
   - Check logs: `bot.log`, `bot_user.log`
   - Review error messages
   - Compare with backup behavior

3. **Fix or revert:**
   - If fixable quickly (< 30 min), fix and test
   - Otherwise, revert to `bot.py.backup` and debug offline

---

## Success Criteria

- [ ] All commands work identically to original bot
- [ ] No performance degradation
- [ ] Logs show no new errors
- [ ] User data preserved and accessible
- [ ] Docker build successful
- [ ] Code is more maintainable (easier to find functions)

---

## Notes & Risks

### Key Risks:
1. **Circular dependencies:** Services may depend on each other (especially storage + handlers)
2. **Global state:** Cache, locks, and semaphores need careful migration
3. **ConversationHandler:** States span multiple handlers - easy to break
4. **No tests:** All validation must be manual

### Mitigation:
- Test each phase independently before moving to next
- Keep `bot.py.backup` for quick rollback
- Use dependency injection where possible
- Consider adding basic tests in future

### Future Improvements (Post-Refactor):
- Add unit tests for services
- Add integration tests for handlers
- Consider using a proper DI framework
- Add mypy type checking
- Consider moving to async file I/O throughout
