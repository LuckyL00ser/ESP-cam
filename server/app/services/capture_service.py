from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.models.tables import Capture
from app.repositories.capture_repo import CaptureRepository, DetectionRepository
from app.schemas.capture import CaptureRead, DetectionItem
from app.utils.timestamps import delta_ms, parse_optional_timestamp


class CaptureService:
    def __init__(self, capture_repo: CaptureRepository, detection_repo: DetectionRepository) -> None:
        self.capture_repo = capture_repo
        self.detection_repo = detection_repo
        self.settings = get_settings()

    @property
    def captures_dir(self) -> Path:
        return self.settings.captures_dir

    def annotated_path_for(self, filename: str) -> Path:
        return self.captures_dir / f"{Path(filename).stem}_annotated.jpg"

    def resolve_unique_path(self, filename: str) -> tuple[Path, str]:
        path = self.captures_dir / filename
        if not path.exists():
            return path, filename

        stem = path.stem
        suffix = path.suffix
        for index in range(1, 1000):
            candidate_name = f"{stem}_{index}{suffix}"
            candidate = self.captures_dir / candidate_name
            if not candidate.exists():
                return candidate, candidate_name
        raise RuntimeError("unable to allocate unique filename")

    def compute_latencies(
        self,
        *,
        capture_started_at: str | None,
        capture_finished_at: str | None,
        captured_at: str | None,
        received_at: datetime,
    ) -> tuple[datetime | None, datetime | None, float | None, float | None]:
        started = parse_optional_timestamp(capture_started_at)
        finished = parse_optional_timestamp(capture_finished_at or captured_at)
        capture_time_ms = None
        total_latency_ms = None

        if started and finished:
            capture_time_ms = round(delta_ms(started, finished), 1)
        if started:
            total_latency_ms = round(delta_ms(started, received_at), 1)

        return started, finished, capture_time_ms, total_latency_ms

    def save_upload(
        self,
        *,
        data: bytes,
        filename: str,
        capture_started_at: str | None,
        capture_finished_at: str | None,
        captured_at: str | None,
        received_at: datetime,
    ) -> Capture:
        path, final_filename = self.resolve_unique_path(filename)
        path.write_bytes(data)

        started, finished, capture_time_ms, total_latency_ms = self.compute_latencies(
            capture_started_at=capture_started_at,
            capture_finished_at=capture_finished_at,
            captured_at=captured_at,
            received_at=received_at,
        )

        capture = Capture(
            filename=final_filename,
            image_path=str(path),
            bytes=len(data),
            capture_started_at=started,
            capture_finished_at=finished,
            received_at=received_at,
            capture_time_ms=capture_time_ms,
            total_latency_ms=total_latency_ms,
            created_at=received_at,
        )
        saved = self.capture_repo.add(capture)
        print(
            "LATENCY "
            + " ".join(
                part
                for part in (
                    f"filename={saved.filename}",
                    f"capture_time_ms={capture_time_ms}",
                    f"total_latency_ms={total_latency_ms}",
                )
                if part
            )
        )
        return saved

    def set_annotated_path(self, capture: Capture, annotated_path: Path) -> Capture:
        capture.annotated_path = str(annotated_path)
        return self.capture_repo.update(capture)

    def to_read_model(self, capture: Capture) -> CaptureRead:
        detection = None
        if capture.id is not None:
            detection = self.detection_repo.get_by_capture_id(capture.id)

        image_url = f"/captures/{capture.filename}"
        if capture.annotated_path and Path(capture.annotated_path).is_file():
            image_url = f"/captures/{Path(capture.annotated_path).name}"

        detections: list[DetectionItem] = []
        detection_count = None
        inference_ms = None
        detected_at = None
        detector_model = None

        if detection is not None:
            raw = json.loads(detection.detections_json)
            detections = [DetectionItem.model_validate(item) for item in raw]
            detection_count = detection.detection_count
            inference_ms = detection.inference_ms
            detected_at = detection.detected_at
            detector_model = detection.model

        return CaptureRead(
            id=capture.id or 0,
            filename=capture.filename,
            image_url=image_url,
            bytes=capture.bytes,
            capture_started_at=capture.capture_started_at,
            capture_finished_at=capture.capture_finished_at,
            received_at=capture.received_at,
            capture_time_ms=capture.capture_time_ms,
            total_latency_ms=capture.total_latency_ms,
            detections=detections,
            detection_count=detection_count,
            inference_ms=inference_ms,
            detected_at=detected_at,
            detector_model=detector_model,
        )

    def get_latest(self) -> CaptureRead | None:
        capture = self.capture_repo.get_latest()
        if capture is None:
            return None
        return self.to_read_model(capture)

    def get_file_path(self, filename: str) -> Path | None:
        if filename.endswith("_annotated.jpg"):
            path = self.captures_dir / filename
            return path if path.is_file() else None

        capture = self.capture_repo.get_by_filename(filename)
        if capture is None:
            path = self.captures_dir / filename
            return path if path.is_file() else None
        return Path(capture.image_path)

    def list_captures(self) -> list[Capture]:
        return self.capture_repo.list_recent()
