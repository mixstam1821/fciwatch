"""Statistics for ONE pair of scans and ONE channel pair.

Sign convention (everywhere in this project):  bias = FCI - SEVIRI, in kelvin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# For normally distributed data, sigma ~ 1.4826 * MAD. MAD is the median absolute
# deviation. We use it because it is not pulled around by a few bad values.
MAD_TO_SIGMA = 1.4826


def robust_sigma(x: np.ndarray) -> float:
    """A spread estimate that ignores outliers."""
    x = np.asarray(x, dtype=float)
    return float(MAD_TO_SIGMA * np.median(np.abs(x - np.median(x))))


@dataclass(frozen=True)
class ScanStats:
    n: int  # number of good boxes used
    bias_median: float  # median of (FCI - SEVIRI) over all boxes, K
    bias_ref: float  # bias at the reference scene temperature, K (the main number)
    slope: float  # change of bias per kelvin of scene temperature (NaN if not fitted)
    robust_sigma: float  # spread of the differences, K
    bt_mean: float  # mean SEVIRI brightness temperature of the boxes, K


def compute_scan_stats(
    fci_bt: np.ndarray,
    seviri_bt: np.ndarray,
    ref_bt: float,
    min_n: int = 50,
    min_range_k: float = 10.0,
    clip_sigma: float = 3.0,
) -> ScanStats | None:
    """Compare matched box means of one scan pair.

    Returns None when there are too few boxes to say anything useful.

    Why `bias_ref` and not just the median?
      The difference FCI - SEVIRI depends a little on how warm the scene is
      (because the spectral bands differ). A winter night and a summer day contain
      different scenes, so the plain median could move up and down with the season
      even if nothing is wrong with the instrument. To avoid this, we fit a straight
      line  difference = a + b * (SEVIRI_BT - ref_bt)  and report `a`: the bias at one
      fixed scene temperature. Then scenes of different temperature can be compared.

      If the scene has too little temperature range for a fit (smaller than
      `min_range_k`), we fall back to the plain median.
    """
    fci_bt = np.asarray(fci_bt, dtype=float)
    seviri_bt = np.asarray(seviri_bt, dtype=float)
    ok = np.isfinite(fci_bt) & np.isfinite(seviri_bt)
    fci_bt, seviri_bt = fci_bt[ok], seviri_bt[ok]
    if fci_bt.size < min_n:
        return None

    diff = fci_bt - seviri_bt
    med = float(np.median(diff))
    sigma = robust_sigma(diff)

    # Remove strong outliers (bad matches, cloud edges that slipped through).
    # The spread gets a small floor (0.01 K, far below real instrument noise). Without it,
    # a perfectly constant difference would give a spread of zero and nothing would be removed.
    limit = clip_sigma * max(sigma, 0.01)
    keep = np.abs(diff - med) <= limit
    diff, seviri_bt = diff[keep], seviri_bt[keep]
    if diff.size < min_n:
        return None

    # 5th to 95th percentile = how wide the scene temperature range is.
    bt_range = float(np.percentile(seviri_bt, 95) - np.percentile(seviri_bt, 5))
    if bt_range >= min_range_k:
        slope, intercept = np.polyfit(seviri_bt - ref_bt, diff, 1)
        slope, bias_ref = float(slope), float(intercept)
    else:
        slope, bias_ref = float("nan"), float(np.median(diff))

    return ScanStats(
        n=int(diff.size),
        bias_median=float(np.median(diff)),
        bias_ref=bias_ref,
        slope=slope,
        robust_sigma=robust_sigma(diff),
        bt_mean=float(np.mean(seviri_bt)),
    )
