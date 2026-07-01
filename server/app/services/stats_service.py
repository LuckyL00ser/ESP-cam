from __future__ import annotations

import json
from collections import Counter

from sqlmodel import Session, select

from app.models.tables import Capture, Detection
from app.repositories.capture_repo import CaptureRepository, DetectionRepository
from app.schemas.stats import (
    ClassCount,
    ClassDistributionResponse,
    StatsSummary,
    TimeseriesPoint,
    TimeseriesResponse,
)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1)))))
    return round(ordered[index], 1)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


class StatsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.capture_repo = CaptureRepository(session)
        self.detection_repo = DetectionRepository(session)

    def summary(self) -> StatsSummary:
        captures = self.capture_repo.list_recent()
        capture_times = [c.capture_time_ms for c in captures if c.capture_time_ms is not None]
        total_latencies = [c.total_latency_ms for c in captures if c.total_latency_ms is not None]

        detections = self.session.exec(select(Detection)).all()
        inference_times = [d.inference_ms for d in detections if d.inference_ms is not None]

        return StatsSummary(
            count=len(captures),
            avg_capture_time_ms=_avg(capture_times),
            avg_total_latency_ms=_avg(total_latencies),
            avg_inference_ms=_avg(inference_times),
            p95_capture_time_ms=_percentile(capture_times, 95),
            p95_total_latency_ms=_percentile(total_latencies, 95),
            p95_inference_ms=_percentile(inference_times, 95),
        )

    def timeseries(self, limit: int) -> TimeseriesResponse:
        captures = self.capture_repo.list_recent(limit=limit)
        captures.reverse()
        points: list[TimeseriesPoint] = []

        for capture in captures:
            inference_ms = None
            detection_count = None
            if capture.id is not None:
                detection = self.detection_repo.get_by_capture_id(capture.id)
                if detection is not None:
                    inference_ms = detection.inference_ms
                    detection_count = detection.detection_count

            points.append(
                TimeseriesPoint(
                    filename=capture.filename,
                    received_at=capture.received_at.isoformat(),
                    capture_time_ms=capture.capture_time_ms,
                    total_latency_ms=capture.total_latency_ms,
                    inference_ms=inference_ms,
                    detection_count=detection_count,
                )
            )

        return TimeseriesResponse(points=points)

    def class_distribution(self, limit: int) -> ClassDistributionResponse:
        rows = self.detection_repo.list_with_captures(limit=limit)
        counter: Counter[str] = Counter()

        for detection, _capture in rows:
            for item in json.loads(detection.detections_json):
                class_name = item.get("class_name")
                if class_name:
                    counter[class_name] += 1

        classes = [
            ClassCount(class_name=name, count=count)
            for name, count in counter.most_common()
        ]
        return ClassDistributionResponse(classes=classes)

    def legacy_latency_payload(self) -> dict:
        summary = self.summary()
        captures = self.capture_repo.list_recent()
        return {
            "count": summary.count,
            "avg_capture_time_ms": summary.avg_capture_time_ms,
            "avg_total_latency_ms": summary.avg_total_latency_ms,
            "samples": [
                {
                    "filename": c.filename,
                    "capture_started_at": c.capture_started_at.isoformat() if c.capture_started_at else None,
                    "capture_finished_at": c.capture_finished_at.isoformat() if c.capture_finished_at else None,
                    "received_at": c.received_at.isoformat(),
                    "capture_time_ms": c.capture_time_ms,
                    "total_latency_ms": c.total_latency_ms,
                }
                for c in captures
            ],
        }
