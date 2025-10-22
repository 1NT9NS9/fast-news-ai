# Phase 2 Detailed Execution Plan (Week 1)

Each subtask below is scoped to ≤1.5 hours and can be scheduled independently unless a prerequisite is stated. Owners are suggestions; adjust as needed.

## Concurrency & Data Integrity Track

- **1. Inventory StorageService usage** (≈1h, Owner: Backend)  
  - Enumerate every import/instantiation of `StorageService` across `bot/services`, `bot/handlers`, and tests.  
  - Produce a checklist of call sites that must migrate to the singleton factory.  
  - Deliverable: short note in `docs/SECURITY_NOTES_PHASE2.md` listing files and findings.

- **2. Introduce singleton factory skeleton** (≈1h, Owner: Backend)  
  - Add `get_storage_service()` in `bot/services/storage.py` returning a module-scoped instance with async locks for file access.  
  - Provide temporary shim so legacy direct instantiation keeps working (logged deprecation).  
  - Deliverable: updated module with TODO markers for follow-up removal of direct instantiation.

- **3. Migrate core call sites to singleton** (≈1.5h, Owner: Backend)  
  - Update bot startup, `/news` handler, and scheduler jobs to use `get_storage_service()`.  
  - Run unit tests touching storage to confirm no regressions.  
  - Deliverable: passing tests + checklist updates.

- **4. Harden StorageService locking** (≈1h, Owner: Backend)  
  - Wrap read/write/delete paths with `asyncio.Lock` or `asyncio.Semaphore` shared across the singleton.  
  - Document lock coverage comments for future maintainers.  
  - Deliverable: code comments + verified lock acquisition order (no deadlock).

- **5. Extend concurrency tests** (≈1.5h, Owner: QA)  
  - Create `tests/test_concurrency_storage.py` simulating ≥10 concurrent `/news` requests via `anyio` or `pytest-asyncio`.  
  - Assert channel lists, counters, and file snapshots remain consistent.  
  - Deliverable: new test module and green test run.

- **6. Instrument `/news` rate-limit breach logging** (≈1h, Owner: Backend)  
  - Add structured log/metric emission on rate-limit failures, using existing logger/metrics helpers.  
  - Update tests to assert log entry presence when breaches occur.  
  - Deliverable: log format documented in `docs/monitoring.md`.

- **7. Verification sweep** (≈1h, Owner: Backend)  
  - Run full test suite; spot-check `/news` manually under concurrent load (e.g., `locust` or custom script).  
  - File any follow-up issues discovered during manual testing.  
  - Deliverable: test results posted in project channel.

## Docker & Runtime Posture Track

- **8. Add non-root user to Dockerfile** (≈1h, Owner: DevOps)  
  - Create `botuser` group/user, adjust ownership of app directories, switch to `USER botuser`.  
  - Build local image and confirm `whoami == botuser`.  
  - Deliverable: Dockerfile diff + `docker run --rm image whoami` screenshot/log.

- **9. Define Docker HEALTHCHECK** (≈1h, Owner: DevOps)  
  - Implement script or command invoking bot liveness endpoint/startup ping.  
  - Ensure health check respects <30s timeout and 30s interval.  
  - Deliverable: documented command and successful `docker inspect --format='{{json .State.Health}}'`.

- **10. Enforce runtime file permissions** (≈1h, Owner: DevOps)  
  - Ensure `data/` and `backups/` directories are created with `0700`; adjust entrypoint if needed.  
  - Confirm permissions via container run; capture evidence.  
  - Deliverable: permission check output stored in `docs/SECURITY_NOTES_PHASE2.md`.

- **11. Update .dockerignore hygiene** (≈1h, Owner: DevOps)  
  - Exclude `.env`, local logs, dumps, virtualenvs, Git metadata.  
  - Validate build context size reduction (`docker build --no-cache` timing).  
  - Deliverable: refreshed `.dockerignore` with rationale comment header.

## CI & Dependency Hygiene Track

- **12. Split prod/dev requirements** (≈1h, Owner: Backend)  
  - Create `requirements-prod.txt` (runtime) and `requirements-dev.txt` (extends prod).  
  - Update local docs for new install commands.  
  - Deliverable: requirements files + `README` snippet.

- **13. Align Dockerfile with prod requirements** (≈1h, Owner: DevOps)  
  - Modify Docker build to install from `requirements-prod.txt`.  
  - Verify image builds and application starts without dev-only deps.  
  - Deliverable: build log excerpt included in notes.

- **14. Pin HTTP client dependency** (≈1h, Owner: Backend)  
  - Evaluate `requests` usage; either pin to latest secure patch or refactor to async client reuse.  
  - Update dependency files and run smoke tests.  
  - Deliverable: change rationale recorded in commit message and notes.

- **15. Integrate pip-audit & bandit into CI** (≈1.5h, Owner: DevOps)  
  - Update CI pipeline (GitHub Actions or equivalent) to add dedicated jobs failing on high severity findings.  
  - Add caching to keep runtime within acceptable bounds.  
  - Deliverable: CI config diff and successful run screenshot/log.

- **16. Configure dependency monitoring bot** (≈1h, Owner: DevOps)  
  - Enable Dependabot or Renovate with weekly schedule; restrict auto-merge; set security severity ≥high.  
  - Test by triggering a dummy PR or dry run.  
  - Deliverable: configuration file committed + confirmation note from service.

- **17. Document developer workflow updates** (≈1h, Owner: Tech Writer)  
  - Update `CONTRIBUTING.md` with new install commands, CI expectations, and dependency update flow.  
  - Notify team via project channel with summary of changes.  
  - Deliverable: merged doc updates + announcement draft.

## Cross-Track Coordination

- **18. Phase 2 retrospective & sign-off** (≈1h, Owner: Security Lead)  
  - Review deliverables, confirm checklist completion, and capture lessons learned.  
  - Update SECURITY_PLAN.md status for Phase 2 and queue Phase 3 kickoff tasks.  
  - Deliverable: meeting notes stored in `docs/SECURITY_NOTES_PHASE2.md`.

