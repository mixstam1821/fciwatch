import numpy as np
import pytest

from fciwatch.stats import compute_scan_stats, robust_sigma


def _scene(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    return rng.uniform(250, 300, n)  # wide range of scene temperatures


def test_recovers_offset_and_slope():
    sev = _scene()
    # truth: bias at 280 K is -0.4 K, and it grows by 0.01 K per K of scene temperature
    fci = sev + (-0.4 + 0.01 * (sev - 280.0)) + np.random.default_rng(1).normal(0, 0.05, sev.size)
    st = compute_scan_stats(fci, sev, ref_bt=280.0)
    assert st.bias_ref == pytest.approx(-0.4, abs=0.02)
    assert st.slope == pytest.approx(0.01, abs=0.002)


def test_bias_ref_ignores_scene_mix():
    # Same instrument offset, but one scene is cold and one is warm.
    # bias_ref should agree; the plain median would not.
    def make(lo, hi, seed):
        sev = np.random.default_rng(seed).uniform(lo, hi, 2000)
        return sev + 0.02 * (sev - 280.0), sev

    f1, s1 = make(250, 280, 1)
    f2, s2 = make(270, 300, 2)
    a, b = compute_scan_stats(f1, s1, 280.0), compute_scan_stats(f2, s2, 280.0)
    assert a.bias_ref == pytest.approx(b.bias_ref, abs=0.02)
    assert abs(a.bias_median - b.bias_median) > 0.2


def test_outliers_do_not_move_result():
    sev = _scene()
    fci = sev - 0.3
    fci[:20] += 15.0  # a few wild matches
    st = compute_scan_stats(fci, sev, 280.0)
    assert st.bias_ref == pytest.approx(-0.3, abs=0.02)


def test_too_few_boxes_gives_none():
    assert compute_scan_stats(np.ones(10), np.ones(10), 280.0) is None


def test_narrow_scene_falls_back_to_median():
    sev = np.random.default_rng(3).uniform(279, 281, 500)
    st = compute_scan_stats(sev - 0.25, sev, 280.0)
    assert np.isnan(st.slope)
    assert st.bias_ref == pytest.approx(-0.25, abs=1e-6)


def test_robust_sigma_matches_normal_sigma():
    x = np.random.default_rng(0).normal(0, 2.0, 100000)
    assert robust_sigma(x) == pytest.approx(2.0, rel=0.03)
