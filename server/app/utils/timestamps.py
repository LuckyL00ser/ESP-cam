from __future__ import annotations

import re
from datetime import UTC, datetime

ISO8601_Z = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$"
)
FILENAME_TS = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z(?:_\d+)?\.jpg$")


def parse_capture_timestamp(value: str) -> datetime:
    match = ISO8601_Z.match(value.strip())
    if not match:
        raise ValueError("invalid timestamp")
    year, month, day, hour, minute, second, fractional = match.groups()
    micro = int((fractional or "0").ljust(6, "0")[:6])
    return datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second), micro, tzinfo=UTC
    )


def parse_optional_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parse_capture_timestamp(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def delta_ms(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() * 1000.0


def filename_from_capture_timestamp(captured_at: str) -> str:
    match = ISO8601_Z.match(captured_at.strip())
    if not match:
        raise ValueError("invalid captured_at")

    year, month, day, hour, minute, second, fractional = match.groups()
    ms = (fractional or "0").ljust(3, "0")[:3]
    return f"{year}{month}{day}T{hour}{minute}{second}{ms}Z.jpg"


def timestamp_from_filename(filename: str) -> str | None:
    match = FILENAME_TS.match(filename)
    if not match:
        return None
    y, mo, d, h, mi, s, ms = match.groups()
    return f"{y}-{mo}-{d}T{h}:{mi}:{s}.{ms}Z"
