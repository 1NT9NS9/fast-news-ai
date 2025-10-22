# Phase 4 Detailed Execution Plan (Weeks 3–4)

Subtasks are scoped to ≤1.5 hours, enabling incremental delivery and quick verification. Adjust owners based on availability.

## Prompt-Injection Defense & Channel Controls

- **1. Catalogue existing prompt entry points** (≈1h, Owner: AI Lead)  
  - List commands/features sending user text to LLM; record context templates.  
  - Store findings in `docs/SECURITY_NOTES_PHASE4.md`.

- **2. Draft prompt sanitization rules** (≈1h, Owner: AI Lead)  
  - Define regex/heuristics for URL bait, system override phrases, embedded commands.  
  - Document acceptance criteria for downstream filters.  
  - Deliverable: spec section appended to notes.

- **3. Implement sanitizer helper** (≈1h, Owner: Backend)  
  - Add `bot/utils/prompt_guard.py` with `sanitize_prompt()` and list of disallowed patterns.  
  - Include unit tests covering allow/deny scenarios.  
  - Deliverable: module + passing tests.

- **4. Integrate sanitizer into AI workflows** (≈1.5h, Owner: Backend)  
  - Invoke guard before each Gemini request; log redactions.  
  - Ensure friendly user messaging when content is blocked.  
  - Deliverable: integration diff + manual validation screenshot.

- **5. Establish channel blocklist pipeline** (≈1h, Owner: Backend)  
  - Create persistent blocklist store (JSON or config) with helper functions to check membership.  
  - Add admin commands to view/update blocklist with audit logging hook.  
  - Deliverable: helper module + admin handler tests.

- **6. Populate initial blocklist** (≈1h, Owner: Security Lead)  
  - Seed with known malicious channels from incident logs; capture rationale.  
  - Deliverable: blocklist file committed + notes.

- **7. Create prompt-injection regression tests** (≈1.5h, Owner: QA)  
  - Add tests simulating injection attempts; assert sanitizer blocks and logs event.  
  - Deliverable: new test module with green run.

## Audit Logging & Forensics

- **8. Implement audit logger module** (≈1h, Owner: Backend)  
  - Create `bot/utils/audit.py` with rotating `RotatingFileHandler`, 10MB, 10 backups, mode 0600.  
  - Expose `log_admin_action()` and `log_unauthorized_access()`.  
  - Deliverable: module with docstring usage guidelines.

- **9. Wire audit logging into admin endpoints** (≈1.5h, Owner: Backend)  
  - Instrument admin handlers (add/remove channel, blocklist updates, config changes).  
  - Add coverage tests ensuring audit entries emitted.  
  - Deliverable: diff + test evidence.

- **10. Secure audit log permissions** (≈1h, Owner: DevOps)  
  - On startup ensure `bot_audit.log` created with 0600; verify in Docker container.  
  - Document cross-platform considerations.  
  - Deliverable: permission check output stored in notes.

- **11. Build forensic extraction script** (≈1h, Owner: DevOps)  
  - Add script under `tools/collect_audit_logs.py` packaging logs with checksum for incident response.  
  - Provide usage instructions.  
  - Deliverable: script + README snippet.

- **12. Document audit retention policy** (≈1h, Owner: Security Lead)  
  - Define retention duration, rotation cadence, archival path, and access controls.  
  - Deliverable: policy page within docs.

## Metrics, Alerts & Monitoring

- **13. Finalize Prometheus exporter integration** (≈1h, Owner: Backend)  
  - Review Phase 3 metrics; ensure namespace/labels match Prometheus standards.  
  - Add configuration flag to enable/disable exporter.  
  - Deliverable: configuration diff + smoke test.

- **14. Add alert rule files** (≈1h, Owner: DevOps)  
  - Translate thresholds into `monitoring/alerts/*.yaml`; include annotations for runbooks.  
  - Validate syntax with `promtool check rules`.  
  - Deliverable: committed YAML + validation output.

- **15. Hook alerts into notification channel** (≈1.5h, Owner: DevOps)  
  - Configure Alertmanager route to Slack/Teams/email; verify authentication tokens stored securely.  
  - Deliverable: configuration snippet + successful test alert evidence.

- **16. Expand monitoring runbook** (≈1h, Owner: Tech Writer)  
  - Update runbook with steps for interpreting metrics, acknowledging alerts, and escalation sequence.  
  - Deliverable: runbook section committed in docs.

## Data Protection & Runbooks

- **17. Encrypt JSON persistence** (≈1.5h, Owner: Backend)  
  - Integrate `cryptography.Fernet` using `DATA_ENCRYPTION_KEY`; handle key errors gracefully.  
  - Provide migration path for existing plaintext files.  
  - Deliverable: code changes + migration instructions.

- **18. Verify encryption works end-to-end** (≈1h, Owner: QA)  
  - Write tests ensuring saved files decrypt correctly and tampering is detected.  
  - Deliverable: test results appended to notes.

- **19. Review backup rotation & encryption** (≈1h, Owner: DevOps)  
  - Confirm backups use same encryption; adjust cron/rotation scripts to purge old plaintext.  
  - Deliverable: updated scripts + verification logs.

- **20. Draft full incident response runbook** (≈1.5h, Owner: Security Lead)  
  - Cover detection, containment, eradication, recovery, and postmortem for security incidents.  
  - Include contact matrix and communication templates.  
  - Deliverable: runbook in `docs/IR_RUNBOOK.md`.

- **21. Schedule quarterly security reviews** (≈1h, Owner: Security Lead)  
  - Create calendar invites/tasks for next four quarters; outline agenda.  
  - Deliverable: summary log added to notes and shared with stakeholders.

## Close-Out

- **22. Phase 4 verification pass** (≈1h, Owner: QA)  
  - Execute regression suite, security scanners, and manual validation of prompt guard + encryption.  
  - Deliverable: final report stored in docs.

- **23. Executive sign-off & handover** (≈1h, Owner: Security Lead)  
  - Present results to leadership, archive plan artifacts, and transition to maintenance cadence.  
  - Deliverable: sign-off memo filed with security documentation.

