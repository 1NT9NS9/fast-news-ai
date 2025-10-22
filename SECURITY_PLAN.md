# Unified Security Improvement Plan — KeyTime Bot

Last Updated: 2025-10-21
Status: CRITICAL — Immediate Action Required

This document consolidates and de-duplicates SECURITY_C_PLAN.md and SECURITY_CC_PLAN.md into a single, actionable roadmap. It focuses on immediate risk reduction, durable guardrails, and verifiable delivery.

Scope: Supersedes SECURITY_C_PLAN.md and SECURITY_CC_PLAN.md.

## Objectives
- Eliminate exploitable gaps: credentials, SSRF/path traversal, logging leaks, race conditions, AI abuse.
- Strengthen runtime posture: least privilege, rate limits, backpressure, safe defaults.
- Improve observability and recovery: metrics, audits, backups, rollback.

## Guiding Principles
- Deny-by-default, minimize attack surface.
- Fail safe, isolate blast radius, make behavior observable.
- Ship in small, testable increments with rollback.

## Timeline Overview
- Phase 1 (Day 0–1): Critical fixes and credential hygiene.
- Phase 2 (Week 1): Concurrency, logging safety, Docker hardening, CI hygiene.
- Phase 3 (Week 2): AI throttles/safety, scraping + queue limits, secrets manager, observability.
- Phase 4 (Weeks 3–4): Prompt-injection defenses, audit logging, metrics/alerts, data-at-rest + runbooks.

---

## Phase 1 — Critical (Day 0–1)

1) Credential Rotation & Secrets
- Backup `.env` securely; rotate Telegram bot token (BotFather `/revoke`) and Gemini API key (AI Studio).
- Verify `.env` is not in git history: `git log --all --full-history -- .env`; scrub if present.
- Production: plan to source from a secret manager (used in Phase 3) with `.env` reserved for local/dev.

2) Input Validation & SSRF Hardening
- Add `bot/utils/validators.py`:
  - `validate_channel_name()`: `^@?[a-zA-Z0-9_]{5,32}$` (reject `..`, `/`, `\`).
  - `validate_scrape_url()`: enforce `https://t.me/s/{channel}`; block `localhost`, private IPs, file/proc schemes.
- Apply validators in `bot/services/scraper.py` before any fetch and in `bot/handlers/manage.py` before channel add.

3) Path Traversal Safe Restore
- In `bot/services/storage.py::restore_user_data_from_backup()`:
  - Enforce filename: `^user_data_\d{8}_\d{6}\.json$`.
  - Use `Path.resolve()` + `.relative_to(backup_dir)`; reject if outside `backups/`.

4) Dependency Vulnerabilities
- Upgrade protobuf and audit:
  - `pip install --upgrade google-generativeai "protobuf>=6.31.1" requests>=2.31.0`
  - `pip install pip-audit && pip-audit`; address findings.

5) Logging & Alerting Safety
- In `bot/utils/logger.py`:
  - Sanitize secrets: Gemini `AIza[a-zA-Z0-9_-]{35}` → `[REDACTED_API_KEY]`; Bot token `\d+:AA[a-zA-Z0-9_-]{33}` → `[REDACTED_BOT_TOKEN]`.
  - Strip absolute paths to basenames; HTML-escape messages or use `parse_mode=None`.
  - Ensure non-blocking sends via `bot/services/messenger.py` (rate-limited queue) rather than direct network calls.
  - Enforce file perms (container/host): `bot.log`, `bot_user.log` mode 600.

Verification (Phase 1)
- `pytest tests/test_ssrf_protection.py`
- `pip-audit`
- Manual: run `python bot.py` (clean start) and simulate invalid inputs; logs should be sanitized.

Rollback (Phase 1)
- Stop bot; restore last working code/data/env snapshot; restart.

---

## Phase 2 — High Priority (Week 1)

1) Concurrency & Data Integrity
- Refactor `StorageService` to a shared singleton (module-level factory) so a single set of async locks protect all paths.
- Add tests simulating concurrent `/news` requests; assert counters, folders, and channel lists stay consistent.
- Instrument `/news` to record per-user rate-limit breaches (metric/log entry).

2) Docker & Runtime Posture
- Update `Dockerfile`:
  - Create non-root user: `groupadd -r botuser && useradd -r -g botuser botuser`; `USER botuser` before `CMD`.
  - Add `HEALTHCHECK`.
  - Ensure data/backups dirs are 700.
- Add/update `.dockerignore` to exclude `.env`, logs, data, `.git`.

3) CI & Dependency Hygiene
- Pin `requests` in `requirements.txt` or refactor logger to reuse the async HTTP client.
- Add security checks to CI: `pip-audit` and `bandit`.
- Enable dependency monitoring (Dependabot/Renovate) with security severity gates.
- Split deps:
  - `requirements-prod.txt`: runtime only
  - `requirements-dev.txt`: extends prod with pytest, pip-audit, bandit, black, mypy
  - Update `Dockerfile` to install `-prod.txt`.

Verification (Week 1)
- `docker run --rm keytime-bot:secure whoami` → `botuser`.
- Concurrency tests pass; CI gates enforce audit tools and deny critical findings.

---

## Phase 3 — Controls Expansion (Week 2)

1) AI Usage Hardening
- Reduce `GEMINI_CONCURRENT_LIMIT` to ~16 and enforce RPM throttles at the command/AI layer.
- Re-enable/confirm Gemini safety settings; document override procedure for incident response.

2) Rate Limiting & Queue Safety
- In `bot/services/ai.py`: per-user embedding throttle (e.g., 100 req/min sliding window with deque + user locks).
- In `bot/services/scraper.py`: semaphore (max 5 concurrent) and global 60 scrapes/min cap; acquire slot before each scrape.
- In `bot/services/rate_limiter.py`: add `max_queue_size=10000`; raise and surface metric/alert when full.

3) Secrets Management
- Source production secrets from a secret manager (Vault/Azure Key Vault/etc.); keep `.env` for local/dev only.

4) Observability Foundations
- Emit structured counters for rate-limit events, request failures, AI fallbacks (Prometheus/OpenTelemetry compatible).

Verification (Week 2)
- `pytest tests/test_ai_rate_limiting.py` and `tests/test_scraper_rate_limits.py`.
- Observe queue depth and backpressure behavior under load.

---

## Phase 4 — Abuse Protections, Auditability, and Data (Weeks 3–4)

1) Prompt Injection Defense
- Create `bot/utils/content_filter.py`:
  - Regex patterns to detect injections (e.g., `ignore (previous|all|above) instructions`, `you are (now|a)`, `system:` tokens).
  - `sanitize_prompt_input()` to replace matches with `[FILTERED]`.
  - `CHANNEL_BLOCKLIST` for admin-managed denylists.
- Apply in `bot/services/ai.py`: Filter blocked channels; sanitize all post text before prompts.

2) Audit Logging
- Create `bot/utils/audit.py` with rotating file handler (`bot_audit.log`, 10MB, keep 10):
  - `log_admin_action(user_id, action, details)`
  - `log_unauthorized_access(user_id, action)`
- Enforce file perms 600; integrate calls in admin handlers.

3) Monitoring & Alerts
- `bot/utils/metrics.py` (Prometheus): `news_requests_total`, `rate_limit_breaches`, `ai_failures`, `request_duration`, `queue_depth`.
- Alert thresholds: AI failures >5%, queue >5000, per-chat worst delay >1m, rate-limit breaches >100/min.

4) Data Protection & Runbooks
- Short-term: Encrypt JSON persistence using `cryptography` (Fernet); key in `DATA_ENCRYPTION_KEY`.
- Medium-term: Migrate to encrypted datastore (SQLite/PG with at-rest encryption, least-privileged access).
- Review backup rotation and encryption for `backups/user_data_*`.
- Define incident response runbook (thresholds, on-call, comms) and schedule quarterly security reviews.

Verification (Weeks 3–4)
- `pytest tests/test_prompt_injection_defense.py` and audit logging tests.
- `curl http://localhost:8000/metrics` shows expected metrics; alerts fire at thresholds.

---

## File-Level Implementation Pointers
- `bot/services/scraper.py`: enforce `https://t.me/s/` origin; integrate validators; add RPM/semaphore gates.
- `bot/services/storage.py`: safe restore with `Path.resolve()/relative_to()`; singleton pattern for shared locks.
- `bot/services/ai.py`: per-user rate limiter; lowered concurrency; safety settings.
- `bot/services/rate_limiter.py`: `max_queue_size` + metrics for drops/backpressure; ensure messenger uses queue.
- `bot/utils/validators.py`: strict regex + SSRF/URL guards.
- `bot/utils/logger.py`: sanitization, non-blocking send, safe formatting, file perms.
- `Dockerfile` and `.dockerignore`: drop root, perms, healthcheck, exclusions.
- CI: `pip-audit`, `bandit`, dependency bot; split prod/dev requirements.

---

## Risks & Mitigations
- Storage refactor regressions → add integration tests, stage rollout.
- Added throttles increase latency → tune thresholds, cache results, expose metrics.
- Secret manager operational overhead → document workflows and provide tooling/scripts.
- Summarization quality dips after safety tightening → monitor baseline metrics; iterate prompts.

---

## Verification Checklist (Aggregated)
- Tests: concurrency, SSRF/path traversal, logger formatting, AI rate limiting, scraper limits, prompt-injection.
- Security scans in CI: `pip-audit`, `bandit` with fail-on-critical.
- Runtime posture: container runs as `botuser`; logs/audit files mode 600; queue size/latency within bounds.
- Functional: `/news` under load respects per-user + global limits; admin notifications remain sanitized.

---

## Rollback

Emergency
```bash
docker stop keytime-bot  # or: pkill -f bot.py
cp backups/user_data_<timestamp>.json user_data.json
git stash && git checkout <previous_commit>
cp ../env_backup_<date>.txt .env
python bot.py
```

Feature Flags (in `config.py`)
```python
ENABLE_ENCRYPTION = os.getenv('ENABLE_ENCRYPTION', 'true') == 'true'
ENABLE_SSRF_PROTECTION = os.getenv('ENABLE_SSRF_PROTECTION', 'true') == 'true'
```

Operator Notes: see `docs/SECURITY_NOTES_PHASE1.md` for applied mitigations and rollback pointers.

---

## Implementation Checklist

Phase 1 (Critical)
- [x] Credential rotation + verify `.env` not in git
- [x] SSRF validation wired to scraper + handlers
- [x] Path traversal safe restore
- [x] Protobuf/requests upgrade + `pip-audit`
- [x] Logger sanitization + non-blocking + perms

Phase 2 (Week 1)
- [ ] StorageService singleton + concurrency tests
- [ ] Docker non-root + perms + healthcheck + .dockerignore
- [ ] CI: `pip-audit`, `bandit`, dependency bot
- [ ] Split prod/dev requirements; Docker uses prod
- [ ] Revisit protobuf/requests bump with compatibility fixes (deferred from Phase 1)
- [ ] Re-enable logger file permission hardening with cross-platform guard rails (deferred from Phase 1)

Phase 3 (Week 2)
- [ ] AI throttles + safety settings
- [ ] Scraping limits (semaphore + RPM)
- [ ] Rate-limiter `max_queue_size` + alerts
- [ ] Secrets manager for prod
- [ ] Observability counters for errors/fallbacks

Phase 4 (Weeks 3–4)
- [ ] Prompt-injection scrub + channel blocklist
- [ ] Audit logging (rotating, 600 perms)
- [ ] Metrics + alerting thresholds
- [ ] Data encryption or DB migration
- [ ] IR runbook + quarterly review

---

Version: 1.0 (Unified from SECURITY_C_PLAN.md + SECURITY_CC_PLAN.md)
