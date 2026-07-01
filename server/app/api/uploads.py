from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.dependencies import CaptureServiceDep, DetectionServiceDep
from app.schemas.capture import LatestCaptureResponse, UploadResponse
from app.utils.timestamps import filename_from_capture_timestamp

router = APIRouter(tags=["uploads"])


@router.get("/api")
def api_info(capture_service: CaptureServiceDep) -> dict:
    settings = get_settings()
    captures = capture_service.list_captures()
    return {
        "status": "ok",
        "upload_endpoint": "POST /upload",
        "upload_field": settings.upload_field_name,
        "timestamp_fields": ["capture_started_at", "capture_finished_at"],
        "captures_saved": len(captures),
        "latest_capture": captures[0].filename if captures else None,
        "capture_retention_minutes": settings.capture_retention_minutes,
        "capture_cleanup_interval_seconds": settings.capture_cleanup_interval_seconds,
        "detector_url": settings.detector_url_normalized or None,
    }


@router.get("/api/latest", response_model=LatestCaptureResponse)
def api_latest(capture_service: CaptureServiceDep) -> LatestCaptureResponse:
    return LatestCaptureResponse(latest=capture_service.get_latest())


@router.post("/upload", response_model=UploadResponse)
async def upload_image(
    capture_service: CaptureServiceDep,
    detection_service: DetectionServiceDep,
    image: UploadFile = File(...),
    capture_started_at: str | None = Form(None),
    capture_finished_at: str | None = Form(None),
    captured_at: str | None = Form(None),
) -> UploadResponse:
    settings = get_settings()

    if image.content_type not in (None, "image/jpeg", "application/octet-stream"):
        raise HTTPException(status_code=415, detail=f"Expected JPEG, got {image.content_type}")

    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image too large")

    name_ts = capture_finished_at or captured_at
    if name_ts:
        try:
            filename = filename_from_capture_timestamp(name_ts)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid capture timestamp") from exc
    else:
        filename = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "_server.jpg"

    received_at = datetime.now(UTC)
    capture = capture_service.save_upload(
        data=data,
        filename=filename,
        capture_started_at=capture_started_at,
        capture_finished_at=capture_finished_at,
        captured_at=captured_at,
        received_at=received_at,
    )

    if settings.detector_url_normalized:
        import asyncio

        asyncio.create_task(detection_service.run_detection(capture.filename))

    return UploadResponse(
        filename=capture.filename,
        bytes=capture.bytes,
        capture_started_at=capture_started_at,
        capture_finished_at=capture_finished_at or captured_at,
        received_at=received_at.isoformat(),
        capture_time_ms=capture.capture_time_ms,
        total_latency_ms=capture.total_latency_ms,
        saved_to=capture.image_path,
    )
