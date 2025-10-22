# Phase 1 Security Execution Plan — KeyTime Bot

Last Updated: 2025-10-21
Scope: Expands “Phase 1 — Critical (Day 0–1)” from SECURITY_PLAN.md into time‑boxed, verifiable subtasks.

Objectives
- Remove high-risk classes: leaked secrets, SSRF/path traversal, unsafe logging.
- Remediate known dependency vulnerabilities.
- Make changes small, testable, and reversible.

Constraints
- Subtasks are 30–90 minutes (≤1–1.5h) each.
- Deliver in small commits; keep rollback easy.

Milestones
- M1: Secrets rotated + history checked.
- M2: SSRF validators created + integrated.
- M3: Safe restore implemented.
- M4: Vulnerable packages remediated.
- M5: Logger sanitization and file permission hardening.

Execution Map (Time‑boxed Subtasks)

1) Prep: Snapshot and Branching (30–45m) [Complete]
- Steps
  - Create a short‑lived working branch `sec/phase1`.
  - Snapshot current env: copy `.env` to `backups/env_backup_<YYYYMMDD-HHMM>.txt`.
  - Verify `README.md`/CLAUDE.md reflect current quick start (no edits required unless stale).
- Files: `.git/`, `backups/`
- Acceptance
  - Branch created; env backup present and excluded from git.

2) Secrets: Rotate Telegram Bot Token (45–60m) [Complete]
- Steps
  - Use BotFather: `/revoke` current token; generate a new token.
  - Update `.env` value `TELEGRAM_BOT_API=...`.
  - Restart local run to confirm bot connects using the new token.
- Files: `.env`
- Acceptance
  - Bot starts with new token; old token invalidated.

3) Secrets: Rotate Gemini API Key (30–45m) [Complete]
- Steps
  - Create a new Gemini API key in Google AI Studio; revoke old key.
  - Update `.env` `GEMINI_API=...`.
  - Run a minimal AI call via `bot/services/ai.py` path that initializes client (local smoke run).
- Files: `.env`
- Acceptance
  - AI client initializes without errors; old key revoked.

4) Secrets Hygiene: Check VCS Exposure (45–60m) [Complete]
- Steps
  - Inspect history for `.env` or tokens: `git log --all --full-history -- .env` and targeted greps for token patterns.
  - If found, document commit SHAs and prepare purge plan (BFG/git filter‑repo) for Phase 2 if needed; ensure current `.gitignore` blocks `.env`.
- Files: `.gitignore`, repo history
- Acceptance
  - Written note in PR/commit message: “No secrets in history” or “Secrets found; queued for history purge in Phase 2”.

5) SSRF Guardrails: Add Validators Module (45–60m) [Complete]
- Steps
  - Create `bot/utils/validators.py` with:
    - `validate_channel_name(name: str) -> str` enforcing `^@?[A-Za-z0-9_]{5,32}$` and canonicalizing to leading `@`.
    - `validate_scrape_url(channel: str) -> str` enforcing exact `https://t.me/s/<channel>`; block localhost, private IPs, non‑https schemes.
  - Include focused unit tests under `tests/` (naming aligns with repo patterns).
- Files: `bot/utils/validators.py`, `tests/test_validators.py`
- Acceptance
  - Tests pass locally; invalid inputs raise `ValueError` with clear messages.

6) Wire Validators: Scraper Integration (60–90m) [Complete]
- Steps
  - In `bot/services/scraper.py`, validate channel and computed URL before any request.
  - Enforce `https://t.me/s/` origin; reject non‑conforming.
  - Add minimal logging on validation failures (INFO/WARN) without echoing raw user input.
- Files: `bot/services/scraper.py`
- Acceptance
  - Invalid channels/URLs are rejected early; happy path unchanged; smoke test `/news` still works.

7) Wire Validators: Channel Management Integration (45–60m) [Complete]
- Steps
  - In `bot/handlers/manage.py`, validate channel names on add/remove operations using `validate_channel_name`.
  - Normalize and store canonical `@channel` form in user data.
- Files: `bot/handlers/manage.py`, `bot/models/user_data.py` (if normalization helpers are present)
- Acceptance
  - UI flow rejects malformed channel IDs; existing valid channels unaffected.

8) Path Traversal Safe Restore (60–90m) [Complete]
- Steps
  - In `bot/services/storage.py`, harden restore path:
    - Allow only `^user_data_\d{8}_\d{6}\.json$` filenames.
    - Use `Path.resolve()` and ensure `candidate_path.relative_to(backups_dir)` succeeds; otherwise abort.
  - Add unit tests targeting malicious filename attempts and success path.
- Files: `bot/services/storage.py`, `tests/test_storage_restore.py`
- Acceptance
  - Tests cover valid/invalid cases; restore rejects traversal attempts.

9) Dependency Bump: Protobuf and Requests (45–60m)
- Steps
  - Update `requirements.txt` to include: `protobuf>=6.31.1`, `requests>=2.31.0` (keeping compatibility with pinned Google SDKs).
  - Run local install; verify app still starts and `/news` basic path functions.
- Files: `requirements.txt`
- Acceptance
  - App runs without import/runtime errors; versions reflect bump.

10) Dependency Audit: pip‑audit (45–60m)
- Steps
  - Install and run `pip-audit` locally.
  - Address any CRITICAL/HIGH findings that are safe to pin within current stack.
  - Document unresolved items with rationale and schedule follow‑ups in Phase 2.
- Files: `requirements.txt`, audit notes in PR/commit description
- Acceptance
  - No critical outstanding findings or clear follow‑up plan documented.

11) Logger: Secret Redaction + Safe Formatting (60–90m)
- Steps
  - In `bot/utils/logger.py`, add filters to sanitize:
    - Gemini keys `AIza[\w-]{35}` → `[REDACTED_API_KEY]`.
    - Telegram tokens `\d+:AA[\w-]{33}` → `[REDACTED_BOT_TOKEN]`.
  - Strip absolute paths to basenames; disable HTML parsing in log sinks (avoid `parse_mode`).
  - Ensure error notifications route through `bot/services/messenger.py` if anything is sent to Telegram, not direct HTTP.
- Files: `bot/utils/logger.py`, `bot/services/messenger.py` (confirm usage)
- Acceptance
  - Local logs show redaction; no HTML parsing in logs; runtime warnings/errors still visible.

12) Logger: File Permissions (30–45m)
- Steps
  - When initializing handlers, set restrictive file modes (0600) on `bot.log` and `bot_user.log` where OS permits.
  - Add a startup check that logs a WARN if perms are looser than expected.
- Files: `bot/utils/logger.py`
- Acceptance
  - On Unix hosts, perms are 600; on Windows, no error and check is skipped or informational.

13) Verification Pass (45–60m)
- Steps
  - Run unit tests added in Steps 5 and 8.
  - Run quick manual validation: invalid channel input and restore traversal attempt.
  - Perform a `/news` request end‑to‑end; check logs for redaction and absence of stack traces.
- Files: test files, runtime logs
- Acceptance
  - All tests pass; manual checks succeed; bot remains functional.

14) Documentation + Rollback Notes (30–45m)
- Steps
  - Update `SECURITY_PLAN.md` checklist items for Phase 1 as done.
  - Add short operator notes to `docs/` (e.g., `docs/SECURITY_NOTES_PHASE1.md`) summarizing what changed and how to revert.
  - Record any deferred items into Phase 2 backlog.
- Files: `SECURITY_PLAN.md`, `docs/SECURITY_NOTES_PHASE1.md`
- Acceptance
  - Clear operator guidance exists; deferred items captured.

Risk Management
- Keep each subtask behind small commits for easy `git revert`.
- Prefer additive changes and feature flags where feasible (e.g., `ENABLE_SSRF_PROTECTION`).
- If an integration step breaks `/news`, roll back the last change, capture logs, and file an issue.

Deliverables Summary
- Code: `bot/utils/validators.py`, hardened `scraper.py`, hardened `storage.py`, updated `logger.py`, updated `requirements.txt`.
- Tests: `tests/test_validators.py`, `tests/test_storage_restore.py`.
- Ops: Rotated secrets; audit notes; Phase 1 verification recorded.

Estimated Duration
- 10–12 effective hours across 1–2 working days, parallelizable where practical (e.g., validators and logger tasks in parallel).

