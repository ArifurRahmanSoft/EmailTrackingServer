# EmailTrackingServer

EmailTrackingServer is a standalone FastAPI service for email-open tracking.
It dual-writes open events to `data/EmailTracking.xlsx` and Neon PostgreSQL.
Excel support remains active and tracking continues when PostgreSQL is
temporarily unavailable.

The project does not send email or implement a dashboard, authentication,
reports, scheduler, or desktop integration.

## Requirements

- Python 3.12
- FastAPI and Uvicorn
- openpyxl and Pillow
- SQLAlchemy 2 ORM
- psycopg 3 PostgreSQL driver
- Neon PostgreSQL

All Python dependencies are pinned in `requirements.txt`. Render selects Python
3.12 from the root `.python-version` file.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes on Render | Neon PostgreSQL connection string |
| `PORT` | Yes on Render | Port exposed by the web service |
| `LOG_LEVEL` | No | Logging level; defaults to `INFO` |
| `DATA_FOLDER` | No | Excel folder; defaults locally to `data/` |

Never commit `DATABASE_URL` or place it directly in source code. The application
accepts Neon's standard `postgresql://` URL and selects the psycopg 3 driver
automatically.

## Local setup

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PORT = "8000"
$env:LOG_LEVEL = "INFO"
$env:DATA_FOLDER = "data"
$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
uvicorn main:app --host 0.0.0.0 --port $env:PORT
```

Swagger UI is available at `http://localhost:8000/docs`.

## Automatic database setup

At application startup, SQLAlchemy calls `Base.metadata.create_all()` using
`DATABASE_URL`. This creates the `email_tracking` table if it does not exist;
no manual SQL or migration command is required for this phase. Existing tables
and rows are left intact.

The table contains:

- `id` as its primary key and unique `tracking_id`
- `recipient_email` and `sender_email`
- `open_count` and `click_count`
- `first_open`, `last_open`, `first_click`, and `last_click`
- `created_at` and `updated_at`
- `last_ip` and `user_agent`

For each successful Excel open update, PostgreSQL receives an atomic upsert with
the resulting Excel `OpenCount`. An existing database row retains `first_open`
while `open_count`, `last_open`, `last_ip`, `user_agent`, and `updated_at` are
updated. A database error is logged and never changes the tracking-pixel HTTP
response or rolls back the Excel write.

## Excel storage

The application creates the configured data folder and `EmailTracking.xlsx`
automatically. Daily logs are written to `logs/YYYY-MM-DD.log`. The existing
Excel schema and tracking behavior remain unchanged.

## Click tracking

Tracked links use this endpoint:

```text
GET /email/click/{tracking_id}?url={encoded_original_url}
```

Example:

```text
/email/click/7d19af31-2d65-49db-b52e-2c92b5d39b61?url=https%3A%2F%2Fpowersoft.com
```

The complete flow is:

1. Validate that `tracking_id` contains only URL-safe letters, numbers,
   underscores, or hyphens.
2. Validate that `url` is a complete HTTP or HTTPS URL.
3. Find and lock the existing PostgreSQL row for the tracking ID.
4. Return HTTP 404 without redirecting when the row does not exist.
5. Increment `click_count`, set `first_click` only when it is currently null,
   and update `last_click`, `last_ip`, `user_agent`, and `updated_at` in UTC.
6. Commit the transaction.
7. Return an immediate HTTP 302 redirect to the exact original URL.

Missing or invalid input returns HTTP 400. A redirect is never issued unless
the database transaction succeeds.

## Development endpoints

Temporary debug routes appear in Swagger under **Development / Debug Only**:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/tracking` | List Excel tracking records |
| `GET /api/download-excel` | Download the current workbook |
| `GET /api/debug` | Show application and Excel diagnostics |
| `GET /api/database/status` | Show database connection, table, and row count |

Example database status response:

```json
{
  "database_connected": true,
  "table_exists": true,
  "total_records": 12
}
```

## Deploy to Render

The repository includes `render.yaml` with these commands:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

1. Push the project to a Git repository connected to Render.
2. In Render, create or sync the Blueprint from `render.yaml`.
3. In the service Environment page, set the existing Neon `DATABASE_URL` as a
   secret environment variable.
4. Deploy and wait for the `/health` check to pass.
5. Open `/api/database/status` and confirm all three values indicate success.

Render preserves the separately configured `DATABASE_URL` because the Blueprint
does not define or overwrite it.

## Verification URLs

```text
https://<service-name>.onrender.com/health
https://<service-name>.onrender.com/email/open/test123
https://<service-name>.onrender.com/email/click/test123?url=https%3A%2F%2Fpowersoft.com
https://<service-name>.onrender.com/api/database/status
https://<service-name>.onrender.com/docs
```

The `/health` response remains:

```json
{
  "status": "ok"
}
```

## Tests

Install development dependencies and run the click-tracking test suite:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

The tests use an in-memory fake database service and never connect to Neon or
modify the Excel workbook.
