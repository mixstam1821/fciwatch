"""The whole numeric chain without any satellite files:
two fake images -> quiet boxes -> scan statistics. We know the answer, so we can check it."""

import numpy as np
import pytest

from fciwatch.boxes import select_matching_boxes
from fciwatch.stats import compute_scan_stats


def test_images_to_bias_recovers_known_offset():
    rng = np.random.default_rng(42)
    # A smooth "scene": a warm-to-cold gradient, plus a cloudy, noisy corner.
    y, x = np.mgrid[0:400, 0:400]
    seviri = 300.0 - 0.1 * y + 0.02 * x
    seviri[:100, :100] += rng.normal(0, 6, (100, 100))  # cloud edges: must be filtered out

    true_offset, true_slope = -0.35, 0.01
    fci = seviri + true_offset + true_slope * (seviri - 280.0)
    fci = fci + rng.normal(0, 0.1, fci.shape)  # pixel noise, averages out inside the boxes

    f_box, s_box = select_matching_boxes(fci, seviri, factor=10, max_std_k=1.0)
    assert f_box.size < (400 // 10) ** 2  # the cloudy corner was removed

    st = compute_scan_stats(f_box, s_box, ref_bt=280.0)
    assert st.bias_ref == pytest.approx(true_offset, abs=0.03)
    assert st.slope == pytest.approx(true_slope, abs=0.003)
