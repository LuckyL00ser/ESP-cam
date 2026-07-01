from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.dependencies import CaptureServiceDep, DetectionServiceDep
from app.schemas.capture import CaptureListItem, CaptureListResponse

router = APIRouter(tags=["captures"])


@router.get("/captures", response_model=CaptureListResponse)
def list_captures(capture_service: CaptureServiceDep) -> CaptureListResponse:
    captures = capture_service.list_captures()
    return CaptureListResponse(
        count=len(captures),
        captures=[
            CaptureListItem(
                filename=capture.filename,
                bytes=capture.bytes,
                url=f"/captures/{capture.filename}",
            )
            for capture in captures
        ],
    )


@router.get("/captures/{filename}")
def get_capture(filename: str, capture_service: CaptureServiceDep) -> FileResponse:
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = capture_service.get_file_path(filename)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(path, media_type="image/jpeg", filename=filename)


@router.get("/detections/{filename}")
def get_detections(filename: str, detection_service: DetectionServiceDep) -> dict:
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    payload = detection_service.get_detection_payload(filename)
    if payload is None:
        raise HTTPException(status_code=404, detail="No detections for this capture")

    return payload
