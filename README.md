# EmailTrackingServer

EmailTrackingServer is a standalone FastAPI service for email-open tracking.
It stores events in `data/EmailTracking.xlsx` and does not send email or
implement a dashboard, database, authentication, reports, scheduler, desktop
integration, or click-tracking logic.

## Requirements

- Python 3.12
- FastAPI
- Uvicorn
- openpyxl
- Pillow

All Python dependencies are pinned in `requirements.txt`. Render selects Python
3.12 from the root `.python-version` file.

## Local setup

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PORT = "8000"
$env:LOG_LEVEL = "INFO"
$env:DATA_FOLDER = "data"
uvicorn main:app --host 0.0.0.0 --port $env:PORT
```

Swagger UI is available at `http://localhost:8000/docs`.

## Environment variables

| Variable | Render value | Purpose |
| --- | --- | --- |
| `PORT` | `10000` | Port exposed by the Render web service |
| `LOG_LEVEL` | `INFO` | Application logging level |
| `DATA_FOLDER` | `/opt/render/project/src/data` | Persistent workbook directory |

When `DATA_FOLDER` is omitted locally, it defaults to the project-relative
`data/` directory. The application creates both the configured data directory
and `EmailTracking.xlsx` automatically. It also creates `logs/` automatically
and writes daily `YYYY-MM-DD.log` files.

## Deploy to Render

The repository includes a Render Blueprint in `render.yaml`.

1. Push this project to a GitHub, GitLab, or Bitbucket repository.
2. In the Render Dashboard, select **New > Blueprint**.
3. Connect the repository containing this project.
4. Confirm that Render detects the root `render.yaml` file.
5. Review the `email-tracking-server` service and apply the Blueprint.
6. Wait for the build and `/health` health check to pass.

Render uses these commands:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

The Blueprint provisions a Starter web service and a 1 GB persistent disk at
`/opt/render/project/src/data`. The disk is necessary because Render's default
filesystem is ephemeral; without it, Excel updates would be lost on restarts
and deployments. Persistent disks are not available on Render's free web-service
plan.

`runtime.txt` is intentionally not included because Render currently uses
`.python-version` for Python selection. A `Procfile` is unnecessary because the
Blueprint defines `startCommand` directly.

## Verify the deployment

Replace `<service-name>` with the deployed Render hostname:

```text
https://<service-name>.onrender.com/health
https://<service-name>.onrender.com/email/open/test123
https://<service-name>.onrender.com/docs
```

The health endpoint must return:

```json
{
  "status": "ok"
}
```

The open endpoint updates `EmailTracking.xlsx` and returns the existing
transparent 1x1 PNG. The Phase 2 tracking implementation is unchanged.

## Operational notes

- The persistent disk permits only one service instance and prevents
  zero-downtime deploys, which protects the single Excel workbook from
  concurrent instances.
- Daily application logs are written under `logs/` and emitted to standard
  output for viewing in the Render Dashboard. The local log files are ephemeral;
  Render's log stream should be used for production diagnostics.
- The `.gitignore` excludes generated workbooks, logs, virtual environments,
  caches, and local environment files.
"# EmailTrackingServer" 
"# EmailTrackingServer" 
