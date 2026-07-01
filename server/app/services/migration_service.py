from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from app.config import get_settings
from app.models.tables import Capture, Detection
from app.repositories.capture_repo import CaptureRepository, DetectionRepository
from app.utils.timestamps import (
    delta_ms,
    parse_capture_timestamp,
    parse_optional_timestamp,
    timestamp_from_filename,
)


def _parse_jsonl_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        try:
            value = ast.literal_eval(line)
            return value if isinstance(value, dict) else None
        except (SyntaxError, ValueError):
            return None


class MigrationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.capture_repo = CaptureRepository(session)
        self.detection_repo = DetectionRepository(session)
        self.settings = get_settings()

    def import_jsonl_if_needed(self) -> int:
        if self.capture_repo.count() > 0:
            return 0

        captures_dir = self.settings.captures_dir
        latency_log = captures_dir / "latency.jsonl"
        detections_log = captures_dir / "detections.jsonl"

        if not latency_log.is_file():
            return 0

        imported = 0
        detection_by_filename: dict[str, dict] = {}

        if detections_log.is_file():
            for line in detections_log.read_text(encoding="utf-8").splitlines():
                entry = _parse_jsonl_line(line)
                if entry and entry.get("filename"):
                    detection_by_filename[entry["filename"]] = entry

        for line in latency_log.read_text(encoding="utf-8").splitlines():
            entry = _parse_jsonl_line(line)
            if not entry:
                continue

            filename = entry.get("filename")
            if not filename:
                continue

            image_path = captures_dir / filename
            if not image_path.is_file():
                continue

            started_at = parse_optional_timestamp(entry.get("capture_started_at"))
            finished_at = parse_optional_timestamp(
                entry.get("capture_finished_at") or entry.get("captured_at")
            )
            received_at = parse_optional_timestamp(entry.get("received_at")) or datetime.fromtimestamp(
                image_path.stat().st_mtime, tz=UTC
            )

            capture_time_ms = entry.get("capture_time_ms") or entry.get("capture_duration_ms")
            total_latency_ms = (
                entry.get("total_latency_ms")
                or entry.get("delta_start_ms")
                or entry.get("delta_ms")
            )

            if capture_time_ms is None and started_at and finished_at:
                capture_time_ms = round(delta_ms(started_at, finished_at), 1)
            if total_latency_ms is None and started_at:
                total_latency_ms = round(delta_ms(started_at, received_at), 1)

            if finished_at is None:
                ts = timestamp_from_filename(filename)
                finished_at = parse_optional_timestamp(ts)

            annotated_path = captures_dir / f"{Path(filename).stem}_annotated.jpg"
            capture = Capture(
                filename=filename,
                image_path=str(image_path),
                annotated_path=str(annotated_path) if annotated_path.is_file() else None,
                bytes=entry.get("bytes", image_path.stat().st_size),
                capture_started_at=started_at,
                capture_finished_at=finished_at,
                received_at=received_at,
                capture_time_ms=capture_time_ms,
                total_latency_ms=total_latency_ms,
                created_at=received_at,
            )
            saved = self.capture_repo.add(capture)
            imported += 1

            detection_entry = detection_by_filename.get(filename)
            if detection_entry and saved.id is not None:
                detections = detection_entry.get("detections", [])
                detected_at = parse_optional_timestamp(detection_entry.get("detected_at")) or datetime.now(
                    UTC
                )
                self.detection_repo.add(
                    Detection(
                        capture_id=saved.id,
                        model=detection_entry.get("model", "unknown"),
                        inference_ms=float(detection_entry.get("inference_ms", 0.0)),
                        detection_count=int(
                            detection_entry.get("detection_count", len(detections))
                        ),
                        detections_json=json.dumps(detections),
                        detected_at=detected_at,
                    )
                )

        if imported:
            print(f"MIGRATION imported {imported} capture(s) from JSONL logs")
        return imported
