"""From many scan results to a drift time series.

A "record" is one row in results.csv: one scan pair, one channel pair.
Columns: time, pair, n, bias_median, bias_ref, slope, robust_sigma, bt_mean

Drift = (bias on a given day) - (bias in a baseline period).

Important: this is a RELATIVE number. The baseline is the "zero". If the instrument
was already off before the baseline period, we cannot see that. We only see change.
"""

from __future__ import annotations

import pandas as pd

RECORD_COLUMNS = [
    "time",
    "pair",
    "n",
    "bias_median",
    "bias_ref",
    "slope",
    "robust_sigma",
    "bt_mean",
]


def load_records(path) -> pd.DataFrame:
    """Read a results.csv and check it has the columns we need."""
    df = pd.read_csv(path, parse_dates=["time"])
    missing = [c for c in RECORD_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    return df.sort_values(["pair", "time"]).reset_index(drop=True)


def compute_daily_drift(
    df: pd.DataFrame,
    baseline_start=None,
    baseline_end=None,
    baseline_days: int = 14,
    value: str = "bias_ref",
) -> pd.DataFrame:
    """Daily median of `value` per channel pair, minus the baseline value.

    Baseline period:
      * If `baseline_start` and `baseline_end` are given, use that window.
      * Otherwise use the first `baseline_days` days of the data.
    The baseline is the median of the daily values inside the window, per pair.

    Output columns: pair, day, value, n_scans, baseline, drift
    """
    if df.empty:
        return pd.DataFrame(columns=["pair", "day", "value", "n_scans", "baseline", "drift"])

    d = df.copy()
    d["day"] = d["time"].dt.floor("D")
    daily = (
        d.groupby(["pair", "day"])
        .agg(value=(value, "median"), n_scans=(value, "size"))
        .reset_index()
    )

    if baseline_start is None:
        start = daily["day"].min()
        end = start + pd.Timedelta(days=baseline_days)
    else:
        start = pd.Timestamp(baseline_start)
        end = (
            pd.Timestamp(baseline_end)
            if baseline_end is not None
            else start + pd.Timedelta(days=baseline_days)
        )

    in_base = daily[(daily["day"] >= start) & (daily["day"] < end)]
    base = in_base.groupby("pair")["value"].median().rename("baseline")
    daily = daily.merge(base, on="pair", how="left")
    # A pair with no data in the baseline window gets NaN drift. We do not guess.
    daily["drift"] = daily["value"] - daily["baseline"]
    return daily


def summarize(daily: pd.DataFrame, threshold_k: float = 0.3, recent_days: int = 7) -> pd.DataFrame:
    """One line per channel pair: how big is the drift, and should someone look at it?

    `threshold_k` is a simple alert level chosen by the user. It is NOT an official
    EUMETSAT requirement. Pick a value that makes sense for your use.
    """
    rows = []
    for pair, g in daily.groupby("pair"):
        g = g.sort_values("day")
        recent = g.tail(recent_days)["drift"]
        valid = g["drift"].dropna()
        recent_med = float(recent.median()) if recent.notna().any() else float("nan")
        max_abs = float(valid.abs().max()) if len(valid) else float("nan")
        n_alert = int((valid.abs() > threshold_k).sum())
        if pd.isna(recent_med):
            status = "NO DATA"
        elif abs(recent_med) > threshold_k:
            status = "CHECK"
        else:
            status = "OK"
        rows.append(
            {
                "pair": pair,
                "first_day": g["day"].min().date().isoformat(),
                "last_day": g["day"].max().date().isoformat(),
                "n_days": len(g),
                "baseline_k": float(g["baseline"].iloc[0])
                if g["baseline"].notna().any()
                else float("nan"),
                "recent_drift_k": recent_med,
                "max_abs_drift_k": max_abs,
                "n_alert_days": n_alert,
                "status": status,
            }
        )
    return pd.DataFrame(rows)
