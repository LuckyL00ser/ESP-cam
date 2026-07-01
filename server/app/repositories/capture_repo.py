from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.tables import Capture, Detection


class CaptureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def count(self) -> int:
        return len(self.session.exec(select(Capture)).all())

    def get_by_filename(self, filename: str) -> Capture | None:
        return self.session.exec(select(Capture).where(Capture.filename == filename)).first()

    def get_latest(self) -> Capture | None:
        statement = select(Capture).order_by(Capture.received_at.desc())
        return self.session.exec(statement).first()

    def list_recent(self, limit: int | None = None) -> list[Capture]:
        statement = select(Capture).order_by(Capture.received_at.desc())
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def list_older_than(self, cutoff: datetime) -> list[Capture]:
        statement = select(Capture).where(Capture.received_at < cutoff)
        return list(self.session.exec(statement).all())

    def add(self, capture: Capture) -> Capture:
        self.session.add(capture)
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def update(self, capture: Capture) -> Capture:
        self.session.add(capture)
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def delete(self, capture: Capture) -> None:
        detection = self.session.exec(
            select(Detection).where(Detection.capture_id == capture.id)
        ).first()
        if detection is not None:
            self.session.delete(detection)
        self.session.delete(capture)
        self.session.commit()


class DetectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_capture_id(self, capture_id: int) -> Detection | None:
        return self.session.exec(
            select(Detection).where(Detection.capture_id == capture_id)
        ).first()

    def get_by_filename(self, filename: str) -> Detection | None:
        capture = self.session.exec(select(Capture).where(Capture.filename == filename)).first()
        if capture is None or capture.id is None:
            return None
        return self.get_by_capture_id(capture.id)

    def add(self, detection: Detection) -> Detection:
        self.session.add(detection)
        self.session.commit()
        self.session.refresh(detection)
        return detection

    def list_with_captures(self, limit: int) -> list[tuple[Detection, Capture]]:
        statement = (
            select(Detection, Capture)
            .join(Capture, Detection.capture_id == Capture.id)
            .order_by(Capture.received_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())
