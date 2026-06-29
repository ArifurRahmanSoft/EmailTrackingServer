"""Public HTTP endpoints for the tracking server."""

import logging
from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Path, Request, status
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from app.models.statistics import SampleStatistics
from app.services.excel_tracking import ExcelTrackingService
from app.services.tracking_pixel import get_transparent_pixel
from config.settings import load_settings

router = APIRouter()
logger = logging.getLogger(__name__)
tracking_service = ExcelTrackingService(load_settings().tracking_file)

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
