import numpy as np
import pytest

from fciwatch.boxes import block_reduce_stats, select_matching_boxes


def test_block_mean_is_correct():
    a = np.arange(16, dtype=float).reshape(4, 4)
    mean, _std, n = block_reduce_stats(a, 2)
    assert mean.shape == (2, 2)
    assert mean[0, 0] == pytest.approx((0 + 1 + 4 + 5) / 4)
    assert (n == 4).all()


def test_nan_is_ignored_and_counted():
    a = np.ones((4, 4))
    a[0, 0] = np.nan
    mean, _, n = block_reduce_stats(a, 2)
    assert n[0, 0] == 3 and mean[0, 0] == 1.0


def test_all_nan_box_gives_nan_without_crash():
    a = np.full((2, 2), np.nan)
    mean, _, n = block_reduce_stats(a, 2)
    assert np.isnan(mean[0, 0]) and n[0, 0] == 0


def test_edge_rows_are_dropped():
    mean, _, _ = block_reduce_stats(np.ones((5, 7)), 2)
    assert mean.shape == (2, 3)


def test_noisy_box_is_rejected():
    rng = np.random.default_rng(1)
    base = np.full((20, 20), 280.0)
    noisy = base.copy()
    noisy[:10, :10] += rng.normal(0, 5, (10, 10))  # one cloudy quarter
    f, _s = select_matching_boxes(noisy, base, factor=10, max_std_k=1.0)
    assert f.size == 3  # the noisy box is gone, the other three stay


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        select_matching_boxes(np.ones((10, 10)), np.ones((10, 20)))
