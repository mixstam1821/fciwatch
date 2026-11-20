"""Match FCI scans with SEVIRI scans that were taken at nearly the same time.

FCI scans the full disk every 10 minutes (:00, :10, :20 ...).
SEVIRI scans the full disk every 15 minutes (:00, :15, :30, :45).
So the times that both have are :00 and :30, every hour.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Folder names for one scan look like 20260301T120000.
SCAN_TIME_FORMAT = "%Y%m%dT%H%M%S"


def parse_scan_time(text: str) -> datetime:
    """Read a scan time from a folder name such as '20260301T120000'."""
    return datetime.strptime(text, SCAN_TIME_FORMAT)


def format_scan_time(t: datetime) -> str:
    return t.strftime(SCAN_TIME_FORMAT)


def snap_time(t: datetime, step_min: int = 5) -> datetime:
    """Round a time to the nearest `step_min` minutes.

    The real sensing start of a scan can be a few seconds off the nominal time.
    Rounding gives us clean names and makes matching easy.
    """
    step = step_min * 60
    seconds = (t - t.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
    snapped = round(seconds / step) * step
    day_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start + timedelta(seconds=snapped)


def pair_scans(
    fci_times: list[datetime],
    seviri_times: list[datetime],
    tolerance_min: float = 5.0,
) -> list[tuple[datetime, datetime]]:
    """One-to-one matching of FCI and SEVIRI times.

    For every FCI time we take the closest unused SEVIRI time. The pair is kept only
    if the two times are not more than `tolerance_min` minutes apart.
    """
    tol = timedelta(minutes=tolerance_min)
    free = sorted(seviri_times)
    pairs: list[tuple[datetime, datetime]] = []
    for ft in sorted(fci_times):
        if not free:
            break
        best = min(free, key=lambda st: abs(st - ft))
        if abs(best - ft) <= tol:
            pairs.append((ft, best))
            free.remove(best)
    return pairs
