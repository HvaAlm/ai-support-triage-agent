# Project Work Report

**Project:** AI Support Triage Agent  
**Reporting period:** 16 September–18 October 2026  
**Prepared:** 18 October 2026

## Scope and source of this report

The available repository and Codex task records show substantial project work beginning around 26 September 2026. No project commits or project-task history dated 16–25 September were available, so activity during those dates cannot be reliably reconstructed.

The repository has only its initial Git commit; the implementation is currently present as uncommitted working-tree changes. This report therefore uses project documentation, file dates, and available task history rather than a complete commit-by-commit record.

## Executive summary

The project developed into a Python MVP for triaging Persian-language support reports. A local CLI and Telegram interface share a SQLite-backed case workflow. The system can collect and classify a report, ask scenario-specific follow-up questions, retrieve a bounded backend source snapshot from GitLab, request a read-only Codex investigation, and prepare a Jira ticket preview for owner review.

Ticket creation is separated from investigation and requires explicit confirmation of the current preview. Offline mock mode and dry-run publication are available for local use. Existing n8n files were retained, but the Python application does not depend on n8n.

## Work completed

### Support intake and case handling

- Implemented Persian intake for aspect sentiment analysis and text summarization/abstraction reports.
- Added deterministic feature classification and scenario-specific follow-up questions.
- Built shared application logic for the CLI and Telegram, backed by SQLite.
- Persisted cases, conversation history, answers, active-case selection, revisions, attachments, Telegram update state, and publication results.
- Added owner checks and stale-preview protection.

### Backend investigation

- Added bounded, authenticated GitLab retrieval for a configured project and ref.
- Resolved the selected ref to a commit SHA and used that SHA for source reads.
- Added limits on requests, files, file size, total source size, and retrieval time; excluded sensitive and irrelevant paths.
- Integrated Codex CLI in read-only mode using structured output and retrieved source snapshots.
- Validated source quotations against exact file lines and kept user reports, evidence, hypotheses, and suggested fixes distinct.
- Explicitly surfaced missing access, retrieval errors, invalid results, and timeouts instead of silently falling back to mock findings.

### Ticket preparation and publication safeguards

- Added a reviewable ticket preview and confirmation tied to the current owner and revision.
- Reserved publication attempts durably to protect against concurrent or repeated submissions.
- Reused the existing Jira skill CLI rather than adding a separate Jira API or authentication client.
- Saved only actual issue keys and URLs returned by the skill; dry-run mode does not invent Jira results.
- Kept uncertain publication outcomes available for reconciliation and prevented automatic duplicate retries.
- Routed cases with photo attachments to manual handoff because the existing skill does not support photo uploads.

### Interfaces, configuration, and documentation

- Added a local CLI and Telegram polling interface with allowlisted private-chat access.
- Added opaque photo attachment handling; photo contents are not sent for image interpretation.
- Added packaging, configuration examples, installation instructions, architecture documentation, and n8n task-runner documentation.
- Preserved the existing n8n files while documenting that they are not used by the Python application.

## Timeline from available records

| Period | Recorded work |
| --- | --- |
| 16–25 September | No project-task history or commits were available to confirm activity. |
| Around 26 September | The project task history begins. Work included an n8n support-intake flow, feature-catalog discovery, intake validation, and scenario-based reporting. An abstraction-analysis test was recorded, including a customer-ID correction in a saved case. |
| Late September | The repository documents a standalone Python application with CLI and Telegram intake, SQLite persistence, bounded GitLab retrieval, read-only Codex investigation, and Jira skill publication. |
| 30 September | n8n task-runner configuration and documentation, plus workflow-intake files, were updated. |
| 3–5 October | The task history records n8n workflow and feature-catalog debugging and testing. |
| 7 October | A migration bundle was prepared for moving the n8n setup to another device. Its manifest records database and n8n data backups, workflow and encrypted-credential exports, project files, and restore instructions. |

## Verification recorded in project documentation

The implementation report records:

- **45 automated tests passed** using `python3 -m unittest discover -s tests -q`.
- `python3 -m compileall -q triage` passed.
- Editable installation in a temporary virtual environment passed.
- The installed `support-triage` command and offline case-creation path were exercised.
- Tests covered both supported feature types, all eight scenarios, persistence and restarts, ownership checks, stale confirmations, concurrent publication, attachments, GitLab limits and pinning, evidence validation, Codex invocation isolation, Telegram redelivery, and the Jira adapter with fake results.

These results are documented in [`docs/implementation-report.md`](implementation-report.md). They describe local and automated verification, not successful live operation against external accounts.

## Outstanding verification and limitations

- Live GitLab retrieval was not verified because the report records that `GITLAB_READ_TOKEN` was unavailable. Backend feature paths should not be treated as verified until a live retrieval succeeds.
- Telegram transport was not exercised against a live bot account because a bot token was unavailable.
- Jira issue creation was not exercised against a live account. The implementation report states that no Jira issue was created during implementation.
- Photo-bearing drafts require manual handoff because the supplied Jira skill has no attachment-upload operation.
- Source search is bounded and may not find every relevant file. A verified source quotation establishes what the file contains, but does not by itself prove runtime causality.
- Publication retries, administrative reconciliation, promotion of attempted dry-run cases, and parallel Telegram investigation are not implemented.

## Project references

- [README](../README.md) — setup, usage, configuration, interfaces, and operational limits.
- [Architecture](architecture.md) — system design and workflow boundaries.
- [Implementation and verification report](implementation-report.md) — implementation summary and recorded checks.
- [n8n task-runner notes](n8n-task-runners.md) — n8n runner setup documentation.
