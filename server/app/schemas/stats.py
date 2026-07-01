from __future__ import annotations

from pydantic import BaseModel


class StatsSummary(BaseModel):
    count: int
    avg_capture_time_ms: float | None = None
    avg_total_latency_ms: float | None = None
    avg_inference_ms: float | None = None
    p95_capture_time_ms: float | None = None
    p95_total_latency_ms: float | None = None
    p95_inference_ms: float | None = None


class TimeseriesPoint(BaseModel):
    filename: str
    received_at: str
    capture_time_ms: float | None = None
    total_latency_ms: float | None = None
    inference_ms: float | None = None
    detection_count: int | None = None


class TimeseriesResponse(BaseModel):
    points: list[TimeseriesPoint]


class ClassCount(BaseModel):
    class_name: str
    count: int


class ClassDistributionResponse(BaseModel):
    classes: list[ClassCount]
