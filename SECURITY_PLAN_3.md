# Phase 3 Detailed Execution Plan (Week 2)

All subtasks are scoped to ≤1.5 hours and include explicit deliverables for quick verification. Adjust owners to match current staffing.

## AI Usage Hardening Track

- **1. Validate current Gemini quotas** (≈1h, Owner: AI Lead)  
  - Pull existing `GEMINI_CONCURRENT_LIMIT` and RPM settings; compare with provider quotas.  
  - Document safe baseline limits and store notes in `docs/SECURITY_NOTES_PHASE3.md`.

- **2. Implement lower concurrency defaults** (≈1h, Owner: Backend)  
  - Update config to set `GEMINI_CONCURRENT_LIMIT` ≈16 and enforce via semaphore in `bot/services/ai.py`.  
  - Run targeted tests to confirm saturation behavior.  
  - Deliverable: code change + test output snippet.

- **3. Add RPM throttling guard** (≈1.5h, Owner: Backend)  
  - Introduce sliding-window counter per command/AI request (e.g., deque timestamps) in `bot/services/ai.py`.  
  - Include unit test covering limit breach.  
  - Deliverable: new tests passing locally.

- **4. Re-enable Gemini safety toggles** (≈1h, Owner: AI Lead)  
  - Ensure API client enforces toxicity/abuse filters; surface config flag for incident overrides.  
  - Provide documentation snippet describing override workflow.  
  - Deliverable: updated `docs/AI_SAFETY.md`.

- **5. Add AI failure instrumentation** (≈1h, Owner: Backend)  
  - Emit structured log/metric on exceptions, including response code and latency bucket.  
  - Confirm metrics integrate with existing Prometheus helper (prep for later tasks).  
  - Deliverable: screenshot/log showing metric increment.

## Rate Limiting & Queue Safety Track

- **6. Introduce per-user embedding throttle** (≈1h, Owner: Backend)  
  - Add per-user rate limiter (100 req/min default) in `bot/services/ai.py`.  
  - Write unit test verifying limiter blocks excess calls.  
  - Deliverable: test report attached to notes.

- **7. Apply global embedding cap** (≈1h, Owner: Backend)  
  - Add global semaphore (e.g., max 5 concurrent) for embedding operations.  
  - Update integration test to cover saturation.  
  - Deliverable: updated test ensures queue fallback triggers.

- **8. Gate scraper concurrency** (≈1h, Owner: Backend)  
  - Implement `asyncio.Semaphore` around network fetch in `bot/services/scraper.py` with max 5 concurrent.  
  - Include warning log when queue backs up.  
  - Deliverable: log sample in notes.

- **9. Enforce scraper RPM limit** (≈1.5h, Owner: Backend)  
  - Add rolling 60 scrapes/minute cap with delay/backoff.  
  - Create regression test simulating burst traffic.  
  - Deliverable: passing test evidence.

- **10. Propagate rate-limit errors to client** (≈1h, Owner: Backend)  
  - Standardize exception handling so Telegram replies show friendly rate-limit messaging.  
  - Verify via manual bot interaction in staging.  
  - Deliverable: screenshot of bot response.

- **11. Update rate limiter module docs** (≈1h, Owner: Tech Writer)  
  - Extend `docs/SECURITY_NOTES_PHASE3.md` with architecture diagrams or pseudo-code describing new limits.  
  - Ensure on-call playbook references these thresholds.  
  - Deliverable: committed doc update.

## Secrets Manager Integration Track

- **12. Evaluate candidate secret stores** (≈1h, Owner: DevOps)  
  - Compare AWS Secrets Manager vs. Azure Key Vault vs. HashiCorp Vault; capture pros/cons with existing infra.  
  - Document recommendation and migration timeline.  
  - Deliverable: decision log in docs folder.

- **13. Prototype local secrets adapter** (≈1.5h, Owner: DevOps)  
  - Implement `bot/utils/secrets.py` with interface supporting `.env` (legacy) and cloud provider (stub).  
  - Ensure module falls back safely during migrations.  
  - Deliverable: new module + unit tests for both backends.

- **14. Wire adapter into configuration loading** (≈1h, Owner: Backend)  
  - Replace direct `os.getenv` calls in config entrypoint with secrets adapter.  
  - Verify bot startup under both `.env` and stub cloud mode.  
  - Deliverable: startup logs confirming values resolved.

- **15. Draft migration checklist for production** (≈1h, Owner: DevOps)  
  - Outline steps to move prod `.env` values into chosen secret manager, including validation and rollback.  
  - Share with operations team for review.  
  - Deliverable: checklist in `docs/SECURITY_NOTES_PHASE3.md`.

## Observability & Alerts Track

- **16. Implement metrics module skeleton** (≈1h, Owner: Backend)  
  - Create `bot/utils/metrics.py` exposing Prometheus counters/gauges for `news_requests_total`, `rate_limit_breaches`, `ai_failures`, `request_duration`, `queue_depth`.  
  - Provide no-op fallback when Prometheus client not installed.  
  - Deliverable: module with docstring usage examples.

- **17. Instrument key code paths** (≈1.5h, Owner: Backend)  
  - Hook metrics into `/news` handler, rate limiter, AI client, and queue manager.  
  - Ensure labels adhere to naming conventions.  
  - Deliverable: diff showing instrumentation + smoke test demonstrating metric increments.

- **18. Expose metrics endpoint** (≈1h, Owner: Backend)  
  - Add HTTP endpoint (e.g., `GET /metrics`) via existing web server or lightweight FastAPI/Quart setup.  
  - Confirm endpoint is guarded by auth token or IP allowlist.  
  - Deliverable: curl output snippet in notes.

- **19. Define alert thresholds** (≈1h, Owner: Security Lead)  
  - Translate plan thresholds (AI failures >5%, queue >5000, worst delay >1m, rate-limit breaches >100/min) into Prometheus alert rules.  
  - Store rule files under `monitoring/alerts/`.  
  - Deliverable: committed YAML + rationale.

- **20. Test alert pipeline** (≈1h, Owner: DevOps)  
  - Use dummy metrics or `promtool` to simulate threshold breach; ensure alerts fire and notify designated channel.  
  - Document verification steps.  
  - Deliverable: test log and screenshot of alert notification.

## Close-Out

- **21. Phase 3 verification run** (≈1h, Owner: QA)  
  - Execute full automated test suite plus targeted load tests for AI/scraper throttles.  
  - Summarize findings and next steps.  
  - Deliverable: report appended to `docs/SECURITY_NOTES_PHASE3.md`.

- **22. Stakeholder sign-off meeting** (≈1h, Owner: Security Lead)  
  - Review checklist, confirm alerting/limits operational, and plan Phase 4 kickoff.  
  - Capture decisions and outstanding risks.  
  - Deliverable: meeting minutes stored with other Phase 3 docs.

