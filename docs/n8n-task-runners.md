# n8n task runners

Docker Compose runs n8n and its external task runners at version 2.37.10.
The runner broker is available only through the Compose network; port 5679 is
not published on the host. Existing PostgreSQL and n8n volumes are reused.

Set `N8N_RUNNERS_AUTH_TOKEN` in the ignored local `.env` file before starting.
Generate a value once with `python3 -c 'import secrets; print(secrets.token_hex(32))'`.
Compose passes the same token to n8n and the runner launcher. Do not commit it.

```bash
docker compose config --quiet
docker compose up -d n8n task-runners
docker compose logs --tail=50 n8n task-runners
```

`n8n-task-runners.json` is based on the matching official runner image's default
configuration, with Python's `json` standard-library module allowed. No external
Python packages are enabled. The file is mounted read-only.

To verify the actual Python Code node, select Python (Native), Run Once for All
Items, and run:

```python
import json
return [{"json": {"runner_ok": json.loads('{"ok": true}')["ok"]}}]
```

The output should contain `runner_ok: true`. Then rerun Prepare Intake Input.

## Intake verification (2026-09-30)

The saved `Datami — Support Intake & Triage` workflow uses `feature_catalog_draft`
consistently for aggregation, Python input/output, and the LLM prompt. Its LLM user prompt consumes
`message_text` and the normalized catalog from the preparation node.

The `Datami — Intake Preparation Check` manual workflow successfully replayed
the saved Telegram sample and a read-only snapshot of three active catalog rows
through aggregation, Edit Fields, and Python (Native) on an external runner.
Verified feature keys: `aspect_sentiment_analysis`, `abstraction_analysis`, and
`plot_description`. The output retained message text, normalized sender/chat IDs
to strings, and parsed all five catalog list fields into arrays.

This check uses a catalog snapshot because `n8n execute` in version 2.37.10 does
not initialize the Data Table module. The main workflow keeps its live Data
Table node. The check stops at Prepare Intake Input: it does not call the LLM,
send Telegram messages, or create Jira issues. It does not verify a fresh
Telegram webhook delivery or the current live Data Table node in the editor.

The temporary test runner was removed after verification. The standard external
runner remains available to editor executions. Reload the editor after CLI
imports before making further workflow edits.

## Structured intake configuration

The repository contains the main workflow export captured in the migration
bundle on 2026-10-07 (`workflows/support-triage.json`). Its 17-node snapshot
connects the Telegram intake path through catalog retrieval, preparation, the
LLM chain and structured parser, Python validation, support-case upsert, and a
Telegram reply. The `If`, `Code in Python` fixture, and `Find Platform Mapping`
nodes are not connected in this snapshot. The workflow is marked inactive.

The standalone prompt and output schema in `workflows/intake/` were synchronized
from the saved LLM node and parser schema. The model output stays wrapped in
`output` by n8n. The model must keep `ready_for_investigation=false`; validation
is handled by the connected Python node, while the Data Table upsert persists
the case. Previous-case context is read from the support-case table when
available. The workflow asks up to three Persian questions and handles reports
where no request ID exists.

`Datami — Intake Model Check` contains four synthetic Persian reports and a
catalog snapshot for evaluation. Its live execution has not run: explicit
authorization is pending for sending the internal catalog to the configured
model endpoint. No successful model evaluation is claimed. The saved export is
a dated snapshot and does not confirm the current live editor state.

When upgrading, update both image versions together and compare the runner
configuration with the new image's default before restarting. Do not use
`docker compose down -v`, which would delete persisted data.
