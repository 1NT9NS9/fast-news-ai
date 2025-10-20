Tasks to Implement Rate Limits + Queue

Notes
- Tasks are scoped to <= 1–1.5 hours each.
- Paths refer to repository files (create new files if they don’t exist).

1) Inventory all outbound sends [Complete]
- Goal: Find every place that calls Telegram send APIs directly.
- Actions: Search for `bot.send_`, `context.bot.send_`, `editMessage`, and media group sends.
- Output: Short list of file:line references to update.
- Done: All direct-sends identified and listed.

2) Add config constants [Complete]
- File: `bot/utils/config.py`
- Add: `GLOBAL_RATE_MESSAGES_PER_SEC = 30`, `PER_CHAT_COOLDOWN_SEC = 1.0`, `HEAVY_LOAD_DELAY_THRESHOLD_SEC = 3.0`.
- Done: Constants available for import; defaults match plan.

3) Create RateLimiter service skeleton [Complete]
- File: `bot/services/rate_limiter.py`
- Add class with init, `start()`, `stop()`, and `enqueue_send(method, *, chat_id, args=(), kwargs=None, context=None)` signatures.
- Done: Compiles; no behavior yet.

4) Implement global sliding-window limiter [Complete]
- File: `bot/services/rate_limiter.py`
- Use `collections.deque` of timestamps; provide `can_send_global(now)` and `record_global(now)` enforcing <= 30 msgs/sec.
- Done: Unit-level functions ready; covered by simple self-test or docstring examples.

5) Implement per-chat cooldown tracker [Complete]
- Track `last_sent_at` per `chat_id`; provide `next_allowed_for_chat(chat_id, now)` and `record_chat_send(chat_id, now)` with >= 1s spacing.
- Done: Functions return correct timestamps in quick sanity checks.

6) Implement scheduling queue and worker loop [Complete]
- File: `bot/services/rate_limiter.py`
- Use `heapq` over `(ready_at, seq, task)`; background `asyncio` worker pops due items, sleeps until next due.
- Done: Worker starts/stops cleanly; no-ops for now at dispatch.

7) Implement dispatch with revalidation [Complete]
- File: `bot/services/rate_limiter.py`
- On pop, re-check global and per-chat limits; if not allowed, recompute `ready_at` and requeue; else call the PTB bot method with args/kwargs.
- Done: Messages send when allowed; postponed if not.

8) Record send events and update limiters [Complete]
- File: `bot/services/rate_limiter.py`
- After successful send, update global deque and per-chat `last_sent_at`.
- Done: Timestamps persisted; affects subsequent scheduling.

9) Add basic retry policy for transient errors [Complete]
- File: `bot/services/rate_limiter.py`
- Retry on network/429 with exponential backoff respecting limits; cap attempts (e.g., 3).
- Done: Backoffs occur without breaking limits; failures logged.

10) Heavy load: initial typing action [Complete]
- File: `bot/services/rate_limiter.py`
- On enqueue, if `ready_at - now > HEAVY_LOAD_DELAY_THRESHOLD_SEC`, immediately send `sendChatAction(chat_id, 'typing')` (bypasses queue).
- Done: Typing appears right away; no message budget consumed.

[test] tests/ test_api_4.py - test_api_10.py [Complete]

11) Messenger wrapper helpers [Complete]
- File: `bot/services/messenger.py`
- Add `send_text`, `send_photo`, `send_document`, `send_media_group` thin wrappers over `enqueue_send`.
- Done: Handlers can import and use.

12) Bootstrap RateLimiter in app startup [Complete]
- File: `bot/main.py`
- Instantiate service with `application.bot`; wire `on_startup` to `start()` and `on_shutdown` to `stop()`.
- Done: Bot boots with worker running; graceful shutdown works.

13) Refactor buttons handler [Complete]
- File: `bot/handlers/buttons.py`
- Replace direct sends with messenger wrappers; keep `answer_callback_query` immediate.
- Done: Handler compiles and uses the queue.

14) Refactor news handler [Complete]
- File: `bot/handlers/news.py`
- Route all outgoing text/media sends through messenger wrappers; preserve existing functionality.
- Done: Compiles; digest sends are queued and rate-limited.

[test] tests/ test_api_4.py - test_api_10.py, test_api_13.py - test_api_14.py [Complete]

15) Refactor manage handler [Complete]
- File: `bot/handlers/manage.py`
- Replace direct sends with messenger wrappers; ensure folder operations still respond promptly.
- Done: Compiles; behavior unchanged except for rate control.

16) Refactor start/log handlers [Complete]
- Files: `bot/handlers/start.py`, `bot/handlers/log.py`
- Replace direct sends with messenger wrappers; confirm admin log sends are queued.
- Done: Both compile and run via queue.

17) Add delay metrics to /log output [Complete]
- File: `bot/handlers/log.py`
- Include queue depth, max delay, average delay, and highest per-chat delay in `/log` output (admin-only).
- Done: Admin `/log` shows delay metrics when backlog exists.

18) Logging and metrics [Complete]
- File: `bot/services/rate_limiter.py`
- Log on enqueue (ready_at, delay, queue depth), on dispatch, and heavy-load typing activations; optional notify `ADMIN_CHAT_ID_LOG` for sustained delays.
- Done: Logs visible in `bot.log` with clear fields.

19) Feature flag for rollout [Complete]
- File: `bot/utils/config.py`
- Add `ENABLE_RATE_LIMITED_QUEUE = True`; guard usage in `main.py` to allow fallback.
- Done: Toggle works; off-mode uses direct sends.

[test] tests/ test_api_4.py - test_api_10.py, test_api_13.py - test_api_19.py [Complete]

20) Manual validation scripts [Complete]
- File: `scripts/validate_rate_limiter.py`
- Script to enqueue N messages across M chats to verify global and per-chat limits, observe backlog metrics, and confirm typing indicator behavior.
- Done: CLI helper simulates bursts, prints pacing summaries, and exercises logging end-to-end.

21) Documentation updates [Complete]
- Files: `README.md` (or add a short section), link from `CLAUDE.md`
- Describe queue behavior, limits, typing indicator under load, and `/log` delay metrics; note that all messages are eventually delivered.
- Done: Docs reviewed and committed.



