"""Command line interface.  Run  `fciwatch --help`  to see all commands.

fciwatch demo     make a report from fake data (no downloads, no credentials)
fciwatch fetch    download FCI + SEVIRI scans from the EUMETSAT Data Store
fciwatch compare  compare downloaded scans and write results.csv
fciwatch report   turn results.csv into an HTML report
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .channels import DEFAULT_PAIRS, PAIRS
from .drift import compute_daily_drift, load_records, summarize
from .report import build_report


def _parse_time(text: str) -> datetime:
    """Accept '2026-03-01' or '2026-03-01T12:00'. Times are UTC."""
    return datetime.fromisoformat(text)


def _write_report(df, out: Path, args, title: str, banner: str | None = None) -> None:
    daily = compute_daily_drift(
        df,
        baseline_start=getattr(args, "baseline_start", None),
        baseline_end=getattr(args, "baseline_end", None),
        baseline_days=args.baseline_days,
        value="bias_ref",
    )
    slope_daily = compute_daily_drift(df, baseline_days=args.baseline_days, value="slope")
    summary = summarize(daily, threshold_k=args.threshold)
    html_text = build_report(
        daily,
        slope_daily,
        summary,
        args.threshold,
        title=title,
        banner=banner,
        echarts_path=getattr(args, "echarts_path", None),
    )
    out.write_text(html_text, encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"\nReport written to {out}")


def cmd_demo(args) -> int:
    from .synthetic import make_synthetic_records

    df = make_synthetic_records(days=args.days)
    _write_report(
        df,
        Path(args.out),
        args,
        title="FCI calibration watch (DEMO)",
        banner="SYNTHETIC DEMO DATA. These are not real measurements. A drift and a step "
        "were added on purpose to show how the report looks.",
    )
    return 0


def cmd_fetch(args) -> int:
    from .fetch import FCI_COLLECTION, SEVIRI_COLLECTION, fetch_collection

    start, end = _parse_time(args.start), _parse_time(args.end)
    out = Path(args.out)
    for kind, default_id, override in (
        ("fci", FCI_COLLECTION, args.fci_collection),
        ("seviri", SEVIRI_COLLECTION, args.seviri_collection),
    ):
        n = fetch_collection(
            override or default_id, kind, start, end, out, args.every_min, args.dry_run
        )
        print(f"{kind}: {n} scan(s) {'planned' if args.dry_run else 'downloaded'}")
    return 0


def cmd_compare(args) -> int:
    try:
        import pyresample  # noqa: F401
        import satpy  # noqa: F401
    except ImportError as err:
        raise SystemExit("Missing dependencies. Run:  pip install 'fciwatch[read]'") from err

    from .pipeline import CompareConfig, compare_directory

    cfg = CompareConfig(
        lat_min=args.bbox[0],
        lat_max=args.bbox[1],
        lon_min=args.bbox[2],
        lon_max=args.bbox[3],
        box_factor=args.box_factor,
        max_std_k=args.max_std,
        tolerance_min=args.tolerance_min,
        pairs=tuple(args.pairs),
    )
    n = compare_directory(Path(args.data), Path(args.out), cfg)
    print(f"{n} new record(s) written to {args.out}")
    return 0


def cmd_report(args) -> int:
    df = load_records(args.results)
    _write_report(df, Path(args.out), args, title=args.title)
    return 0


def _add_report_options(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="alert level in kelvin (your choice, not an official limit). Default 0.3",
    )
    p.add_argument(
        "--baseline-days",
        type=int,
        default=14,
        help="use the first N days as the baseline (zero point). Default 14",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fciwatch", description=__doc__.split("\n")[0])
    p.add_argument("--version", action="version", version=f"fciwatch {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="show more log messages")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="make a report from synthetic data")
    d.add_argument("--out", default="fciwatch_demo.html")
    d.add_argument("--days", type=int, default=120)
    _add_report_options(d)
    d.set_defaults(func=cmd_demo)

    f = sub.add_parser("fetch", help="download scans from the EUMETSAT Data Store")
    f.add_argument("--start", required=True, help="e.g. 2026-03-01 or 2026-03-01T00:00 (UTC)")
    f.add_argument("--end", required=True)
    f.add_argument("--out", default="data")
    f.add_argument(
        "--every-min",
        type=int,
        default=30,
        help="keep one scan every N minutes (multiple of 30 gives matching pairs)",
    )
    f.add_argument("--dry-run", action="store_true", help="only list what would be downloaded")
    f.add_argument("--fci-collection", default=None, help="override the FCI collection id")
    f.add_argument("--seviri-collection", default=None, help="override the SEVIRI collection id")
    f.set_defaults(func=cmd_fetch)

    c = sub.add_parser("compare", help="compare downloaded scans, write results.csv")
    c.add_argument("--data", default="data")
    c.add_argument("--out", default="results.csv")
    c.add_argument("--pairs", nargs="+", default=list(DEFAULT_PAIRS), choices=list(PAIRS))
    c.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        default=[10.0, 50.0, -15.0, 25.0],
        metavar=("LAT_MIN", "LAT_MAX", "LON_MIN", "LON_MAX"),
    )
    c.add_argument("--box-factor", type=int, default=10, help="grid cells per box side")
    c.add_argument("--max-std", type=float, default=1.0, help="max std inside a quiet box (K)")
    c.add_argument("--tolerance-min", type=float, default=5.0)
    c.set_defaults(func=cmd_compare)

    r = sub.add_parser("report", help="make an HTML report from results.csv")
    r.add_argument("results", help="path to results.csv")
    r.add_argument("--out", default="fciwatch_report.html")
    r.add_argument("--title", default="FCI calibration watch")
    r.add_argument("--baseline-start", default=None, help="e.g. 2026-03-01")
    r.add_argument("--baseline-end", default=None, help="e.g. 2026-03-15")
    r.add_argument(
        "--echarts-path", default=None, help="local echarts.min.js to inline (offline report)"
    )
    _add_report_options(r)
    r.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
