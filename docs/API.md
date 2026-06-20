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

Drop-in replacement for the legacy ngrok endpoint.
### After changing `.env` on the VPS

systemd reads `/opt/orch-cloud/.env` only when **orchestrator-api** starts. Editing the file does not affect the running process until you restart:

```bash
sudo cp /opt/orch-cloud/deploy/orchestrator-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart orchestrator-api
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://127.0.0.1:8000/api/v1/execute-agent \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(grep '^ORCHESTRATOR_API_TOKEN=' /opt/orch-cloud/.env | cut -d= -f2- | tr -d '\"'"'"''"'"')'" \
  -d '{"dedicated_prompt":"test","github_url":"https://github.com/BackSoftwareJR/villa_sole"}'
```

Expect **HTTP 200**. **401** means the key in your request does not match `ORCHESTRATOR_API_TOKEN` in the running service (wrong value, stale process, or n8n header not `X-API-Key`).

 Use this URL in your n8n HTTP Request node:

```
http://2.24.15.210:8000/api/v1/execute-agent
```

### Request

Headers:

| Header | Value |
|--------|--------|
| `Content-Type` | `application/json` |
| `X-API-Key` | Your `ORCHESTRATOR_API_TOKEN` from the VPS `.env` |

Body (JSON) — full CRM + n8n payload:

```json
{
  "dedicated_prompt": "Implement the hero section from Figma",
  "exact_prompt": false,
  "github_url": "https://github.com/BackSoftwareJR/villa_sole",
  "website_url": "https://villa-sole.example.com",
  "specialist_role": "frontend dev",
  "task_id": "232",
  "project_id": "99",
  "crm_log_url": "https://backclub.it/api/workspace/agents/12/n8n-callback",
  "crm_auth_token": "your-callback-secret",
  "callback_url": "https://backclub.it/backend/public/api/webhooks/n8n/task-events",
  "callback_status_url": "https://backclub.it/backend/public/api/webhooks/n8n/status",
  "callback_completed_url": "https://backclub.it/backend/public/api/webhooks/n8n/completed",
  "callback_task_log_url": "https://backclub.it/backend/public/api/webhooks/n8n/task-log",
  "callback_close_task_url": "https://backclub.it/backend/public/api/webhooks/n8n/close-task",
  "callback_auth_header": "authbs"
}
```

Workspace agents use `task_id: "workspace_agent_{id}"` (e.g. `"workspace_agent_12"`).

| Field | Required | Maps to |
|-------|----------|---------|
| `dedicated_prompt` | yes | Agent task text |
| `exact_prompt` | no | When `true`, prompt is used verbatim (no sanitize/trim) |
| `github_url` | yes | Find or create orchestrator project by repo URL |
| `specialist_role` | no | Agent preset (see table below) |
| `task_id` | no | CRM task id or `workspace_agent_{id}` → `metadata.crm_task_id` |
| `project_id` | no | External CRM project id → `metadata.crm_project_id` |
| `website_url` | no | Project settings + job metadata |
| `crm_log_url` | no | Legacy log URL (stored in metadata) |
| `crm_auth_token` | no | Auth value for CRM callback headers |
| `callback_url` | no | CRM task-events webhook |
| `callback_status_url` | no | CRM status webhook (live n8n_status updates) |
| `callback_completed_url` | no | CRM completed webhook |
| `callback_task_log_url` | no | CRM task-log webhook (streaming agent output) |
| `callback_close_task_url` | no | CRM close-task webhook (fired on success) |
| `callback_auth_header` | no | Header name for CRM auth (e.g. `authbs`) |

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

## Live updates architecture (CRM + n8n)

End-to-end flow from CRM/n8n to live workspace updates:

```
CRM Task / Workspace Agent
        │
        ▼
   n8n Webhook (optional Groq exact_prompt branch)
        │
        ▼
POST /api/v1/execute-agent  ──►  Job QUEUED
        │                              │
        │                              ├─► callback_status_url  {status: queued}
        ▼                              │
   Worker picks job                    │
        │                              │
        ▼                              │
   Job RUNNING  ───────────────────────┼─► callback_status_url  {status: running}
        │                              │
        ▼                              ├─► callback_task_log_url (each log line)
   Agent subprocess                    │     or callback_url (task-events fallback)
        │                              │
        ▼                              │
   Job COMPLETED/FAILED ───────────────┼─► callback_status_url  {status: completed|failed}
        │                              │
        └──────────────────────────────┴─► callback_completed_url
                                         callback_close_task_url (success only)
```

### When each callback fires

| Milestone | URL | Payload highlights |
|-----------|-----|-------------------|
| Job accepted (queued) | `callback_status_url` | `task_id`, `project_id`, `status: queued`, `run_id`, `progress: 0` |
| Worker starts agent | `callback_status_url` | `status: running`, `message: Agent started`, `progress: 10` |
| Each stdout log line | `callback_task_log_url` | `step_key`, `title`, `message`, `log_message` |
| Job finished | `callback_status_url` | `status: completed` or `failed`, `progress: 100` on success |
| Job finished | `callback_completed_url` | `result` object on success, `error` on failure |
| Success only | `callback_close_task_url` | Same as completed (CRM marks task closed) |

All CRM callbacks include `task_id` (numeric or `workspace_agent_{id}`), `project_id`, and `run_id`.

### Auth on outbound callbacks

The orchestrator signs every callback with optional `X-Orchestrator-Signature` (HMAC-SHA256 of body, `WEBHOOK_SECRET`).

When `callback_auth_header` + `crm_auth_token` are in the request, they are sent on every CRM callback:

```
authbs: <crm_auth_token>
```

### Route CRM callbacks via n8n (recommended)

Set on the orchestrator VPS (or pass `callback_n8n_proxy_url` from CRM in execute-agent):

```env
CRM_CALLBACK_N8N_WEBHOOK_URL=https://n8n.srv1691601.hstgr.cloud/webhook/69069118-f267-4a90-b94c-e32003830893
CRM_CALLBACK_N8N_AUTH_HEADER=authbs
CRM_CALLBACK_N8N_AUTH_VALUE=your-n8n-token
```

When configured, the orchestrator POSTs to the n8n **Callback Receiver** webhook instead of calling backclub.it directly. The envelope:

```json
{
  "callback_type": "completed",
  "target_url": "https://backclub.it/backend/public/api/webhooks/n8n/completed",
  "callback_completed_url": "https://backclub.it/backend/public/api/webhooks/n8n/completed",
  "callback_auth_header": "authbs",
  "crm_auth_token": "secret",
  "task_id": "324",
  "project_id": "21",
  "status": "completed",
  "payload": { "task_id": "324", "status": "completed", "..." : "..." }
}
```

The n8n workflow must forward to `target_url` with header `authbs: {{ $json.crm_auth_token }}` and body `{{ $json.payload }}`.

### n8n HTTP Request node (execute-agent body)

Use this in the n8n node that calls the orchestrator after the webhook switch:

```json
{
  "dedicated_prompt": "={{ $json.dedicated_prompt }}",
  "exact_prompt": "={{ $json.exact_prompt }}",
  "github_url": "={{ $json.github_url }}",
  "website_url": "={{ $json.website_url }}",
  "specialist_role": "={{ $json.specialist_role }}",
  "task_id": "={{ $json.task_id }}",
  "project_id": "={{ $json.project_id }}",
  "crm_auth_token": "={{ $json.crm_auth_token }}",
  "callback_url": "={{ $json.callback_url }}",
  "callback_status_url": "={{ $json.callback_status_url }}",
  "callback_completed_url": "={{ $json.callback_completed_url }}",
  "callback_task_log_url": "={{ $json.callback_task_log_url }}",
  "callback_close_task_url": "={{ $json.callback_close_task_url }}",
  "callback_auth_header": "={{ $json.callback_auth_header }}",
  "callback_n8n_proxy_url": "={{ $json.callback_n8n_proxy_url }}"
}
```

Headers for execute-agent:

| Header | Value |
|--------|--------|
| `Content-Type` | `application/json` |
| `X-API-Key` | `ORCHESTRATOR_API_TOKEN` |

### Example status callback (orchestrator → CRM)

```json
{
  "task_id": "232",
  "project_id": "99",
  "status": "running",
  "n8n_status": "running",
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "orchestrator_job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Agent started",
  "progress": 10
}
```

### Example task-log callback

```json
{
  "task_id": "workspace_agent_12",
  "project_id": "41",
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "step_key": "log_1717939200123",
  "title": "Agent Output",
  "message": "Cloning repository...",
  "log_message": "Cloning repository...",
  "status": "completed"
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
| `WEBHOOK_SECRET` | HMAC (`X-Orchestrator-Signature`) for outbound callbacks |
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

## VPS deploy (2.24.15.210)

From the orchestrator repo on the VPS (`/opt/orch-cloud`):

```bash
cd /opt/orch-cloud
./deploy.sh
```

Ensure `.env` includes:

```env
ORCHESTRATOR_API_TOKEN=<shared-with-n8n>
REQUIRE_API_TOKEN=true
WEBHOOK_SECRET=<optional-hmac-secret>
CORS_ORIGINS=https://backclub.it,https://www.backclub.it
```

Verify after deploy:

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST http://127.0.0.1:8000/api/v1/execute-agent \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ORCHESTRATOR_API_TOKEN" \
  -d '{"dedicated_prompt":"ping","github_url":"https://github.com/BackSoftwareJR/villa_sole","task_id":"1","callback_status_url":"https://backclub.it/api/webhooks/n8n/status","callback_auth_header":"authbs","crm_auth_token":"test"}'
```

Services: `orchestrator-api` (port 8000), `orchestrator-dashboard` (port 3000).

## Roadmap: backclub.it workspace

Future backclub.it module: unified project workspace, sub-task generation from PRO plans, preset analytics, and in-app prompt tuning. Orchestrator API remains the execution engine; backclub.it is the control plane.
