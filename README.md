# HyperOrchestrator

Production-ready, self-improving multi-agent orchestration system for automated code tasks across Laravel and Next.js projects.

## Features

- **Framework analysis** — Auto-detects Laravel or Next.js with confidence scoring; writes rich `.system_context.md`
- **Three execution levels** — Fast (minimal fix), Medium (auto-debug + tests), Pro (AI-decomposed multi-step plan)
- **Self-learning memory** — SQLite-backed error/solution patterns with deduplication, relevance scoring, and structured `.cursorrules` injection
- **Docker isolation** — Ephemeral `hyper-agent-base` containers with repo, API key, and SSH mounts
- **Git workflow** — Clone, checkout `staging`, commit, push with retry/backoff and conflict handling
- **Production hardening** — Pre-flight health checks, correlation IDs, JSON logging, run reports, dry-run mode

## Requirements

- Python 3.12+
- Docker daemon running locally
- `hyper-agent-base` Docker image built and available
- Git installed
- Cursor User API key at `/opt/agent-orchestrator/config/agent.env`
- `~/.ssh` configured for Git push (read-only mount into containers, mode 0600 on private keys)
- `OPENAI_API_KEY` environment variable (required for `--level pro`)

## Installation

```bash
cd "/path/to/orchestratore cloud"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"   # optional: includes pytest
```

## Docker Base Image

Containers expect a base image named `hyper-agent-base` with `cursor-agent` installed:

```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y git curl nodejs npm php-cli composer
COPY cursor-agent /usr/local/bin/cursor-agent
WORKDIR /workspace
```

```bash
docker build -t hyper-agent-base .
```

## Agent Environment

```bash
sudo mkdir -p /opt/agent-orchestrator/config
echo "CURSOR_API_KEY=your-key-here" | sudo tee /opt/agent-orchestrator/config/agent.env
chmod 600 /opt/agent-orchestrator/config/agent.env
```

Mounted read-only as `/workspace/.env` inside containers.

## Usage

```bash
python -m core.main \
  --repo https://github.com/org/my-laravel-app.git \
  --task "Fix N+1 query on users index" \
  --level medium
```

Or after `pip install -e .`:

```bash
hyper-orchestrator --repo <url> --task "<description>" --level fast
```

### Dry Run

Validate configuration, health checks, and framework analysis without executing agents:

```bash
hyper-orchestrator --repo <url> --task "test" --level pro --dry-run
```

### Execution Levels

| Level | Alias | Behavior |
|-------|-------|----------|
| 1 | `fast`, `l1`, `level1` | `cursor-agent --model composer-2.5`, strict minimal fix, push immediately, no test loop |
| 2 | `medium`, `l2`, `level2` | `--yolo` agent, run tests, auto-debug on failure, push only when tests pass |
| 3 | `pro`, `l3`, `level3` | Master AI decomposes into JSON atomic tasks, sequential fresh containers, validates each step |

### Options

```
--repo          Git repository URL (required)
--task          Task description (required)
--level         1/fast, 2/medium, 3/pro (default: medium)
--work-dir      Local clone path (optional)
--max-retries   Medium-level debug retries (default: 3)
--openai-model  Model for PRO decomposition (default: gpt-4o-mini)
--dry-run       Validate without executing agents
--json-log      Structured JSON logs with correlation IDs
--report-dir    Directory for run summary JSON
-v, --verbose   Debug logging
```

## Architecture

```mermaid
flowchart TB
    CLI[main.py CLI] --> ORCH[orchestrator.py]
    ORCH --> HEALTH[health.py preflight]
    ORCH --> GIT[github_manager.py]
    ORCH --> MEM[memory_manager.py]
    ORCH --> DOCK[docker_controller.py]
    ORCH --> ANALYZE[analyzers/]
    ANALYZE --> LAR[laravel_analyzer]
    ANALYZE --> NEXT[nextjs_analyzer]
    ANALYZE --> DET[detector.py]
    ORCH --> PLAN[task_planner.py PRO mode]
    DOCK --> AGENT[cursor-agent in hyper-agent-base]
    MEM --> RULES[.cursorrules injection]
    ANALYZE --> CTX[.system_context.md]
    ORCH --> REPORT[run_report.json]
```

```
core/
├── main.py                 CLI entrypoint
├── orchestrator.py         Level routing, workflow
├── github_manager.py       Clone, staging, push (retry + timeout)
├── docker_controller.py    Ephemeral agent containers
├── memory_manager.py       SQLite learning history
├── models.py               Pydantic schemas
├── exceptions.py           Custom exception hierarchy
├── retry.py                Exponential backoff
├── security.py             URL validation, secret redaction
├── health.py               Pre-flight checks
├── logging_config.py       JSON logs, correlation IDs
├── log_parser.py           Agent success/failure detection
├── task_planner.py         PRO plan validation + ordering
├── context_builder.py      Context window prioritization
├── run_report.py           Run summary artifacts
└── analyzers/
    ├── base_analyzer.py
    ├── detector.py         Framework auto-detection + confidence
    ├── laravel_analyzer.py
    ├── nextjs_analyzer.py
    └── unknown_analyzer.py
```

## Self-Learning

When a Medium or Pro task fails multiple times then succeeds, HyperOrchestrator records error/solution patterns with:

- Deduplication by content hash
- Relevance scoring matched to the current task
- Project-specific vs global patterns (global after 3+ failures)
- Automatic expiry of patterns older than 90 days

Patterns are injected into `.cursorrules` under structured sections before each run.

Data: `~/.hyper-orchestrator/learning_history.db`

## Generated Artifacts

| File | Location | Purpose |
|------|----------|---------|
| `.system_context.md` | Project root | Framework analysis for sub-agents |
| `.cursorrules` | Project root | Injected learned patterns |
| `run-*.json` | `~/.hyper-orchestrator/reports/` | Run summary with correlation ID |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Docker is unavailable` | Daemon not running | Start Docker Desktop / `sudo systemctl start docker` |
| `Base image not found` | Missing image | `docker build -t hyper-agent-base .` |
| `agent.env not found` | Missing API key file | Create `/opt/agent-orchestrator/config/agent.env` |
| `Git push rejected` | Remote staging diverged | Resolve conflicts manually in work dir, or rebase |
| `OPENAI_API_KEY required` | Missing for PRO level | `export OPENAI_API_KEY=sk-...` |
| SSH push fails in container | Key permissions | `chmod 600 ~/.ssh/id_*` |
| Tests keep failing (medium) | Wrong test command | Check `.system_context.md` Testing section |

Enable verbose JSON logs for production debugging:

```bash
hyper-orchestrator --repo <url> --task "..." --level medium --json-log -v
```

## Platform API & Dashboard

HyperOrchestrator includes an H24 multi-project orchestration platform: a FastAPI backend with SQLite persistence, a background job worker, WebSocket log streaming, and a Next.js dashboard.

### Architecture

```mermaid
flowchart LR
    Dashboard[Next.js Dashboard] -->|REST| API[FastAPI api_gateway]
    Dashboard -->|WebSocket| WS[/ws/logs/job_id]
    API --> DB[(orchestrator.db)]
    Worker[Async Job Worker] --> DB
    Worker --> CLI[hyper-orchestrator CLI]
    CLI --> Docker[Docker Agents]
```

```
server/
├── app.py              FastAPI app + lifespan (starts worker)
├── config.py           Environment settings
├── database.py         SQLAlchemy engine + sessions
├── models.py           Project + Job ORM models
├── schemas.py          Pydantic API schemas
├── worker.py           Async queue worker (MAX_CONCURRENT_JOBS)
├── orchestrator.py     CLI subprocess helpers
└── routers/
    ├── health.py       GET /health
    ├── projects.py     Projects CRUD
    ├── jobs.py         Jobs list/get/trigger
    ├── webhook.py      POST /webhook/trigger-task (backward compatible)
    └── ws.py           WebSocket log streaming
dashboard/              Next.js App Router UI
deploy/                 systemd units + env template
```

### Run locally

**Backend:**

```bash
cd "/path/to/orchestratore cloud"
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
uvicorn api_gateway:app --host 0.0.0.0 --port 8000 --reload
```

**Dashboard:**

```bash
cd dashboard
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                        # http://localhost:3000
```

### REST API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness + worker stats |
| GET/POST/PATCH/DELETE | `/projects` | No | Projects CRUD |
| GET | `/jobs` | No | List jobs (`?project_id=&status=`) |
| GET | `/jobs/{job_id}` | No | Job detail + log tail |
| POST | `/projects/{id}/jobs` | No | Queue task for project |
| POST | `/webhook/trigger-task` | Yes | Webhook trigger (auto-creates project) |
| GET | `/jobs/{job_id}/legacy` | Yes | Backward-compatible status format |
| WS | `/ws/logs/{job_id}` | No | Live log stream |

### Authentication (webhook)

Set `ORCHESTRATOR_API_TOKEN` or `WEBHOOK_TOKEN`. Pass via `Authorization: Bearer <token>` or `X-API-Token`.

### Environment

See `deploy/orchestrator.env.example` for `DATABASE_URL`, `MAX_CONCURRENT_JOBS`, `CORS_ORIGINS`, and `NEXT_PUBLIC_API_URL`.

Job logs: `~/.hyper-orchestrator/jobs/{job_id}.log` · Database: `orchestrator.db`

### Systemd (VPS)

```bash
sudo cp deploy/orchestrator-api.service deploy/orchestrator-dashboard.service /etc/systemd/system/
sudo cp deploy/orchestrator.env.example /opt/orch-cloud/.env   # edit secrets
cd /opt/orch-cloud/dashboard && npm install && npm run build
sudo systemctl daemon-reload
sudo systemctl enable --now orchestrator-api orchestrator-dashboard
```

## VPS Deployment Guide

1. **Provision** — Ubuntu 22.04+ VPS with 4GB+ RAM, Docker, Node.js 20+
2. **Clone orchestrator** — `git clone https://github.com/BackSoftwareJR/orch-cloud /opt/orch-cloud`
3. **Install backend** — `cd /opt/orch-cloud && python3.12 -m venv .venv && source .venv/bin/activate && pip install -e .`
4. **Build dashboard** — `cd dashboard && npm install && npm run build`
5. **Build base image** — `docker build -t hyper-agent-base .`
6. **Configure secrets** — Copy `deploy/orchestrator.env.example` to `.env`; set API token, `OPENAI_API_KEY`, Cursor key at `/opt/agent-orchestrator/config/agent.env`
7. **SSH for git push** — Deploy key with `chmod 600`, add to GitHub repos
8. **Enable services** — `systemctl enable --now orchestrator-api orchestrator-dashboard`
9. **Monitor** — Dashboard at `:3000`, API at `:8000`; reports in `~/.hyper-orchestrator/reports/`

## Tests

```bash
pip install pytest
pytest tests/ -v
python -m py_compile core/*.py core/analyzers/*.py server/*.py server/routers/*.py
```

## License

MIT
