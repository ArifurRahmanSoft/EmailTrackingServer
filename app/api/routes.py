"""Public HTTP endpoints for the tracking server."""

import logging
import os
import platform
from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Path, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from app.models.statistics import SampleStatistics
from app.services.database_tracking import DatabaseTrackingService
from app.services.excel_tracking import ExcelTrackingService
from app.services.tracking_debug import TrackingDebugService
from app.services.tracking_pixel import get_transparent_pixel
from config.settings import PROJECT_ROOT, load_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = load_settings()
tracking_service = ExcelTrackingService(settings.tracking_file)
database_service = DatabaseTrackingService(settings.database_url)
debug_service = TrackingDebugService(tracking_service.workbook_path)
DEBUG_TAG = "Development / Debug Only"

# Tracking IDs remain URL-safe and must contain at least one character.
TrackingId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="A URL-safe tracking identifier.",
    ),
]


@router.get("/health", tags=["System"], summary="Check service health")
async def health_check() -> dict[str, str]:
    """Return a lightweight liveness response."""
    return {"status": "ok"}


@router.get(
    "/email/open/{tracking_id}",
    tags=["Tracking"],
    summary="Return the email open tracking pixel",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def track_email_open(tracking_id: TrackingId, request: Request) -> Response:
    """Validate the ID and return a transparent 1×1 PNG.

    The PNG is returned even when the tracking workbook cannot be updated.
    """
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    occurred_at = datetime.now()

    try:
        result = await run_in_threadpool(
            tracking_service.record_open,
            tracking_id,
            client_ip,
            user_agent,
            occurred_at,
        )
        logger.info(
            "DateTime=%s TrackingId=%s ClientIP=%s OpenCount=%d Status=%s Error=None",
            occurred_at.isoformat(),
            tracking_id,
            client_ip,
            result.open_count,
            result.status,
        )
        try:
            await run_in_threadpool(
                database_service.record_open,
                tracking_id,
                result.open_count,
                client_ip,
                user_agent,
                occurred_at,
            )
            logger.info(
                "PostgreSQL tracking update completed: TrackingId=%s OpenCount=%d",
                tracking_id,
                result.open_count,
            )
        except Exception as database_exc:
            # Excel remains authoritative when Neon is unavailable.
            logger.error(
                "PostgreSQL tracking update failed: TrackingId=%s Error=%s",
                tracking_id,
                database_exc,
                exc_info=True,
            )
    except Exception as exc:
        # Storage failures must never prevent an email client loading the pixel.
        logger.error(
            "DateTime=%s TrackingId=%s ClientIP=%s OpenCount=unknown "
            "Status=error Error=%s",
            occurred_at.isoformat(),
            tracking_id,
            client_ip,
            exc,
            exc_info=True,
        )

    return Response(
        content=get_transparent_pixel(),
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get(
    "/email/click/{tracking_id}",
    tags=["Tracking"],
    summary="Handle a tracked-link click",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def track_email_click(tracking_id: TrackingId) -> RedirectResponse:
    """Return a placeholder redirect until click destinations are implemented."""
    _ = tracking_id
    return RedirectResponse(url="/health", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get(
    "/api/statistics",
    tags=["Statistics"],
    summary="Return placeholder tracking statistics",
    response_model=SampleStatistics,
)
async def get_statistics() -> SampleStatistics:
    """Return sample data; no statistics are calculated in Phase 1."""
    return SampleStatistics(
        status="sample",
        total_opens=0,
        total_clicks=0,
        message="Statistics tracking is not implemented yet.",
    )


@router.get(
    "/api/tracking",
    tags=[DEBUG_TAG],
    summary="Development only: list tracking records",
    description="Development / Debug Only. Reads all records without modifying Excel.",
    response_model=None,
)
async def get_tracking_records() -> list[dict[str, object]] | JSONResponse:
    """Return all workbook records or a message when no workbook exists."""
    logger.info("Debug endpoint requested: GET /api/tracking")
    if not debug_service.workbook_path.is_file():
        logger.info("Debug tracking list completed: workbook not found")
        return JSONResponse(content={"message": "No tracking records found."})

    records = await run_in_threadpool(debug_service.read_records)
    logger.info("Debug tracking list completed: total_records=%d", len(records))
    return records


@router.get(
    "/api/download-excel",
    tags=[DEBUG_TAG],
    summary="Development only: download the tracking workbook",
    description="Development / Debug Only. Downloads Excel without modifying it.",
    response_model=None,
    responses={404: {"description": "Tracking workbook not found"}},
)
async def download_tracking_excel() -> FileResponse | JSONResponse:
    """Download the current workbook or return the required 404 response."""
    logger.info("Debug endpoint requested: GET /api/download-excel")
    if not debug_service.workbook_path.is_file():
        logger.info("Debug Excel download failed: workbook not found")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "EmailTracking.xlsx not found."},
        )

    logger.info("Debug Excel download started: path=%s", debug_service.workbook_path)
    return FileResponse(
        path=debug_service.workbook_path,
        filename="EmailTracking.xlsx",
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )


@router.get(
    "/api/debug",
    tags=[DEBUG_TAG],
    summary="Development only: inspect server diagnostics",
    description="Development / Debug Only. Returns runtime and workbook diagnostics.",
)
async def get_debug_information() -> dict[str, object]:
    """Return application, runtime, and read-only workbook diagnostics."""
    logger.info("Debug endpoint requested: GET /api/debug")
    excel_exists = debug_service.workbook_path.is_file()
    total_records = (
        await run_in_threadpool(debug_service.count_records) if excel_exists else 0
    )
    response: dict[str, object] = {
        "application": "EmailTrackingServer",
        "working_directory": os.getcwd(),
        "base_directory": str(PROJECT_ROOT),
        "excel_path": str(debug_service.workbook_path),
        "excel_exists": excel_exists,
        "total_records": total_records,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": platform.python_version(),
        "operating_system": f"{platform.system()} {platform.release()}",
    }
    logger.info(
        "Debug diagnostics completed: excel_exists=%s total_records=%d",
        excel_exists,
        total_records,
    )
    return response


@router.get(
    "/api/database/status",
    tags=[DEBUG_TAG],
    summary="Development only: inspect PostgreSQL status",
    description=(
        "Development / Debug Only. Reports Neon connectivity, table presence, "
        "and the current email_tracking row count."
    ),
)
async def get_database_status() -> dict[str, object]:
    """Return read-only PostgreSQL connection and table diagnostics."""
    logger.info("Debug endpoint requested: GET /api/database/status")
    database_status = await run_in_threadpool(database_service.get_status)
    if database_status.error:
        logger.error("Database status check failed: %s", database_status.error)
    else:
        logger.info(
            "Database status completed: connected=%s table_exists=%s "
            "total_records=%d",
            database_status.connected,
            database_status.table_exists,
            database_status.total_records,
        )
    return {
        "database_connected": database_status.connected,
        "table_exists": database_status.table_exists,
        "total_records": database_status.total_records,
    }
