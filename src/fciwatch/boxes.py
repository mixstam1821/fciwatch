"""Average both images into boxes and keep only the boxes that are 'quiet'.

Why boxes?
  * FCI and SEVIRI do not see the exact same pixel. They have different pixel sizes,
    slightly different viewing angles, and they scan the disk at slightly different
    moments. A pixel-to-pixel comparison would be very noisy.
  * If we first average over a box (for example 10 x 10 pixels), most of this
    mismatch disappears.

Why 'quiet' boxes only?
  * If a box contains a cloud edge, the average depends on exactly where the edge is.
    The two instruments will disagree because of geometry, not because of calibration.
  * So we keep a box only when the pixels inside it are similar (small standard
    deviation) in BOTH images.
"""

from __future__ import annotations

import warnings

import numpy as np


def block_reduce_stats(arr: np.ndarray, factor: int):
    """Mean, standard deviation and valid-pixel count for each `factor` x `factor` box.

    NaN values are ignored. Rows or columns that do not fill a complete box at the
    edge of the image are dropped.
    """
    arr = np.asarray(arr, dtype=float)
    if arr.ndim != 2:
        raise ValueError("Expected a 2-D array")
    if factor < 1:
        raise ValueError("factor must be 1 or larger")
    ny, nx = arr.shape
    ny2, nx2 = (ny // factor) * factor, (nx // factor) * factor
    if ny2 == 0 or nx2 == 0:
        raise ValueError("Image is smaller than one box")

    # Cut the image into boxes. After the reshape and transpose, the last axis holds
    # all the pixels of one box.
    boxes = arr[:ny2, :nx2].reshape(ny2 // factor, factor, nx2 // factor, factor)
    boxes = boxes.transpose(0, 2, 1, 3).reshape(ny2 // factor, nx2 // factor, factor * factor)

    count = np.isfinite(boxes).sum(axis=2)
    # numpy warns when a box has only NaN. That is normal for us (space, missing data),
    # so we silence it here. Those boxes simply get NaN as result.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        mean = np.nanmean(boxes, axis=2)
        std = np.nanstd(boxes, axis=2)
    return mean, std, count


def select_matching_boxes(
    fci: np.ndarray,
    seviri: np.ndarray,
    factor: int = 10,
    max_std_k: float = 1.0,
    min_valid_frac: float = 0.9,
) -> tuple[np.ndarray, np.ndarray]:
    """Return two 1-D arrays (FCI box means, SEVIRI box means) of the good boxes.

    A box is good when, in both images:
      * at least `min_valid_frac` of its pixels have a valid value, and
      * the standard deviation inside the box is at most `max_std_k` kelvin.

    Both images must already be on the same grid (same shape).
    """
    if fci.shape != seviri.shape:
        raise ValueError(f"Images must have the same shape, got {fci.shape} and {seviri.shape}")

    f_mean, f_std, f_n = block_reduce_stats(fci, factor)
    s_mean, s_std, s_n = block_reduce_stats(seviri, factor)

    need = min_valid_frac * factor * factor
    good = (
        (f_n >= need)
        & (s_n >= need)
        & np.isfinite(f_mean)
        & np.isfinite(s_mean)
        & (f_std <= max_std_k)
        & (s_std <= max_std_k)
    )
    return f_mean[good], s_mean[good]
