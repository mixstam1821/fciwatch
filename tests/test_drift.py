import pandas as pd
import pytest

from fciwatch.drift import compute_daily_drift, summarize
from fciwatch.synthetic import make_synthetic_records


def test_baseline_is_zero_and_hidden_drift_is_found():
    daily = compute_daily_drift(make_synthetic_records(days=120, seed=1))

    # healthy channel: drift stays near zero
    ok = daily[daily.pair == "ir105_ir108"]
    assert ok["drift"].abs().max() < 0.1

    # slow drift: +0.004 K/day since day 30. At day 119 that is about +0.36 K.
    slow = daily[daily.pair == "ir123_ir120"].sort_values("day")
    assert slow["drift"].iloc[-1] == pytest.approx(0.004 * 89, abs=0.08)

    # step of +0.5 K on day 80
    step = daily[daily.pair == "ir133_ir134"].sort_values("day")
    assert step["drift"].iloc[:70].abs().max() < 0.1
    assert step["drift"].iloc[-1] == pytest.approx(0.5, abs=0.1)


def test_summary_flags_only_the_drifting_channels():
    daily = compute_daily_drift(make_synthetic_records(days=120, seed=2))
    s = summarize(daily, threshold_k=0.3).set_index("pair")
    assert s.loc["ir105_ir108", "status"] == "OK"
    assert s.loc["ir123_ir120", "status"] == "CHECK"
    assert s.loc["ir133_ir134", "status"] == "CHECK"


def test_explicit_baseline_window():
    t = pd.date_range("2026-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {
            "time": t,
            "pair": "p",
            "n": 100,
            "bias_median": range(10),
            "bias_ref": [float(i) for i in range(10)],
            "slope": 0.0,
            "robust_sigma": 0.1,
            "bt_mean": 280.0,
        }
    )
    daily = compute_daily_drift(df, baseline_start="2026-01-03", baseline_end="2026-01-05")
    # baseline = median of days with value 2 and 3 = 2.5
    assert daily["baseline"].iloc[0] == pytest.approx(2.5)
    assert daily["drift"].iloc[-1] == pytest.approx(9 - 2.5)


def test_empty_input_does_not_crash():
    assert compute_daily_drift(pd.DataFrame(columns=["time", "pair", "bias_ref"])).empty
