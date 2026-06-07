# HyperOrchestrator API — Integration Guide (backclub.it)

Production orchestrator API for **[backclub.it](https://backclub.it)** — task dispatch, specialist agents, and webhook callbacks.

Base URL (API): configure per deployment (e.g. `https://orchestrator.backclub.it` or VPS `:8000`)  
Dashboard: served from backclub.it workspace (future) or direct `:3000`  
OpenAPI: `{BASE_URL}/docs`

## Authentication

When `REQUIRE_API_TOKEN=true`:

```
Authorization: Bearer <ORCHESTRATOR_API_TOKEN>
```

Webhook trigger always requires a token. Optional HMAC on outbound callbacks via `WEBHOOK_SECRET`.

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
| `CURSOR_API_KEY` | Agent execution |
| `CORS_ORIGINS` | Include `https://backclub.it` |

## Roadmap: backclub.it workspace

Future backclub.it module: unified project workspace, sub-task generation from PRO plans, preset analytics, and in-app prompt tuning. Orchestrator API remains the execution engine; backclub.it is the control plane.
