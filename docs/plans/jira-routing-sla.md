# Plan: Jira ticket creation, team routing, and SLA watch

Customized for Datami's support intake (n8n + Telegram + Jira Data Center).
Inspired by the ideas in [AI-Powered-Ticket-Routing-SLA-Breach-Prediction-in-JIRA](https://github.com/aroojjaved93/AI-Powered-Ticket-Routing-SLA-Breach-Prediction-in-JIRA),
but not its code: that repository routes by priority only (`"L2" if High else "L1"`) and trains its
"SLA model" on a 3-row CSV with two features, so there is nothing reusable beyond the concepts.

## Decisions

| Topic | Decision |
| --- | --- |
| Jira | Data Center / Server (self-hosted); no built-in SLA timers, so n8n tracks SLA |
| Routing | Three teams: Backend, Frontend, DevOps |
| Approval | A team lead approves every ticket before it is created in Jira |
| SLA targets | Critical 1 h / 8 h, High 4 h / 2 working days, Medium 1 working day / 5 working days, Low 3 / 10 working days (first response / resolution), Tehran working hours |

## Flow

```text
Support (Telegram) → intake (existing) → READY_FOR_REVIEW
   → Classify Team + Priority (rules + LLM, with reasons)
   → Lead approval card in the leads' Telegram group:  [Approve] [Change team] [Change priority] [Reject]
   → Approve → create Jira issue → post to the team's Telegram group → tell support the ticket key
   → SLA Watch (every 15 min) → warn team at 50% / 80%, lead at 100%
   → Jira status changes (webhook) → update support ("in progress", "fixed")
```

## Phase 1 — Team and priority classification

New step after `Validate Intake Case` when the status is `READY_FOR_REVIEW`.

**Team (Backend / Frontend / DevOps).** The catalog only describes backend code, so the team is decided
from the symptoms, not from the feature alone. The LLM returns `{team, confidence, reason}` using these rules:

- Backend: wrong or missing data, API errors (4xx/5xx with a body), failed analysis/AI requests, exports,
  permissions, quotas — anything a catalog feature's backend code path explains.
- Frontend: layout, rendering, buttons or pages not reacting, browser-specific issues, client-side
  validation, data correct in the API but displayed wrongly (photo descriptions help here).
- DevOps: whole site down or very slow, timeouts across features, login/SSL/domain problems, deploy
  or infrastructure errors, many users affected at once.

Low confidence (< 0.7) is shown on the approval card so the lead decides.

**Priority (Critical / High / Medium / Low).** Rules decide; the LLM may only suggest moving one level
with a reason:

- Critical: production down, data loss, security issue, or a key customer fully blocked.
- High: a main feature broken in production for several customers, no workaround.
- Medium: one customer or a workaround exists (default).
- Low: cosmetic, wording, or enhancement.

Stored on the case: `team`, `team_reason`, `team_confidence`, `priority`, `priority_reason`.

## Phase 2 — Lead approval and Jira creation

- **One bot, one webhook.** Telegram allows one webhook per bot, so button presses (`callback_query`)
  are handled in the existing intake workflow: add `callback_query` to the Telegram Trigger's update
  types and branch right after it. A second workflow with its own Telegram Trigger would break intake.
- Approval card in the leads' group: summary, feature, scenario, customer/identifiers, photo
  descriptions, suggested team + priority with reasons, buttons. Only user IDs in the lead list may press
  them (checked in the workflow, not just by group membership).
- Approve → Jira REST API (Data Center, Personal Access Token as Bearer): project, issue type Bug,
  summary, description (reported facts, steps, expected/actual, identifiers, photo descriptions, support
  case ID), priority, team as a component (or label), and the catalog feature as a label.
- Then: post the ticket key + link to the team's Telegram group, reply to the support person
  (written by `Compose Reply`), and save `jira_key` on the case.
- Reject → the lead must give a reason; support is told and the case reopens for more information.

New data tables:

| Table | Columns |
| --- | --- |
| `team_routing` | team, jira_component, telegram_chat_id |
| `approvers` | telegram_user_id, name |
| `sla_policy` | priority, response_hours, resolution_hours |
| `tickets` | case_id, jira_key, team, priority, created_at, first_response_at, resolved_at, warned_50, warned_80, breached |

## Phase 3 — SLA watch and status updates

- **SLA Watch workflow** (Schedule Trigger, every 15 min): read open rows from `tickets`, fetch status and
  first-response time from Jira (first comment or transition by an engineer), compute elapsed **working**
  time (Tehran working days and hours, configurable; holidays list later), and send each warning once:
  50% and 80% to the team group, 100% to the leads' group.
- **Jira webhook → n8n** (Data Center: System → WebHooks, filtered by JQL `labels = support-intake`):
  on status change, update `tickets` and send a short natural reply to the support person.

## Phase 4 — Learning (later, only with real data)

Log for every ticket: feature, scenario, team suggested vs. final, priority suggested vs. final, photo count,
hour/day created, time to first response, time to resolve, breached, reassigned. After a few hundred resolved
tickets, compare a simple model (logistic regression / gradient boosting) for breach risk and team routing
against the rules, and use it only if it is clearly better. Lead overrides are the training signal.

## Needed before building

- Jira base URL, a Personal Access Token for a service account, project key, issue type, priority names,
  and whether teams are components or labels.
- The leads' Telegram group ID and the lead user IDs; each team's Telegram group ID.
- Working days and hours (assumed Saturday–Wednesday 09:00–17:00 Tehran).

## Verification

- Fixture cases for each team rule and priority rule run through the test workflows (no Jira needed).
- Jira creation tested first against a test project or with a dry-run switch.
- SLA math checked with a small offline test (weekend, after-hours, multi-day cases).
- End-to-end: report → lead approves → Jira issue exists with the right component/priority → team group
  notified → support told → status change in Jira reaches support.
