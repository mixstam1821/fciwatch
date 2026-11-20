"""Fake results with a known drift. Used for the demo and for tests.

THESE ARE NOT REAL MEASUREMENTS. They exist so that you can see what a report looks
like, and so that the tests can check that the drift code finds a drift we put in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .channels import PAIRS


def make_synthetic_records(days: int = 120, scans_per_day: int = 8, seed: int = 0) -> pd.DataFrame:
    """Build a results table for the three default pairs.

    What is hidden inside:
      ir105_ir108: constant offset of -0.35 K, no drift (a healthy channel)
      ir123_ir120: constant offset of +0.10 K, plus a slow drift of +0.004 K per day
                   that starts on day 30
      ir133_ir134: constant offset of -0.20 K, plus a sudden +0.50 K step on day 80
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-01-01")
    rows = []
    for day in range(days):
        for k in range(scans_per_day):
            t = start + pd.Timedelta(days=day, hours=k * 24 / scans_per_day)
            for name, offset, drift in (
                ("ir105_ir108", -0.35, 0.0),
                ("ir123_ir120", 0.10, 0.004 * max(0, day - 30)),
                ("ir133_ir134", -0.20, 0.5 if day >= 80 else 0.0),
            ):
                noise = rng.normal(0, 0.08)  # scan-to-scan noise
                rows.append(
                    {
                        "time": t,
                        "pair": name,
                        "n": int(rng.integers(300, 900)),
                        "bias_median": offset + drift + noise,
                        "bias_ref": offset + drift + noise,
                        "slope": float(rng.normal(0.01, 0.003)),
                        "robust_sigma": float(abs(rng.normal(0.4, 0.05))),
                        "bt_mean": PAIRS[name].ref_bt + float(rng.normal(0, 3)),
                    }
                )
    return pd.DataFrame(rows)
