---
name: jira-blockers
description: Blocking status and reasons for one Jira issue (status flags,
  unresolved "blocked by" links, flagged comments). Use for "what's blocking
  PAY-123" or "is PAY-123 blocked".
version: 1.0.0
metadata:
  category: software-development
  hermes:
    tags:
      - jira
      - project-management
      - tickets
    category: software-development
    requires_toolsets:
      - terminal
---
# Jira: Blockers

Read-only. Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py blockers --issue_key PAY-123
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

`--issue_key` is required. Prints `{"blocked": bool, "reasons": [...]}`.
Only report a blocker if `reasons` actually contains it -- if
`"blocked": false`, say so; don't invent a plausible one.

If the result contains `"error"`, tell the user what went wrong in
plain language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
