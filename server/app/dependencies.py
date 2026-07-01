from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.database import SessionDep
from app.repositories.capture_repo import CaptureRepository, DetectionRepository
from app.services.capture_service import CaptureService
from app.services.cleanup_service import CleanupService
from app.services.detection_service import DetectionService
from app.services.stats_service import StatsService


def get_capture_service(session: SessionDep) -> CaptureService:
    return CaptureService(CaptureRepository(session), DetectionRepository(session))


def get_detection_service(session: SessionDep) -> DetectionService:
    return DetectionService(session)


def get_cleanup_service(session: SessionDep) -> CleanupService:
    return CleanupService(session)


def get_stats_service(session: SessionDep) -> StatsService:
    return StatsService(session)


CaptureServiceDep = Annotated[CaptureService, Depends(get_capture_service)]
DetectionServiceDep = Annotated[DetectionService, Depends(get_detection_service)]
CleanupServiceDep = Annotated[CleanupService, Depends(get_cleanup_service)]
StatsServiceDep = Annotated[StatsService, Depends(get_stats_service)]
