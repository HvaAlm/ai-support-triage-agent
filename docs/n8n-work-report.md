# n8n Work Report

**Project:** AI Support Triage Agent  
**Reporting period:** 16 September–18 October 2026  
**Prepared:** 18 October 2026

## Scope and records

Available project-task history begins around 26 September 2026; no n8n-specific records for 16–25 September were available. This report summarizes the n8n work that can be supported by the task history and repository documentation. The repository has only its initial Git commit, so this is not a complete commit-by-commit history.

## Workflow development

- Developed the `Datami — Support Intake & Triage` workflow for Persian support reports received through Telegram.
- Added feature-catalog preparation and intake processing for aspect sentiment analysis, abstraction/summarization, and plot description.
- Added structured intake output with statuses including `NEED_MORE_INFO`, `UNKNOWN_FEATURE`, and `READY_FOR_REVIEW`, plus a rule-based validation step under development.
- Saved the model prompt and output schema in `workflows/intake/`.
- Kept the investigation readiness flag false while persistent case storage and readiness routing remained incomplete.
- Added separate manual-check workflows for replaying sample intake data and evaluating model output.

## Runner configuration and verification

- Configured external n8n task runners at version 2.37.10 through Docker Compose, reusing the existing PostgreSQL and n8n volumes.
- Kept the runner broker on the Compose network and mounted `n8n-task-runners.json` read-only. The runner configuration allows Python's standard-library `json` module without enabling external Python packages.
- On 30 September, documented a successful Python (Native) runner check and a preparation-workflow replay using a read-only snapshot of three catalog rows. The replay verified three feature keys and normalization of Telegram sender/chat IDs and catalog list fields.
- The documented preparation check stopped before the LLM, Telegram send, or Jira creation. It used a catalog snapshot because `n8n execute` did not initialize the Data Table module in n8n 2.37.10; it did not verify a fresh Telegram webhook or the live Data Table node in the editor.
- Later local checks covered the structured-output schema and node connections. The documented model-evaluation workflow contains synthetic Persian examples, but its live model execution was still pending authorization in the available notes.

## Testing and troubleshooting

The project task history records work on feature-catalog discovery and formatting, source-excerpt validation, workflow connections, intake validation, and abstraction-analysis testing. A recorded abstraction test used a separate case, corrected the customer ID in that case, and reported successful executions 186 and 187. The test was simulated through incoming messages; the model, validation, storage, and Telegram replies were exercised, while investigation remained disabled.

Some workflow tests relied on isolated fixtures or a temporary runner. The task record says the temporary test runner was removed after the test. The standard external runner remained configured for editor executions.

## Migration preparation

On 7 October, a migration bundle was prepared to move the n8n setup to another device. The task record says it included PostgreSQL and n8n data backups, exports of seven workflows and four encrypted credentials, a portable Compose configuration, project files, and restore instructions. The encryption key was checked against the running container during preparation. The archive contains sensitive operational data and should be handled privately.

## Current documented state and open items

- The 7 October workflow export is inactive. It connects intake through validation, support-case upsert, and Telegram reply; its `If`, static Python fixture, and platform-mapping nodes are disconnected.
- The documented model evaluation has not run live; no successful model evaluation is claimed. Sending the internal catalog to the configured model endpoint remains pending explicit authorization.
- The CLI-based preparation check does not substitute for checking the current Data Table node or a real Telegram webhook in the editor.
- Docker access was unavailable while preparing this follow-up, so the live n8n instance could not be inspected. The repository now contains the dated workflow snapshot, with its standalone prompt and schema synchronized to the exported nodes.
- The repository README says the Python application does not use n8n; n8n workflows and runner setup are retained as project artifacts.

## References

- [n8n task-runner and intake verification notes](n8n-task-runners.md)
- [Intake system prompt](../workflows/intake/system-prompt.txt)
- [Intake output schema](../workflows/intake/output-schema.json)
- [Docker Compose configuration](../docker-compose.yaml)
- [Task-runner configuration](../n8n-task-runners.json)
