from __future__ import annotations

from fastapi import APIRouter, Query

from app.config import get_settings
from app.dependencies import StatsServiceDep
from app.schemas.stats import ClassDistributionResponse, StatsSummary, TimeseriesResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
def stats_summary(stats_service: StatsServiceDep) -> StatsSummary:
    return stats_service.summary()


@router.get("/timeseries", response_model=TimeseriesResponse)
def stats_timeseries(
    stats_service: StatsServiceDep,
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> TimeseriesResponse:
    settings = get_settings()
    return stats_service.timeseries(limit or settings.stats_timeseries_default_limit)


@router.get("/classes", response_model=ClassDistributionResponse)
def stats_classes(
    stats_service: StatsServiceDep,
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> ClassDistributionResponse:
    settings = get_settings()
    return stats_service.class_distribution(limit or settings.stats_classes_default_limit)


@router.get("/latency")
def legacy_latency(stats_service: StatsServiceDep) -> dict:
    return stats_service.legacy_latency_payload()
