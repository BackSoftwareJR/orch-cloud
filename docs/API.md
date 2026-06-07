# HyperOrchestrator API — Integration Guide (backclub.it)

Production orchestrator API for **[backclub.it](https://backclub.it)** — task dispatch, specialist agents, and webhook callbacks.

**Production VPS (backclub/orchestrator):** `http://2.24.15.210:8000`  
Dashboard: `http://2.24.15.210:3000`  
OpenAPI: `http://2.24.15.210:8000/docs`

When a reverse proxy is configured on backclub.it, you may also use a path such as `https://orchestrator.backclub.it` — the n8n URL path below stays the same.

## Authentication

When `REQUIRE_API_TOKEN=true`:

```
Authorization: Bearer <ORCHESTRATOR_API_TOKEN>
```

**n8n / Hyper-bs workflow** — use the same token with header `X-API-Key` (preferred for n8n HTTP Request nodes):

```
X-API-Key: <ORCHESTRATOR_API_TOKEN>
```

Also accepted: `X-API-Token`, `Authorization: Bearer …`

Webhook trigger and `/api/v1/execute-agent` always require a token.

Optional HMAC on outbound callbacks via `WEBHOOK_SECRET`.

## n8n integration — `POST /api/v1/execute-agent`

Drop-in replacement for the legacy ngrok endpoint. Use this URL in your n8n HTTP Request node:

```
http://2.24.15.210:8000/api/v1/execute-agent
```

### Request

Headers:

| Header | Value |
|--------|--------|
| `Content-Type` | `application/json` |
| `X-API-Key` | Your `ORCHESTRATOR_API_TOKEN` from the VPS `.env` |

Body (JSON):

```json
{
  "dedicated_prompt": "Implement the hero section from Figma",
  "github_url": "https://github.com/BackSoftwareJR/villa_sole",
  "website_url": "https://villa-sole.example.com",
  "specialist_role": "frontend dev",
  "task_id": "232",
  "project_id": "crm-project-99",
  "crm_log_url": "https://crm.example.com/tasks/232/log",
  "crm_auth_token": "optional-crm-bearer-token"
}
```

| Field | Required | Maps to |
|-------|----------|---------|
| `dedicated_prompt` | yes | Agent task text |
| `github_url` | yes | Find or create orchestrator project by repo URL |
| `specialist_role` | no | Agent preset (see table below) |
| `task_id` | no | Stored as `metadata.crm_task_id` on the job |
| `project_id` | no | External CRM project id → `metadata.crm_project_id` (not orchestrator project id) |
| `website_url` | no | Project settings + job metadata |
| `crm_log_url` | no | Job metadata for callbacks |
| `crm_auth_token` | no | Job metadata (for CRM API calls from agent) |

**Specialist role → preset**

| CRM role (examples) | Preset |
|---------------------|--------|
| frontend dev, ui, ux, design | `ux` |
| backend dev, api | `backend` |
| bug fix, debugger | `bugfix` |
| general, full stack | `general` |

If the GitHub repo is not registered yet, a project is created automatically (`name` = repo name, `repo_url` = `github_url`).

### Response

```json
{
  "status": "accepted",
  "task_id": "42",
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "queue_position": 2,
  "project_id": 5,
  "orchestrator_job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| Field | Meaning |
|-------|---------|
| `task_id` | Orchestrator internal job id (integer as string) |
| `run_id` | UUID for polling logs / status (`GET /jobs/{run_id}`) |
| `queue_position` | Position in the QUEUED queue |
| `project_id` | Orchestrator project id (auto-created if needed) |

### Example curl

```bash
curl -X POST "http://2.24.15.210:8000/api/v1/execute-agent" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ORCHESTRATOR_API_TOKEN" \
  -d '{
    "dedicated_prompt": "Fix mobile nav overlap",
    "github_url": "https://github.com/BackSoftwareJR/villa_sole",
    "specialist_role": "frontend dev",
    "task_id": "232",
    "project_id": "crm-99",
    "website_url": "https://villa-sole.example.com"
  }'
```

## API usage statistics

Track inbound calls from n8n, webhooks, and the dashboard:

```http
GET /stats/api-usage
```

Response includes `total`, `today`, `this_week`, `by_source`, `by_endpoint`, and `recent` (last 10 calls).  
Dashboard: **Stats** page at `/stats`.

## Agent presets (v2.0)

| Preset   | Default level | Best for |
|----------|---------------|----------|
| `general`| medium        | Full-stack, balanced architect |
| `ux`     | medium        | UI/UX, CSS, HTML, editorial layouts, a11y |
| `backend`| medium        | APIs, DB, migrations, security |
| `bugfix` | fast          | Root-cause fix, minimal diff |

Each preset includes a **quality checklist** injected into the agent prompt. Fetch via `GET /presets/{id}`.

## Project settings

Store per-project defaults and webhook URL in `Project.settings`:

```json
{
  "default_preset": "ux",
  "default_level": "medium",
  "webhook_url": "https://backclub.it/api/orchestrator/callback"
}
```

## Typical backclub.it flow

### 1. Register project

```bash
curl -X POST "$BASE_URL/projects" \
  -H "Content-Type: application/json" \
  -d '{"name":"My App","repo_url":"https://github.com/org/repo.git","settings":{"webhook_url":"https://backclub.it/api/orchestrator/callback"}}'
```

### 2. Create task with specialist

```bash
curl -X POST "$BASE_URL/projects/1/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task":"Redesign news page","preset":"ux","level":"medium"}'
```

### 3. Poll or receive webhook

Poll: `GET /jobs/{job_id}`

**Outbound webhook** (when `project.settings.webhook_url` is set):

```json
{
  "event": "job.completed",
  "job_id": "uuid",
  "project_id": 1,
  "preset": "ux",
  "level": "medium",
  "status": "COMPLETED",
  "task_preview": "Redesign news page...",
  "finished_at": "2026-06-07T12:00:00+00:00"
}
```

Header `X-Orchestrator-Signature`: HMAC-SHA256 of body with `WEBHOOK_SECRET`.

### 4. Live logs

```
ws://{HOST}/ws/logs/{job_id}
```

## Preset discovery

```http
GET /presets
GET /presets/ux
```

Detail includes `quality_checklist`, `output_expectations`, `forbidden_actions`.

## Environment variables

| Variable | Description |
|----------|-------------|
| `ORCHESTRATOR_API_TOKEN` | Inbound API auth |
| `REQUIRE_API_TOKEN` | Enforce token on job creation |
| `WEBHOOK_SECRET` | HMAC for outbound callbacks |
| `CURSOR_API_KEY` | Agent execution (file or dashboard Settings) |
| `AGENT_ENV_PATH` | Override path to agent.env (default `/opt/agent-orchestrator/config/agent.env`) |
| `CORS_ORIGINS` | Include `https://backclub.it` |

## Settings — Cursor API key

Manage the Cursor account used by agent containers without restarting the VPS.

```http
GET /settings
PUT /settings/cursor-api-key
DELETE /settings/cursor-api-key
```

When `REQUIRE_API_TOKEN=true`, send `Authorization: Bearer <ORCHESTRATOR_API_TOKEN>`.

**GET /settings** response (key is never returned in full):

```json
{
  "cursor_api_key": {
    "configured": true,
    "masked_preview": "****************1234",
    "updated_at": "2026-06-07T12:00:00+00:00",
    "source_path": "/opt/agent-orchestrator/config/agent.env"
  }
}
```

**PUT /settings/cursor-api-key** body:

```json
{ "api_key": "key_xxxxxxxx" }
```

**Hot reload:** the key is written to `agent.env`. The next job reads it from disk when spawning Docker agent containers. Running jobs keep the key they started with. No VPS or `orchestrator-api` restart is required.

`GET /health` also includes `cursor_api_key` status.

## Roadmap: backclub.it workspace

Future backclub.it module: unified project workspace, sub-task generation from PRO plans, preset analytics, and in-app prompt tuning. Orchestrator API remains the execution engine; backclub.it is the control plane.
