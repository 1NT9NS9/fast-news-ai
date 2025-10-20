# JSON → SQLite Migration Plan

## 1. Objectives & Success Criteria
- Replace `user_data.json` writes with a SQLite-backed store without data loss or user-visible regression.
- Preserve existing behavior (folders, rate limiting, backups) while unlocking transactional safety and concurrent access.
- Finish migration in one working day with the ability to roll back to JSON instantly if needed.

Success is measured by:
1. All reads/writes routed through SQLite by default, with JSON left as a cold backup.
2. Load/latency at or below current levels during `/news` bursts.
3. Monitoring shows no increase in storage-related errors 24 hours post-deploy.

## 2. Current State Snapshot
- `bot/services/storage.py` keeps a process cache, but ultimately loads and rewrites `user_data.json`.
- Aux files (`channel_feed.json`, `plan_subscriptions.json`) remain JSON; only user state migrates.
- Backups: debounced 60 s, capped at `MAX_BACKUP_COUNT`, stored in `USER_DATA_BACKUP_DIR`.
- Data shape per user: `folders`, `active_folder`, `time_limit`, `max_posts`, `news_requests{YYYY-MM-DD: count}`.

Pain points: whole-file rewrites, no concurrency control, increasing corruption risk past a few hundred active users.

## 3. Target Design (SQLite)
- File: `data/keytime.db` (alongside JSON) with WAL mode enabled for concurrent readers.
- Tables (all `INTEGER` except noted):
  - `users(user_id TEXT PRIMARY KEY, active_folder TEXT NOT NULL, time_limit INTEGER, max_posts INTEGER, updated_at DATETIME)`
  - `folders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, name TEXT NOT NULL, UNIQUE(user_id, name))`
  - `folder_channels(folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE, channel TEXT NOT NULL, PRIMARY KEY(folder_id, channel))`
  - `news_requests(user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, request_date TEXT NOT NULL, request_count INTEGER NOT NULL, PRIMARY KEY(user_id, request_date))`
- Views/helpers: materialized view or SQL query for extracting all channels per user.
- Access layer: new async `SQLiteStorageService` using `aiosqlite` to mirror the async API of `StorageService`.
- Migrations: bootstrap creates tables on startup via idempotent `CREATE TABLE IF NOT EXISTS` statements.

## 4. Application Changes
1. **Storage abstraction**: introduce `BaseStorage` protocol with the current method surface (`load_user_data`, `save_user_data`, channel helpers, backups). Keep JSON implementation as `JsonStorageService`.
2. **SQLite implementation**:
   - Map each existing method to SQL transactions; reuse caching logic where practical.
   - Implement batch helpers (e.g., replace entire user record inside a single transaction with `INSERT ... ON CONFLICT` and bulk channel operations).
3. **Feature flag**: add `ENABLE_SQLITE_STORAGE` (env/config). When false, use JSON only; when true, prefer SQLite with optional dual writes.
4. **Dependency injection**: `bot/main.py` chooses implementation based on config and passes it to handlers/services.
5. **Backups**: keep existing JSON backup logic but add SQLite backup step (`VACUUM INTO` nightly or reuse JSON restore until SQLite backup automation is added in later iteration).

## 5. Data Migration Strategy
1. **Pre-migration**
   - Freeze working tree; take manual copy of `user_data.json`.
   - Write `scripts/migrate_user_data_to_sqlite.py`:
     - Loads JSON through `JsonStorageService`.
     - Opens SQLite connection, wraps inserts in a transaction.
     - Maintains backup of original JSON (timestamped copy in backup dir).
   - Unit test the script with fixture JSON (single user, multi-folder, edge cases).
2. **Dry run**
   - Execute script locally against sample/staging data; verify counts (`SELECT COUNT(*)` comparisons).
   - Add validation step that re-hydrates SQLite data via new service and diffs with original JSON (excluding ordering).
3. **Deploy preparation**
   - Ship new code with flag defaulting to JSON.
   - Include migration script + instructions in README/CLAUDE doc.
4. **Live migration**
   - Stop the bot briefly (or use maintenance flag) to avoid writes.
   - Run migration script once, confirm log output + manual spot-check.
   - Enable flag for dual read/write mode: reads prefer SQLite, writes update both stores.
5. **Verification window (2–4 hours)**
   - Monitor logs for storage errors.
   - Run `/news`, `/manage` workflows manually.
   - Compare JSON and SQLite snapshots periodically (scripted checksum).
6. **Cut-over**
   - Toggle config to disable JSON writes and skip JSON load fallback once confident.
   - Archive final JSON copy in backups and document location.

## 6. Testing & Validation
- **Unit tests**: cover SQLite service methods (CRUD, concurrency lock behavior, migrations).
- **Integration tests**: run existing handler flows with dependency injection using an in-memory SQLite DB.
- **Load test**: reuse `scripts/validate_rate_limiter.py` to emulate burst requests while SQLite storage is active.
- **Regression matrix**: `/news`, folder CRUD, plan subscription flows, rate-limit enforcement.
- **Monitoring hooks**: emit metrics (success/failure counts, latency) through existing logger or future metrics sink.

## 7. Rollback Plan
- Keep `ENABLE_SQLITE_STORAGE` flag to fall back immediately to JSON if issues arise.
- Retain untouched `user_data.json` backup (`user_data.json.pre-sqlite-<timestamp>.bak`) for instant restore.
- Provide script `scripts/sqlite_to_json.py` for reverse migration if long-term rollback is needed.

## 8. Timeline (1 Working Day)
1. **Morning (2–3 h)**: implement storage abstraction + SQLite service skeleton; write schema bootstrap.
2. **Midday (2 h)**: build migration script, run dry-run tests, write automated diff validation.
3. **Afternoon (2 h)**: enable dual mode, adjust wiring, add tests/docs, prepare release notes.
4. **Deploy window (1 h buffered)**: run migration in staging, monitor, then promote to production.

## 9. Open Questions / Follow-Ups
- Do we need to migrate `channel_feed.json` and `plan_subscriptions.json` later? Capture requirements.
- Decide on long-term backup cadence for SQLite (cron-based `VACUUM INTO` or OS-level snapshots).
- Evaluate whether to keep per-process caching once SQLite proves fast enough; dropping it simplifies logic.
