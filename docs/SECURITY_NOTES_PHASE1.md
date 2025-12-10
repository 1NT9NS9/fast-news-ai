# Phase 1 Security Notes - KeyTime Bot

Last Updated: 2025-10-21
Owner: Security Task Force
Related Plan: `SECURITY_PLAN.md` (Phase 1)

## Summary
- Secrets rotated (Telegram bot token, Gemini API key) with a fresh `.env` snapshot stored under `backups/`.
- SSRF and channel validation enforced through `bot/utils/validators.py`, `bot/services/scraper.py`, and `bot/handlers/manage.py`.
- Backup restoration hardened against path traversal in `bot/services/storage.py` with supporting unit tests.
- Logger sanitization deployed: outbound logs redact API keys and tokens and send through the rate-limited messenger wrapper.
- Dependency audit executed; protobuf and requests upgrades deferred until compatibility fixes land (tracked in Phase 2 backlog).

## Operator Guidance
- **Secret Hygiene:** Keep the latest `.env` backup encrypted at rest. If rotation is required again, reuse the procedure in `backups/README` or follow Steps 2-4 from `SECURITY_PLAN_1.md`.
- **Validators:** Invalid channel IDs now raise `ValueError`. Store canonical `@channel` identifiers. In emergencies you can set `ENABLE_SSRF_PROTECTION=false` before restarting, but restore it to `true` immediately afterward.
- **Safe Restore:** Only files named `user_data_YYYYMMDD_HHMMSS.json` inside `backups/` are accepted. If restore fails, inspect logs for `Rejected backup path` entries and confirm the filename pattern.
- **Logging:** Sanitization filters run automatically. Use structured fields for debugging; secrets placed in log messages are redacted.

## Rollback Pointers
1. Stop the bot (`docker stop keytime-bot` or `pkill -f bot.py`).
2. Restore code and data:
   - `git revert <commit>` or checkout the prior tag or commit.
   - Copy the desired `backups/user_data_*.json` to `user_data.json`.
   - Copy the matching `backups/env_backup_*.txt` to `.env`.
3. Reinstall dependencies (`pip install -r requirements.txt`) and restart (`python bot.py`).
4. Rotate secrets again after rollback to avoid reusing revoked tokens or keys.

## Deferred Items
- **Protobuf and requests upgrade:** Upstream google client pins require additional testing; revisit under Phase 2 in `SECURITY_PLAN.md`.
- **Logger file permission hardening:** POSIX `0o600` enforcement broke Windows execution; add platform-aware guards in Phase 2.

## Verification Checklist (Completed)
- `pytest` suites for validators and storage restore pass locally.
- Manual `/news` smoke test confirms validator behavior and sanitized logging.
- `pip-audit` executed with no remaining critical findings in Phase 1 scope.
