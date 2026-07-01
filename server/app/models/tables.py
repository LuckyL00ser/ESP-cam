from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Capture(SQLModel, table=True):
    __tablename__ = "captures"

    id: int | None = Field(default=None, primary_key=True)
    filename: str = Field(unique=True, index=True)
    image_path: str
    annotated_path: str | None = None
    bytes: int
    capture_started_at: datetime | None = None
    capture_finished_at: datetime | None = None
    received_at: datetime
    capture_time_ms: float | None = None
    total_latency_ms: float | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )


class Detection(SQLModel, table=True):
    __tablename__ = "detections"

    id: int | None = Field(default=None, primary_key=True)
    capture_id: int = Field(foreign_key="captures.id", unique=True, index=True)
    model: str
    inference_ms: float
    detection_count: int
    detections_json: str
    detected_at: datetime
