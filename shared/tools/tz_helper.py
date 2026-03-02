#!/usr/bin/env python3
"""
tz_helper.py — Timezone display helper
All internal timestamps: UTC (ISO 8601)
All human-facing display: America/New_York (EST/EDT)
"""
from datetime import datetime, timezone, timedelta

# America/New_York offsets
# EST = UTC-5  (Nov first Sun → Mar second Sun)
# EDT = UTC-4  (Mar second Sun → Nov first Sun)
# DST 2026: starts Mar 8, ends Nov 1

def _ny_offset(dt_utc: datetime) -> int:
    """Return UTC offset in hours for America/New_York."""
    year = dt_utc.year
    # Second Sunday of March
    dst_start = datetime(year, 3, 8, 2, 0, tzinfo=timezone.utc)
    dst_start += timedelta(days=(6 - dst_start.weekday()) % 7)
    # First Sunday of November
    dst_end = datetime(year, 11, 1, 2, 0, tzinfo=timezone.utc)
    dst_end += timedelta(days=(6 - dst_end.weekday()) % 7)
    if dst_start <= dt_utc < dst_end:
        return -4  # EDT
    return -5  # EST

def now_est() -> datetime:
    """Current time in America/New_York (EST/EDT)."""
    utc = datetime.now(timezone.utc)
    offset = _ny_offset(utc)
    return utc + timedelta(hours=offset)

def utc_to_est(dt_utc: datetime) -> datetime:
    """Convert UTC datetime to EST/EDT."""
    offset = _ny_offset(dt_utc)
    return dt_utc + timedelta(hours=offset)

def fmt(dt_utc: datetime = None, include_tz: bool = True) -> str:
    """Format UTC datetime as EST/EDT display string."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    offset = _ny_offset(dt_utc)
    local = dt_utc + timedelta(hours=offset)
    tz_label = "EDT" if offset == -4 else "EST"
    if include_tz:
        return local.strftime(f"%Y-%m-%d %H:%M {tz_label}")
    return local.strftime("%Y-%m-%d %H:%M")

def fmt_short(dt_utc: datetime = None) -> str:
    """HH:MM TZ format for inline use."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    offset = _ny_offset(dt_utc)
    local = dt_utc + timedelta(hours=offset)
    tz_label = "EDT" if offset == -4 else "EST"
    return local.strftime(f"%H:%M {tz_label}")

if __name__ == "__main__":
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)
    print(f"UTC:  {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"EST:  {fmt()}")
    print(f"Short: {fmt_short()}")
