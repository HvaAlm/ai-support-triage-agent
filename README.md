# AI Support Triage Agent

A runnable Python MVP for Persian support conversations. Telegram and the local CLI share the same SQLite-backed case workflow:

1. Collect a report and classify `aspect_sentiment_analysis` or `abstraction_analysis` (text summarization/abstraction).
2. Ask scenario-specific follow-up questions in Persian.
3. Retrieve a bounded backend source snapshot from the configured GitLab project at one commit SHA.
4. Investigate with Codex CLI using the existing ChatGPT login in a read-only sandbox.
5. Show a ticket preview separating user reports, verified source quotations, suspected causes, and suggested fixes.
6. Publish only after explicit owner confirmation of that exact preview, using the existing Jira skill.

Offline mock mode works without network access, tokens, Codex, Telegram, or n8n. It returns no fabricated code evidence or root cause. Photos are attachments only. Voice, video, image interpretation, frontend investigation, code execution, and automatic fixes are outside this MVP.

The n8n workflows in [workflows/](workflows/) are the primary Telegram intake path; this Python application runs independently and does not use them.

## n8n intake workflows

| Workflow | Role |
| --- | --- |
| `support-triage.json` | Starts with the support user's Telegram message: allowlisted user → `/new`/`/start` closes the open case. Other messages (text, photos, albums) are collected in the `message_buffer` data table and processed together after 60 seconds without a new message, or immediately on `/done`; the first message of a burst gets a short acknowledgement. Processing: feature catalog → photo description (when a photo or image file is attached) → LLM → validation → `support_cases` → Persian reply. Failures send a Persian error reply. |
| `issue-investigation.json` | Started in the background when support confirms a new issue: a read-only agent reads the backend (`rc`) and frontend (`development`) code, and the tech posts get the suspected file, verified code excerpt, likely cause and suggested fix (a hypothesis). Must stay published. |
| `build-feature-catalog.json` | Set `REPOSITORY` (`backend` → `group/backend` @ `rc`, `frontend` → `group/web` @ `development`) in `Prepare Catalog Scope`. Lists every user-facing feature of that repository, then analyses each one (one agent run per feature) and saves evidence-backed proposals to `feature_catalog_proposals` as `pending_review`. Features with an existing proposal are skipped, so a re-run resumes; `analysis_failed` rows are retried. Approved proposals must be copied to `feature_catalog_draft` with `active=true` before intake uses them. |
| `tests/abstraction-intake-test.json`, `tests/plot-intake-test.json` | Copies of the main flow where a manual trigger and a sample message replace the Telegram Trigger and allowlist. Regenerate them after changing the main flow. |
| `tests/intake-*-check.json` | Model and preparation checks |

For local testing, `scripts/start-tunnel.sh` starts a Cloudflare quick tunnel, writes its address to `N8N_PUBLIC_HOST` in `.env`, and publishes the intake workflow so Telegram delivers every message; re-run it after a reboot (the address changes). On a server, set `N8N_PUBLIC_HOST` to the server's domain instead.

**Confirm and close.** A complete report is shown to support with ✅ / ✏️ buttons; only ✅ posts (or updates) the tech-group post and closes the report. To correct a sent report, reply to or edit one of its messages, then confirm again. In groups, allowlisted users tag `@ai_support_triage_bot`, or reply to a message and tag it.

**Issues and reports.** When a report is ready for review it is classified (team, priority) and compared with open issues of the same feature in the `issues` data table: the same problem increases that issue's `case_count`, a new one creates an `ISS-…` issue with its feature, code modules, team, kind of problem and priority. Send `/report` to the bot for counts by team, module, feature and kind of problem, the most repeated issues, and new issues of the last 7 days. Each case keeps the support/bot conversation, which both models see. New issues, and issues reaching 3, 5, 10 or 20 reports, are pushed to the tech team: add each member's Telegram `chat_id`, `name` and `team` (`all`, `backend`, `frontend`, `devops`) to the `tech_recipients` data table; each member must press Start on the bot once. When support later corrects or adds to a posted report (including editing a Telegram message), the posted messages are edited in place (`tech_messages` records which messages belong to which report).

Import edits with `n8n import:workflow`. Reload open n8n editor tabs after an import: saving from an old tab overwrites it. The support-user allowlist is in the `Allowed Support User?` node.

Compose reads `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, `N8N_PUBLIC_HOST`, and `N8N_RUNNERS_AUTH_TOKEN` from `.env` (see [.env.example](.env.example)).

## Install

Requires Python 3.10+ on Linux/macOS. Run from this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Edit `.env`, then export it in your shell. The application does **not** automatically load it:

```bash
set -a
source .env
set +a
```

Only source your own trusted environment file. It is ignored by Git. The application itself uses the Python standard library; the supplied Jira skill has its own optional dependencies.

## Run the offline MVP

```bash
export APP_MODE=mock
export TICKET_PUBLISHER=dry-run
python -m triage chat
# Equivalent installed command:
support-triage chat
```

Example Persian conversation, one line at a time:

```text
/new تحلیل احساسات محصول اشتباه است
1
کیفیت دوربین خوب است ولی باتری ضعیف است
خروجی برای باتری مثبت بود
باتری
منفی؛ چون متن می‌گوید ضعیف است
متن را به سرویس ارسال کردم و خروجی را دیدم
محیط تست، امروز
نامشخص
/investigate
/preview
```

The preview ends with `/confirm CASE_ID REVISION`. Copy that exact command only after reviewing the ticket. Dry-run saves the draft/result locally and explicitly says **No Jira issue was created.** It returns no Jira issue key or URL.

`/quit` exits the CLI. Restarting resumes the active case. Mock cases cannot be promoted into live cases: start a new case after switching modes.

For commands across separate processes:

```bash
python -m triage new 'خلاصه‌سازی اطلاعات نادرست اضافه می‌کند'
python -m triage say '1'
python -m triage status
# Continue `say` with the answer to each displayed question, then:
python -m triage investigate
python -m triage preview
python -m triage confirm CASE_ID REVISION
# The confirm subcommand redisplays the preview and requires typing CONFIRM.
```

Useful commands:

| CLI | Chat/Telegram | Purpose |
| --- | --- | --- |
| `cases` | `/cases` | List your cases |
| `use CASE_ID` | `/use CASE_ID` | Resume one of your cases |
| `status` | `/status` | Current question, fields, attachments, publication status |
| `say '/answer actual corrected text'` | `/answer actual corrected text` | Correct an answer and invalidate investigation/preview |
| `photo /path/photo.jpg` | Send a photo | Save opaque JPEG/PNG/WebP attachment; no image analysis |
| `handoff` | `/handoff` | Full conversation, findings, attachment manifest, and prepared ticket |
| `catalog` | `/catalog` | Source paths with observed feature references and commit SHA |

Inside CLI chat, `/photo /path/photo.jpg` attaches a local photo. The CLI owner is `cli:<OS username>`. Telegram owners are `telegram:<numeric user ID>`. These are intentionally separate identities; there is no cross-channel impersonation or case transfer in this MVP. The CLI is a trusted local interface, not a network authentication system.

## Live GitLab retrieval and Codex investigation

No backend checkout or clone is required. The application does not investigate its own source.

Install a recent [Codex CLI](https://developers.openai.com/codex/cli/) with Node.js/npm, then sign in with ChatGPT:

```bash
npm install -g @openai/codex
codex login
codex login status
codex exec --help
```

The installed CLI must support `--ignore-user-config`, `--ephemeral`, `--sandbox read-only`, `--output-schema`, and `--output-last-message`. The adapter also disables apps, plugins, hooks, MCP servers, and project instructions for this execution. It does not use `OPENAI_API_KEY`. Official behavior: [noninteractive mode](https://developers.openai.com/codex/noninteractive/).

Configure a project-scoped token with read-only GitLab API access (`read_api` and permission to read the repository):

```bash
export APP_MODE=live
export TICKET_PUBLISHER=dry-run
export GITLAB_BASE_URL=https://git.example.com
export GITLAB_PROJECT_PATH=group/backend
read -rsp 'GitLab read token: ' GITLAB_READ_TOKEN; echo
export GITLAB_READ_TOKEN
# Optional: export BACKEND_REF=your-branch-or-tag
python -m triage chat
```

The retrieval layer resolves the project and its actual default branch through the API, then resolves the selected ref to a commit SHA. Every directory/file read uses that SHA. It uses GET requests only, refuses redirects, and never accesses another project. There are no GitLab credentials in prompts, ticket drafts, logs, or child process environments.

Limits per investigation: 80 requests, a 90-second retrieval budget, at most 10 tree pages (1,000 entries), 60 files, 128 KB per file, and 2 MB total source. Individual requests have a timeout. Secret/environment/private-key paths, dependencies, generated files, frontend directories, symlinks, and credential-like content are excluded. Readable source extensions and exclusions are explicit in `triage/gitlab.py`. This is a bounded search, not exhaustive repository analysis.

Discovery starts with repository docs and relevant source paths, then reads actual source. Observed feature references are recorded in SQLite's `feature_catalog` with path, line, quotation, and commit SHA. These are verified source references, not a claim that a directory owns the whole feature. Until authenticated access succeeds, no backend feature paths are claimed to be verified.

Codex receives only the retrieved snapshot plus case context and path/SHA metadata. Temporary files live outside source control and are removed after investigation. Source citations must match exact file lines; invented quotes, out-of-snapshot paths, and hypotheses without evidence are rejected. A cited line proves source content, not the runtime cause of the incident. Fixes are suggestions only.

Missing access, retrieval limits/failures, Codex login errors, invalid output, and timeouts are explicit. Live mode never silently falls back to mock findings. The case remains available; read-only investigation can be requested again with `/investigate`.

## Telegram

Create a bot through Telegram's BotFather and configure it in your local environment:

```bash
read -rsp 'Telegram bot token: ' TELEGRAM_BOT_TOKEN; echo
export TELEGRAM_BOT_TOKEN
export TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
python -m triage telegram
```

Replace the sample IDs with the numeric Telegram IDs of the case owners. Only allowlisted users in private chats are accepted. Telegram is an online transport even when `APP_MODE=mock`; the local mock CLI remains fully offline.

Use `/new`, answer the Persian questions, then `/investigate`, `/preview`, and the displayed `/confirm CASE_ID REVISION`. Plain-text messages avoid rendering report content as executable markup. Photos are downloaded with a 10 MB limit and retained as attachments without sending image bytes to Codex. Unsupported media is rejected explicitly.

Polling offsets and processed update responses persist in SQLite. A repeated update does not advance the conversation or create a second case/ticket. A failed reply delivery reuses its saved response. A crash after reserving an update but before completing it requires checking `/status`; the bot does not blindly replay the action. Replies may be delivered more than once after a crash, but publication remains protected. Run one polling bot process per token/database; investigations are handled serially in this MVP.

## Jira through the existing skill

The supplied [jira-create-issue skill](agent/skills/jira-create-issue/SKILL.md) documents a noninteractive CLI with an explicit `--confirm` gate. The adapter in `triage/skill_publisher.py` invokes that existing CLI; it adds no Jira HTTP client or authentication implementation.

```bash
python -m pip install -r agent/skills/jira/requirements.txt
python agent/skills/jira/scripts/jira_tool.py create_issue --help
export TICKET_PROJECT=YOUR_VERIFIED_PROJECT_KEY
export TICKET_ISSUE_TYPE=Bug
export TICKET_PUBLISHER=skill
# APP_MODE must be live; complete a new case and confirm its preview.
```

Provision authentication in the skill's own runtime as documented in [its README](agent/skills/jira/README.md). The app passes only the skill's `JIRA_*` environment and standard process variables, excluding GitLab/Telegram/API tokens. `.env.example` contains no Jira credentials. `TICKET_SKILL_SCRIPT` can override the default supplied CLI path when skills are installed elsewhere; it is administrator configuration, never report-controlled.

The ticket must include verified project/type values. Optional custom-field IDs must come from the skill's field discovery tools, never guesses. The skill's own `JIRA_MAX_RETRIES=0` setting disables its default POST retries for creation, because a timed-out request may already have created the issue. No creation deduplication argument is invented.

**Attachment limitation:** the supplied skill has no upload operation. A draft with photos returns `pending` for manual handoff **before creating any issue**. No attachment is silently dropped. Export `/handoff` plus the referenced photo files for the operator. If a future skill is interactive-only, this remains a manual workflow; unattended capability must not be assumed.

## Confirmation, persistence, and recovery

`Publisher.publish(case_id, confirmed_draft) -> Publication` returns status, actual issue key, actual Jira URL, and errors. Investigation never invokes this boundary.

Preview changes invalidate the previous confirmation token. The current owner and revision are checked in SQLite. An atomic attempt reservation commits before calling the publisher, so concurrent/repeated confirmations and process restarts cannot create a second issue. Actual skill-reported keys/URLs are saved without constructing a synthetic URL. Ambiguous failures remain `unknown`; cases, answers, findings, and attachments are preserved.

An attempted case is locked against edits/republication, including dry-run and pending outcomes. Automatic retry, promotion from dry-run to live, and administrative reconciliation are not implemented. After an uncertain outcome, reconcile with the skill/Jira before any operator recovery; do not create a replacement case merely to bypass duplicate protection. Use independent sample cases for mock experiments. Keep the database and attachment directory together when backing up; deleting the database removes the local duplicate guard.

## Configuration and tests

See [.env.example](.env.example) for every application setting. Defaults are offline mock, dry-run, `data/cases.sqlite3`, and `data/attachments`. `INVESTIGATION_TIMEOUT_SECONDS` (default 180) bounds the Codex subprocess separately from retrieval. No `JIRA_MODE`, local backend path, or n8n dependency is used.

```bash
python -m unittest discover -s tests -v
python -m compileall -q triage
```

Tests include real CLI subprocesses, all eight feature scenarios, persistence/restarts, owner isolation, stale confirmations, concurrent publication, photos, GitLab project/ref pinning and limits, evidence validation, Codex credential isolation, Telegram redelivery, and the existing skill adapter with fake responses.

See [architecture](docs/architecture.md) and [implementation/verification report](docs/implementation-report.md). Live GitLab, Telegram, and Jira account behavior remains unverified until their required access is configured; no successful external result is fabricated.
