from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.dependencies import CaptureServiceDep
from app.schemas.capture import CaptureBrowseResponse, PaginatedCapturesResponse

router = APIRouter(prefix="/api/captures", tags=["history"])


@router.get("", response_model=PaginatedCapturesResponse)
def list_captures_history(
    capture_service: CaptureServiceDep,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> PaginatedCapturesResponse:
    captures, total = capture_service.list_paginated(offset=offset, limit=limit)
    return PaginatedCapturesResponse(
        total=total,
        limit=limit,
        offset=offset,
        captures=captures,
    )


@router.get("/{capture_id}", response_model=CaptureBrowseResponse)
def get_capture_by_id(capture_id: int, capture_service: CaptureServiceDep) -> CaptureBrowseResponse:
    context = capture_service.get_browse_context(capture_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Capture not found")
    return CaptureBrowseResponse.model_validate(context)
