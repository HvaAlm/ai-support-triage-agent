# Application architecture

## Components

- `config.py`: validated process configuration, mock/live selection, interface settings.
- `scenarios.py`: deterministic Persian feature classification and scenario questionnaires. Ambiguous reports require an explicit choice. Supported features are `aspect_sentiment_analysis` and `abstraction_analysis` (summarization).
- `application.py`: the shared case workflow, answer correction, photos, investigations, ticket preview, and confirmation.
- `store.py`: SQLite conversations, active cases, optimistic versions, feature references, Telegram update reservations/responses/offsets.
- `gitlab.py`: project-scoped read-only retrieval, default-branch/ref resolution, commit-pinned file access, exclusion rules, credential isolation, and budgets.
- `investigation.py`: clearly labeled mock output or Codex CLI analysis in a temporary read-only snapshot, with schema and source-citation validation.
- `publication.py`: the existing small publisher protocol, durable drafts, owner/revision checks, attempt reservations, and issue mapping.
- `skill_publisher.py`: a thin subprocess adapter to the existing `jira-create-issue` CLI. No application Jira REST/auth implementation.
- `telegram.py` and `__main__.py`: interface adapters. Neither contains independent triage business logic.

Python orchestrates everything. The existing n8n scaffold remains separate and is not needed to run the application.

## Case flow

A report starts a persistent case owned by the interface's authenticated/local identity. An unambiguous keyword classification selects the feature; otherwise the user chooses. The user selects a scenario, then supplies sample input, actual output, scenario-specific expected behavior/error details, reproduction, environment/time, and request ID or an explicit unknown.

Once questions are answered, `/investigate` performs read-only analysis. `/preview` serializes all user observations and findings into the ticket's description. Facts, hypotheses, proposed fixes, and limitations have separate sections. An attachment manifest is part of the confirmed draft. `/confirm CASE_ID REVISION` approves that exact persisted version.

Conversation updates use optimistic versions and invalidate an unattempted preview transactionally. Preview creation checks the same session version under a SQLite write transaction. Confirmation checks ownership/revision and reserves the attempt before external work. This prevents stale or simultaneous confirmation from invoking creation twice. Cases and publication records share one SQLite database.

Answers can be corrected with `/answer`; this invalidates the investigation and preview. Photos invalidate the preview but are never interpreted or passed to Codex. An attempted case is locked, including dry-run/pending outcomes. There is intentionally no automatic publication retry or reconciliation interface in this MVP.

## GitLab retrieval

The configured project path is resolved through `/api/v4/projects/<encoded path>`. The response's `path_with_namespace` must match configuration. The selected ref (or discovered `default_branch`) is resolved to a SHA through the commits endpoint. Directory and raw file requests always include that SHA.

All requests are GET, scoped to the configured project endpoint, and refuse redirects. The token is a request header held by the retrieval object, never part of a URL, prompt, logged exception, stored case, or child environment. Errors are sanitized to useful status/limitation messages.

Tree pagination, total request/time/file/byte budgets, file-type filters, symlink exclusions, and secret/dependency/generated/frontend exclusions bound access. The tree can be partial; this is reported. Relevant documentation, matching paths, and a bounded fallback of backend route/service/model paths are inspected. Actual source references are recorded in the feature catalog with line evidence and SHA. The catalog records observed references, not unsupported architectural ownership claims. No verified entries exist before successful repository access.

Only the filtered temporary snapshot and its metadata reach Codex. No full clone or existing backend checkout is required. The source cache is removed after inspection. The application repository is never used as a backend substitute.

## Codex contract

The existing ChatGPT login is checked with `codex login status`. An API-key login is not accepted. `codex exec` runs with `read-only`, `approval_policy="never"`, `--ignore-user-config`, and `--ephemeral`. Apps, plugins, hooks, MCP servers, and project instructions are disabled for the child. The environment is restricted to ordinary process variables and the existing login location, excluding GitLab/Jira/Telegram/API tokens.

The investigator receives the report, answers, selected feature/scenario, source snapshot, and commit metadata. It is instructed to treat report/source text as untrusted data, not execute project code, not investigate frontend behavior, not create tickets, and not apply fixes. There are no images or attachment bytes in the prompt.

Schema validation requires exact source path/line/quotation evidence. Paths must be inside the retrieved snapshot, quotations must match source lines, and hypotheses must reference valid evidence indices with low/medium confidence and a verification step. Evidence hashes and commit SHA are persisted. This verifies quotations, not the semantic correctness of every inference or the runtime root cause. Insufficient evidence must remain a limitation.

Mock mode does not invoke GitLab or Codex and returns no invented code facts/hypotheses. Live failures never switch into mock mode. Read-only investigation may be repeated; publication may not.

## Jira skill integration

The supplied `agent/skills/jira-create-issue/SKILL.md` v1.1.0 documents the concrete `agent/skills/jira/scripts/jira_tool.py create_issue` command. Its help and implementation were inspected. Required fields are project, summary, and issue type; optional fields include description, parent, labels, assignee, priority, components, and verified custom fields. The adapter maps title to summary and forwards supported fields only.

The application passes `--confirm` only after owner approval of the current preview. A successful result requires `confirmed: true`, `issue.key`, and `issue.url`; the key and URL are persisted verbatim. A declined confirmation remains pending. Exceptions, malformed output, errors, and incomplete success remain unknown and are not automatically retried. Partial-success keys/URLs are retained when present.

The skill's default HTTP retry policy includes POST. Its existing `JIRA_MAX_RETRIES=0` setting disables ambiguous creation retries in this invocation. No duplicate-detection/correlation parameter is invented. Authentication stays with the supplied skill runtime. Only its `JIRA_*` environment and ordinary process variables are forwarded.

There is no attachment-upload operation in the supplied tool registry. Drafts with photos return pending before creation and remain available for manual handoff. Adding support requires a documented capability in the existing skills; this app must not implement a second Jira upload client. An interactive-only future skill also requires manual handoff, not an unattended success claim.

## Telegram and recovery

Only private chats from configured numeric user IDs are accepted. The sender ID determines ownership; IDs embedded in report text cannot impersonate another owner. CLI ownership uses the local username in a separate identity namespace.

Each Telegram update is reserved before domain work. Responses are saved before delivery, and the polling offset advances only after delivery (or deliberate rejection of unauthorised/unsupported update types). A failed send reuses the response without repeating domain actions. An interrupted reservation requires `/status` instead of blind replay. Duplicate replies after a crash are possible; duplicate publication is guarded independently.

This MVP uses one polling process and serial investigations. Multi-worker scheduling, account linking, automated reconciliation, retention policies, frontend/media interpretation, and automatic fixes are not implemented.
