# AI Support Triage Agent

An AI-powered technical support triage system that converts support reports into structured engineering bug tickets.

The system receives a support request, analyzes the issue using an LLM, determines the responsible engineering team, creates a structured Jira ticket, and notifies the relevant team.

---

## 🎯 Problem

Technical support teams often receive issues in an unstructured format:

- Incomplete descriptions
- Screenshots without context
- Missing reproduction steps
- Unclear responsibility between Backend, Frontend, and DevOps
- Repetitive or duplicate bug reports

This project aims to automate the initial technical triage process and reduce the manual work required to turn a support report into an actionable engineering ticket.

---

## 🏗️ Architecture

```text
┌─────────────────────┐
│   Support Engineer  │
└──────────┬──────────┘
           │
           │ Message / Screenshot
           ▼
┌─────────────────────┐
│    Telegram Bot     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│         n8n         │
│    Orchestrator     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    AI Triage Agent  │
│                     │
│  • Issue Analysis   │
│  • Classification   │
│  • Priority         │
│  • Information      │
│    Extraction       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Structured Issue   │
│        JSON         │
└──────────┬──────────┘
           │
           ▼
      ┌────┴────┐
      │         │
      ▼         ▼
   Missing    Valid
    Info       Issue
      │         │
      ▼         ▼
   Support    Jira
   Request    Ticket
                │
                ▼
        ┌───────────────┐
        │ Team Channel  │
        │               │
        │ Backend       │
        │ Frontend      │
        │ DevOps        │
        └───────────────┘
```

---

## ✨ Features

### Current

- Receive technical support reports through Telegram
- Process natural-language support messages
- Extract structured issue information using an LLM
- Classify issues by responsible engineering team
- Determine issue priority
- Detect missing information
- Generate structured Jira bug reports
- Notify the relevant engineering team

### Planned

- 🖼️ Screenshot and image analysis
- 📚 Documentation search with RAG
- 🔎 Similar Jira issue detection
- 💻 Repository and source-code analysis
- 🔀 Backend / Frontend / DevOps specialized agents
- 🔍 Git history and regression analysis
- 👤 Human approval workflow
- 📊 Triage confidence scoring
- 📈 Support and bug analytics

---

## 🔄 Workflow

The initial workflow follows these steps:

```text
1. Receive Support Request
        ↓
2. Normalize Input
        ↓
3. Analyze Issue with AI
        ↓
4. Generate Structured JSON
        ↓
5. Validate Required Information
        ↓
6. Classify Responsible Team
        ↓
7. Create Jira Bug
        ↓
8. Notify Engineering Team
        ↓
9. Send Result Back to Support
```

---

## 🧠 AI Triage

The AI agent converts an unstructured support report into a structured engineering issue.

Example input:

```text
Users are getting a 500 error when creating an order.
The issue started around 14:30 today and has been reported
by several users on Android.
```

Example output:

```json
{
  "title": "Order creation returns HTTP 500 on Android",
  "issue_type": "bug",
  "team": "backend",
  "priority": "high",
  "environment": "production",
  "platform": "android",
  "steps_to_reproduce": [
    "Open the Android application",
    "Attempt to create an order"
  ],
  "expected_behavior": "Order should be created successfully.",
  "actual_behavior": "Application returns HTTP 500.",
  "missing_information": [],
  "is_ready_for_jira": true
}
```

The agent is instructed not to invent technical information. Missing information is explicitly returned so that the support engineer can provide additional details.

---

## 🛠️ Tech Stack

| Technology       | Purpose                           |
| ---------------- | --------------------------------- |
| n8n              | Workflow orchestration            |
| LLM              | Issue analysis and classification |
| Telegram Bot API | Support interface                 |
| Jira API         | Bug tracking                      |
| Docker           | Local and self-hosted deployment  |

Additional technologies will be introduced as the project evolves.

---

## 📁 Project Structure

```text
ai-support-triage-agent/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
│
├── workflows/
│   └── support-triage.json
│
├── docs/
│   ├── architecture.md
│   └── screenshots/
│
└── examples/
    ├── sample-support-message.json
    └── sample-ai-output.json
```

---

## 🚀 Getting Started

### Prerequisites

- Docker
- Docker Compose
- Telegram Bot
- LLM API credentials
- Jira account with API access

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/ai-support-triage-agent.git

cd ai-support-triage-agent
```

### 2. Configure environment variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Configure the required credentials:

```env
N8N_HOST=localhost
N8N_PROTOCOL=http
TIMEZONE=Asia/Tehran

TELEGRAM_BOT_TOKEN=
LLM_API_KEY=

JIRA_BASE_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=
```

### 3. Start n8n

```bash
docker compose up -d
```

### 4. Open n8n

Open:

```text
http://localhost:5678
```

---

## 🔐 Security

This project is designed to be self-hosted.

Secrets and credentials should be provided through environment variables and must never be committed to the repository.

The following files should remain local:

```text
.env
```

Sensitive credentials include:

- Telegram Bot Token
- LLM API Key
- Jira API Token
- Other integration credentials

---

## 🗺️ Roadmap

### Phase 1 — Basic Triage

- [x] Self-hosted n8n
- [ ] Telegram integration
- [ ] AI issue analysis
- [ ] Structured issue output
- [ ] Team classification
- [ ] Jira integration
- [ ] Team notification

### Phase 2 — Context Awareness

- [ ] Screenshot analysis
- [ ] Document processing
- [ ] Documentation RAG
- [ ] Similar Jira issue detection

### Phase 3 — Engineering Investigation

- [ ] Git repository integration
- [ ] Code search
- [ ] Git history analysis
- [ ] Suspected root-cause detection
- [ ] Regression detection

### Phase 4 — Multi-Agent System

- [ ] Triage Agent
- [ ] Backend Agent
- [ ] Frontend Agent
- [ ] DevOps Agent
- [ ] QA Agent
- [ ] Agent orchestration

### Phase 5 — Production Hardening

- [ ] Authentication and authorization
- [ ] Observability
- [ ] Error handling
- [ ] Retry mechanisms
- [ ] Audit logs
- [ ] Human approval workflow
- [ ] Confidence-based automation

---

## 🎯 Project Goal

The long-term goal is to build an AI-assisted engineering support layer that can:

```text
Support Report
      ↓
Understand the Problem
      ↓
Find Relevant Context
      ↓
Investigate the Codebase
      ↓
Identify the Responsible Team
      ↓
Suggest the Root Cause
      ↓
Create an Actionable Jira Ticket
      ↓
Notify the Engineering Team
```

The system is designed to assist engineers and support teams, not replace engineering judgment.
