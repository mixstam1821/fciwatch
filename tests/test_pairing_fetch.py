from datetime import datetime, timedelta
from types import SimpleNamespace

from fciwatch.fetch import select_products
from fciwatch.pairing import format_scan_time, pair_scans, parse_scan_time, snap_time


def test_snap_time():
    assert snap_time(datetime(2026, 3, 1, 11, 59, 52)) == datetime(2026, 3, 1, 12, 0)
    assert snap_time(datetime(2026, 3, 1, 12, 31, 10)) == datetime(2026, 3, 1, 12, 30)


def test_scan_time_roundtrip():
    t = datetime(2026, 3, 1, 12, 30)
    assert parse_scan_time(format_scan_time(t)) == t


def test_pairing_picks_common_times_and_is_one_to_one():
    base = datetime(2026, 3, 1, 12, 0)
    fci = [base + timedelta(minutes=10 * i) for i in range(7)]  # every 10 min
    sev = [base + timedelta(minutes=15 * i) for i in range(5)]  # every 15 min
    pairs = pair_scans(fci, sev, tolerance_min=2)
    assert [(a.minute, b.minute) for a, b in pairs] == [(0, 0), (30, 30), (0, 0)]
    assert len({b for _, b in pairs}) == len(pairs)  # no SEVIRI scan used twice


def test_pairing_respects_tolerance():
    t = datetime(2026, 3, 1, 12, 0)
    assert pair_scans([t], [t + timedelta(minutes=9)], tolerance_min=5) == []


def test_select_products_keeps_only_half_hours():
    base = datetime(2026, 3, 1, 12, 0)
    prods = [
        SimpleNamespace(sensing_start=base + timedelta(minutes=m, seconds=7))
        for m in range(0, 61, 10)
    ]
    chosen = select_products(prods, every_min=30)
    assert [t.minute for t, _ in chosen] == [0, 30, 0]
