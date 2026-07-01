from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlmodel import Session

from app.config import get_settings
from app.models.tables import Detection
from app.repositories.capture_repo import CaptureRepository, DetectionRepository
from app.services.capture_service import CaptureService


class DetectionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.capture_repo = CaptureRepository(session)
        self.detection_repo = DetectionRepository(session)
        self.capture_service = CaptureService(self.capture_repo, self.detection_repo)
        self.settings = get_settings()

    async def run_detection(self, filename: str) -> None:
        detector_url = self.settings.detector_url_normalized
        if not detector_url:
            return

        capture = self.capture_repo.get_by_filename(filename)
        if capture is None or capture.id is None:
            return

        path = Path(capture.image_path)
        if not path.is_file():
            return

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                with path.open("rb") as fh:
                    response = await client.post(
                        f"{detector_url}/detect",
                        params={"annotate": "true"},
                        files={"image": (filename, fh, "image/jpeg")},
                    )
                response.raise_for_status()
                result = response.json()
        except Exception as exc:
            print(f"DETECT failed filename={filename}: {exc}")
            return

        detections = result.get("detections", [])
        detected_at = datetime.now(UTC)
        detection = Detection(
            capture_id=capture.id,
            model=result.get("model", "unknown"),
            inference_ms=float(result.get("inference_ms", 0.0)),
            detection_count=int(result.get("detection_count", len(detections))),
            detections_json=json.dumps(detections),
            detected_at=detected_at,
        )
        self.detection_repo.add(detection)
        print(
            f"DETECT filename={filename} count={detection.detection_count} "
            f"inference_ms={detection.inference_ms}"
        )

        annotated_b64 = result.get("annotated_jpeg_b64")
        if annotated_b64:
            annotated_path = self.capture_service.annotated_path_for(filename)
            annotated_path.write_bytes(base64.b64decode(annotated_b64))
            self.capture_service.set_annotated_path(capture, annotated_path)

    def get_detection_payload(self, filename: str) -> dict | None:
        detection = self.detection_repo.get_by_filename(filename)
        if detection is None:
            return None
        return {
            "filename": filename,
            "model": detection.model,
            "inference_ms": detection.inference_ms,
            "detection_count": detection.detection_count,
            "detections": json.loads(detection.detections_json),
            "detected_at": detection.detected_at.isoformat(),
        }
