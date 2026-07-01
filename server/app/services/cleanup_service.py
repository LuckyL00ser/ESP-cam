from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session

from app.config import get_settings
from app.repositories.capture_repo import CaptureRepository


class CleanupService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.capture_repo = CaptureRepository(session)
        self.settings = get_settings()

    def cleanup_old_captures(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=self.settings.capture_retention_minutes)
        stale = self.capture_repo.list_older_than(cutoff)
        deleted_names: list[str] = []

        for capture in stale:
            for path_value in (capture.image_path, capture.annotated_path):
                if not path_value:
                    continue
                path = Path(path_value)
                if path.is_file():
                    path.unlink()
            deleted_names.append(capture.filename)
            self.capture_repo.delete(capture)

        if deleted_names:
            print(
                f"CLEANUP removed {len(deleted_names)} capture(s) older than "
                f"{self.settings.capture_retention_minutes}m: {', '.join(deleted_names)}"
            )

        return len(deleted_names)
