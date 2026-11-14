# MVP implementation and verification

## Implemented

- Python orchestration independent of n8n, with shared local CLI and Telegram application logic.
- SQLite cases, conversation history/answers, active case selection, optimistic revisions, feature references, Telegram offsets/update responses, and Jira mappings.
- Persian intake and scenario-based follow-ups for aspect sentiment analysis and summarization/abstraction. Classification is deterministic; ambiguous input prompts a choice.
- Bounded authenticated GitLab GET retrieval from the configured project, discovered default branch, and a fixed commit SHA for every source read. No local backend checkout or full clone.
- Read-only Codex CLI investigation using the existing ChatGPT login, filtered source snapshots, structured output, and validated path/line quotations. Facts, suspected causes, verification steps, and proposed fixes remain distinct.
- Explicit ticket preview/current-owner confirmation, durable creation reservation, duplicate protection, and preservation after errors.
- Existing Jira skill CLI reuse with actual returned key/URL; no new Jira HTTP/auth implementation.
- Fully offline mock CLI and clearly labeled dry-run publication with no synthetic Jira result or fabricated backend evidence.
- Photos retained only as opaque attachments; unsupported media and automatic fixes excluded.
- Configuration, packaging, installation/run instructions, architecture documentation, and automated tests.

## Verification

- `python3 -m unittest discover -s tests -q`: **45 tests passed**.
- `python3 -m compileall -q triage`: passed.
- Editable installation in a temporary virtual environment: passed.
- Installed `support-triage` command help and offline case creation: passed.
- Whitespace checks for the implementation files: passed.

Automated tests cover both features and all eight scenarios, restarts, conversation ownership, stale preview rejection, concurrent publication, ambiguous outcomes, attachment preservation, GitLab project identity/default-ref/SHA behavior, limits and credential exclusions, evidence rejection, Codex invocation isolation, Telegram redelivery, and the Jira skill adapter with fake results. The CLI end-to-end test launches separate real Python processes from report through dry-run confirmation and verifies persisted state.

The installed Codex CLI exposes the required noninteractive/read-only/structured-output flags. `codex login status` reports an existing ChatGPT login. The provided Jira creation CLI help runs locally. These checks do not prove a live investigation or a successful Jira creation.

## Live verification pending

`GITLAB_READ_TOKEN` and `TELEGRAM_BOT_TOKEN` were not configured in the execution environment. The backend's feature paths and live project access therefore remain unverified, and no verified backend catalog entries are fabricated. A live Codex investigation on the requested GitLab repository has not been run. Telegram transport and Jira account creation have not been exercised against live accounts. No Jira issue was created during implementation.

Configure read-only GitLab access, Telegram token/allowlist, and the skill's own Jira runtime credentials as described in README. Run a new live case, inspect the retrieved evidence and commit, and confirm only the preview you intend to publish. Do not use fake test issue keys as evidence of live success.

## Remaining capability limitations

The supplied Jira skill has no photo-upload operation. Attachment-bearing drafts remain pending for manual handoff before creating any issue. Publication retries/reconciliation and promotion of attempted dry-run cases are intentionally not automated. The bot handles cases serially in one process. The source search is bounded and can be incomplete; source quotation validation does not establish runtime causality.

Existing n8n files and unrelated pre-existing workspace changes were left intact.
