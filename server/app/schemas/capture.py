from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DetectionItem(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: list[float]


class CaptureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    image_url: str
    bytes: int
    capture_started_at: datetime | None = None
    capture_finished_at: datetime | None = None
    received_at: datetime
    capture_time_ms: float | None = None
    total_latency_ms: float | None = None
    detections: list[DetectionItem] = []
    detection_count: int | None = None
    inference_ms: float | None = None
    detected_at: datetime | None = None
    detector_model: str | None = None


class LatestCaptureResponse(BaseModel):
    latest: CaptureRead | None = None


class UploadResponse(BaseModel):
    ok: bool = True
    filename: str
    bytes: int
    capture_started_at: str | None = None
    capture_finished_at: str | None = None
    received_at: str
    capture_time_ms: float | None = None
    total_latency_ms: float | None = None
    saved_to: str


class CaptureListItem(BaseModel):
    filename: str
    bytes: int
    url: str


class CaptureListResponse(BaseModel):
    count: int
    captures: list[CaptureListItem]
